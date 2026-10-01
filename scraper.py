import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from event_utils import is_continuous_event


BASE_URL = "https://uma.inven.co.kr"
DECKBUILDER_URL = f"{BASE_URL}/dataninfo/deckbuilder/"
DETAIL_AJAX_URL = f"{BASE_URL}/dataninfo/deckbuilder/detail.ajax.php"
DATA_DIR = Path(__file__).parent / "data"
CACHE_FILE = DATA_DIR / "cards.json"
REQUEST_TIMEOUT = 25
REQUEST_INTERVAL_SECONDS = 0.6
SUPPORT_TYPES = {
    "1": "스피드",
    "2": "스태미나",
    "3": "파워",
    "4": "근성",
    "5": "지능",
    "6": "친구",
    "7": "그룹",
}
GOLD_RARITIES = {"레어", "금색", "gold"}


def text_of(element: Any) -> str:
    return element.get_text(" ", strip=True) if element else ""


def parse_card_index(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    card_elements = soup.select("#deckBuilder dl.support-card-list li[data-code]")
    if not card_elements:
        card_elements = soup.select("dl.support-card-list li[data-code]")

    cards = []
    seen_codes = set()
    for element in card_elements:
        code = element.get("data-code", "").strip()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        cards.append(
            {
                "code": code,
                "name": element.get("title", "").strip(),
                "type": SUPPORT_TYPES.get(element.get("data-type", ""), "알 수 없음"),
                "icon": element.get("data-icon", "").strip(),
                "url": f"{BASE_URL}/db/scard/{code}",
            }
        )
    return cards


def parse_event_choices(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("카드 이벤트 응답이 JSON 배열이 아닙니다.")

    events = []
    for item in payload:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        if not is_continuous_event(item):
            continue

        choices = []
        for content in item.get("content", []):
            if not isinstance(content, str):
                continue
            fragment = BeautifulSoup(content, "html.parser")
            choice_text = text_of(fragment.select_one(".word"))
            rewards = [text_of(reward) for reward in fragment.select(".reward")]
            skills = []
            for link in fragment.select("a[data-uma-skill-code]"):
                skills.append(
                    {
                        "code": link.get("data-uma-skill-code", "").strip(),
                        "name": text_of(link),
                        "url": urljoin(BASE_URL, link.get("href", "")),
                    }
                )
            choices.append(
                {
                    "text": choice_text,
                    "rewards": rewards,
                    "skills": skills,
                }
            )

        events.append({"name": str(item["name"]).strip(), "choices": choices})
    return events


def parse_card_skills(html: str) -> tuple[list[dict[str, Any]], list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    skill_root = soup.select_one("#scardSkill")
    if skill_root is None:
        return [], []

    skills = []
    gold_skill_names = []
    for section in skill_root.select(":scope > .db_board"):
        acquisition = text_of(section.select_one(".info_title"))
        for table in section.select(".skill_area table"):
            name_element = table.select_one(".skillName .nameText")
            if name_element is None:
                continue

            skill_link = table.select_one(".skillName a[href]")
            skill_image = table.select_one(".skillImage")
            rarity_text = text_of(skill_image)
            rarity = rarity_text.split()[0] if rarity_text else ""
            skill_code_match = re.search(r"/db/skill/(\d+)", skill_link.get("href", "")) if skill_link else None
            skill = {
                "code": skill_code_match.group(1) if skill_code_match else "",
                "name": text_of(name_element),
                "rarity": rarity,
                "is_gold": rarity.casefold() in GOLD_RARITIES,
                "acquisition": acquisition,
                "description": text_of(table.select_one(".skillInfo")),
            }
            skills.append(skill)
            if skill["is_gold"] and skill["name"] not in gold_skill_names:
                gold_skill_names.append(skill["name"])

    return skills, gold_skill_names


class InvenScraper:
    def __init__(self, request_interval: float = REQUEST_INTERVAL_SECONDS) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; UmaGoldSkillChecker/1.0)",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            }
        )
        self.request_interval = request_interval
        self.last_request_at = 0.0

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        wait_seconds = self.request_interval - (time.monotonic() - self.last_request_at)
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        response = self.session.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
        self.last_request_at = time.monotonic()
        response.raise_for_status()
        if response.apparent_encoding:
            response.encoding = response.apparent_encoding
        return response

    def fetch_card_index(self) -> list[dict[str, Any]]:
        cards = parse_card_index(self.fetch_html(DECKBUILDER_URL))
        if not cards:
            raise RuntimeError("덱빌더에서 서포트 카드 목록을 찾지 못했습니다.")
        return cards

    def fetch_html(self, url: str) -> str:
        return self._request("GET", url).text

    def fetch_events(self, code: str) -> list[dict[str, Any]]:
        response = self._request(
            "POST",
            DETAIL_AJAX_URL,
            data={"type": "supportCard", "code": code},
            headers={
                "Referer": DECKBUILDER_URL,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        try:
            payload = response.json()
        except ValueError:
            payload = json.loads(response.content.decode(response.encoding or "utf-8"))
        return parse_event_choices(payload)

    def fetch_card_skills(self, card_url: str) -> tuple[list[dict[str, Any]], list[str]]:
        response = self._request("GET", card_url)
        return parse_card_skills(response.text)

    def scrape_cards(self, limit: int | None = None) -> list[dict[str, Any]]:
        cards = self.fetch_card_index()
        if limit is not None:
            cards = cards[:limit]

        results = []
        for index, card in enumerate(cards, start=1):
            print(f"[{index}/{len(cards)}] {card['name']}")
            card["events"] = self.fetch_events(card["code"])
            card["skills"], card["gold_skills"] = self.fetch_card_skills(card["url"])
            results.append(card)
        return results


def load_cached_cards(
    cache_file: Path = CACHE_FILE,
    max_age_hours: float = 24,
) -> list[dict[str, Any]] | None:
    if not cache_file.exists():
        return None
    age_seconds = time.time() - cache_file.stat().st_mtime
    if age_seconds > max_age_hours * 60 * 60:
        return None
    try:
        cards = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return cards if isinstance(cards, list) and cards else None


def save_cached_cards(cards: list[dict[str, Any]], cache_file: Path = CACHE_FILE) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = cache_file.with_suffix(cache_file.suffix + ".tmp")
    temporary_file.write_text(
        json.dumps(cards, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_file, cache_file)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="인벤 서포트 카드 이벤트와 금색 스킬을 JSON으로 수집합니다."
    )
    parser.add_argument("--refresh", action="store_true", help="캐시를 무시하고 다시 수집")
    parser.add_argument("--cache-hours", type=float, default=24, help="캐시 유효 시간(기본 24시간)")
    parser.add_argument("--limit", type=int, help="테스트용 카드 수 제한; 이 경우 캐시는 저장하지 않음")
    args = parser.parse_args()

    if args.limit is None and not args.refresh:
        cached_cards = load_cached_cards(max_age_hours=args.cache_hours)
        if cached_cards is not None:
            print(f"캐시 사용: {len(cached_cards)}개 카드 ({CACHE_FILE})")
            return

    cards = InvenScraper().scrape_cards(limit=args.limit)
    if args.limit is None:
        save_cached_cards(cards)
        updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(f"저장 완료: {len(cards)}개 카드, {CACHE_FILE} (수집 시각 UTC {updated_at})")
    else:
        print(f"테스트 수집 완료: {len(cards)}개 카드 (캐시는 갱신하지 않음)")


if __name__ == "__main__":
    main()
