import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper import BASE_URL, DECKBUILDER_URL, InvenScraper, text_of


SUPPORT_CARD_LIST_URL = f"{BASE_URL}/db/scard/"
OUTPUT_FILE = Path(__file__).parent / "data" / "support_cards.json"


def parse_support_card_list(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    cards_by_code: dict[str, dict[str, Any]] = {}

    for link in soup.select("a[href]"):
        href = link.get("href", "")
        match = re.search(r"/db/scard/(\d+)(?:[/?#]|$)", href)
        name = text_of(link)
        if not match or not name:
            continue

        code = match.group(1)
        if code in cards_by_code:
            continue

        row = link.find_parent("tr")
        cells = row.find_all("td", recursive=False) if row else []
        image = cells[0].select_one("img") if cells else None
        cards_by_code[code] = {
            "code": code,
            "name": name,
            "type": text_of(cells[2]) if len(cells) > 2 else "",
            "icon": image.get("src", "") if image else "",
            "url": urljoin(BASE_URL, href),
        }

    return list(cards_by_code.values())


def save_support_cards(cards: list[dict[str, Any]], output_file: Path = OUTPUT_FILE) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = output_file.with_suffix(output_file.suffix + ".tmp")
    temporary_file.write_text(
        json.dumps(cards, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_file, output_file)


def build_support_cards() -> list[dict[str, Any]]:
    scraper = InvenScraper()
    scraper.fetch_html(DECKBUILDER_URL)
    listing_html = scraper.fetch_html(SUPPORT_CARD_LIST_URL)
    cards = parse_support_card_list(listing_html)
    if not cards:
        raise RuntimeError("서포트 카드 목록 페이지에서 카드 링크를 찾지 못했습니다.")

    print(f"목록에서 {len(cards)}개 카드를 확인했습니다.")
    for index, card in enumerate(cards, start=1):
        print(f"[{index}/{len(cards)}] {card['name']}")
        card["events"] = scraper.fetch_events(card["code"])
        card["skills"], card["gold_skills"] = scraper.fetch_card_skills(card["url"])
    return cards


def main() -> None:
    cards = build_support_cards()
    save_support_cards(cards)
    print(f"완료: {len(cards)}개 카드 저장 -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()