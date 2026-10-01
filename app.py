import inspect
import json
from pathlib import Path
from typing import Any

import streamlit as st


BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "support_cards.json"
MAX_SELECTED_CARDS = 6
TRACK_KEY_PREFIX = "track::"


def load_cards(path: Path = DATA_FILE) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as data_file:
        cards = json.load(data_file)
    if not isinstance(cards, list):
        raise ValueError("support_cards.json은 JSON 배열이어야 합니다.")
    return [card for card in cards if isinstance(card, dict) and card.get("code")]


def gold_skill_names(card: dict[str, Any]) -> list[str]:
    raw_skills = card.get("gold_skills", [])
    names = []
    for skill in raw_skills:
        name = skill.get("name", "") if isinstance(skill, dict) else str(skill)
        if name and name not in names:
            names.append(name)
    if not names:
        names = [
            str(skill["name"])
            for skill in card.get("skills", [])
            if isinstance(skill, dict) and skill.get("is_gold") and skill.get("name")
        ]
    return names


def choice_task_key(card_code: str, event_index: int, choice_index: int) -> str:
    return f"{TRACK_KEY_PREFIX}choice::{card_code}::{event_index}::{choice_index}"


def skill_task_key(card_code: str, skill_index: int) -> str:
    return f"{TRACK_KEY_PREFIX}skill::{card_code}::{skill_index}"


def build_tasks(cards: list[dict[str, Any]]) -> list[str]:
    task_keys = []
    for card in cards:
        code = str(card["code"])
        for event_index, event in enumerate(card.get("events", [])):
            for choice_index, _ in enumerate(event.get("choices", [])):
                task_keys.append(choice_task_key(code, event_index, choice_index))
        for skill_index, _ in enumerate(gold_skill_names(card)):
            task_keys.append(skill_task_key(code, skill_index))
    return task_keys


def missed_gold_skill_events(
    cards: list[dict[str, Any]],
    state: Any,
) -> list[dict[str, str]]:
    missed = []
    for card in cards:
        code = str(card["code"])
        gold_names = gold_skill_names(card)
        skill_records = [
            skill for skill in card.get("skills", [])
            if isinstance(skill, dict) and skill.get("is_gold")
        ]

        for skill_index, skill_name in enumerate(gold_names):
            if state.get(skill_task_key(code, skill_index), False):
                continue
            records = [skill for skill in skill_records if skill.get("name") == skill_name]
            skill_codes = {str(skill.get("code", "")) for skill in records if skill.get("code")}
            normalized_name = " ".join(skill_name.casefold().split())

            for event_index, event in enumerate(card.get("events", [])):
                for choice_index, choice in enumerate(event.get("choices", [])):
                    choice_key = choice_task_key(code, event_index, choice_index)
                    if state.get(choice_key, False):
                        continue

                    linked_skills = [
                        skill for skill in choice.get("skills", [])
                        if isinstance(skill, dict)
                    ]
                    matches_skill = any(
                        (skill_codes and str(skill.get("code", "")) in skill_codes)
                        or " ".join(str(skill.get("name", "")).casefold().split()) == normalized_name
                        for skill in linked_skills
                    )
                    if not matches_skill:
                        choice_text = " ".join(
                            [
                                str(choice.get("text", "")),
                                *[str(reward) for reward in choice.get("rewards", [])],
                            ]
                        ).casefold()
                        matches_skill = normalized_name in " ".join(choice_text.split())
                    if matches_skill:
                        missed.append(
                            {
                                "card": str(card.get("name", "이름 없는 카드")),
                                "skill": skill_name,
                                "event": str(event.get("name", "이름 없는 이벤트")),
                                "choice": str(choice.get("text") or f"선택지 {choice_index + 1}"),
                            }
                        )
    return missed


def card_label(card: dict[str, Any]) -> str:
    card_type = card.get("type", "")
    suffix = f" · {card_type}" if card_type else ""
    return f"{card.get('name', '이름 없는 카드')}{suffix}"


st.set_page_config(
    page_title="육성 체크보드 | 우마무스메",
    page_icon="🏇",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
    <style>
    :root {
        --ink: #19352b;
        --muted: #65756d;
        --paper: #f4f6f0;
        --panel: #ffffff;
        --line: #d9e1d8;
        --leaf: #3f7958;
        --coral: #d9674e;
    }
    .stApp { background: var(--paper); color: var(--ink); }
    .block-container { max-width: 1360px; padding-top: 2rem; padding-bottom: 3rem; }
    [data-testid="stSidebar"] { background: #eaf0e8; border-right: 1px solid var(--line); }
    [data-testid="stSidebar"] .block-container { padding-top: 1.6rem; }
    h1, h2, h3 { color: var(--ink); }
    h1 { font-family: Georgia, "Batang", serif; font-size: 2.2rem; }
    .eyebrow { color: var(--coral); font-size: 0.75rem; font-weight: 700; letter-spacing: 0.12em; }
    [data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--line); border-top: 3px solid var(--leaf); border-radius: 6px; padding: 0.8rem 1rem; }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stTabs"] button[aria-selected="true"] { color: var(--leaf); border-bottom-color: var(--coral); }
    [data-testid="stProgressBar"] > div > div > div > div { background-color: var(--leaf); }
    hr { border-color: var(--line); }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="eyebrow">TRAINING LOG / SUPPORT DECK</div>', unsafe_allow_html=True)
st.title("육성 체크보드")

with st.sidebar:
    st.markdown("## 육성 덱")
    st.caption("최대 6장 선택")

if not DATA_FILE.exists():
    st.warning("카드 데이터 파일이 없습니다.")
    st.code("python make_json.py", language="powershell")
    st.stop()

try:
    cards = load_cards()
except (OSError, json.JSONDecodeError, ValueError) as error:
    st.error(f"카드 데이터를 읽지 못했습니다: {error}")
    st.stop()

cards_by_code = {str(card["code"]): card for card in cards}
if not cards_by_code:
    st.warning("카드 데이터가 비어 있습니다. 데이터 생성 스크립트를 실행해 주세요.")
    st.code("python make_json.py", language="powershell")
    st.stop()

card_codes = list(cards_by_code)
if "max_selections" in inspect.signature(st.multiselect).parameters:
    with st.sidebar:
        selected_codes = st.multiselect(
            "육성할 서포트 카드",
            options=card_codes,
            format_func=lambda code: card_label(cards_by_code[code]),
            max_selections=MAX_SELECTED_CARDS,
            placeholder="카드 이름으로 검색",
            key="selected_card_codes",
        )
else:
    selected_codes = []
    for slot in range(MAX_SELECTED_CARDS):
        available_codes = [code for code in card_codes if code not in selected_codes]
        with st.sidebar:
            selected_code = st.selectbox(
                f"카드 {slot + 1}",
                options=[""] + available_codes,
                format_func=lambda code: "선택 안 함" if not code else card_label(cards_by_code[code]),
                key=f"selected_card_slot_{slot}",
            )
        if selected_code:
            selected_codes.append(selected_code)

with st.sidebar:
    st.caption(f"선택 {len(selected_codes)} / {MAX_SELECTED_CARDS}")
    if st.button("체크 초기화", use_container_width=True):
        for key in list(st.session_state):
            if key.startswith(TRACK_KEY_PREFIX):
                del st.session_state[key]
        st.rerun()

selected_cards = [cards_by_code[code] for code in selected_codes]
task_keys = build_tasks(selected_cards)
completed_tasks = sum(bool(st.session_state.get(key, False)) for key in task_keys)
remaining_tasks = len(task_keys) - completed_tasks
missed_gold_events = missed_gold_skill_events(selected_cards, st.session_state)

with st.sidebar:
    st.markdown("### ⚠️ 누락된 금색 스킬 경고")
    if missed_gold_events:
        st.warning(f"미완료 이벤트 {len(missed_gold_events)}개")
        for missed_event in missed_gold_events:
            st.markdown(f"**{missed_event['card']}** · {missed_event['skill']}")
            st.caption(f"{missed_event['event']} / {missed_event['choice']}")
    else:
        st.caption("현재 누락된 금색 스킬 이벤트가 없습니다.")

metric_columns = st.columns(3)
metric_columns[0].metric("선택 카드", f"{len(selected_cards)} / {MAX_SELECTED_CARDS}")
metric_columns[1].metric("완료 항목", f"{completed_tasks} / {len(task_keys)}")
metric_columns[2].metric("남은 항목", remaining_tasks)
st.progress(completed_tasks / len(task_keys) if task_keys else 0.0)
st.divider()

if not selected_cards:
    st.info("사이드바에서 현재 육성 중인 서포트 카드를 선택하세요.")
    st.stop()

card_tabs = st.tabs([card.get("name", "이름 없는 카드") for card in selected_cards])
for card, card_tab in zip(selected_cards, card_tabs):
    code = str(card["code"])
    with card_tab:
        st.markdown(f"### {card.get('name', '이름 없는 카드')}")
        st.caption(" · ".join(value for value in (card.get("type", ""), card.get("rarity", "")) if value))
        event_column, skill_column = st.columns([1.7, 1], gap="large")

        with event_column:
            st.markdown("#### 이벤트 선택지")
            events = card.get("events", [])
            if not events:
                st.caption("이벤트 정보가 없습니다.")
            for event_index, event in enumerate(events):
                st.markdown(f"**{event.get('name', '이름 없는 이벤트')}**")
                choices = event.get("choices", [])
                if not choices:
                    st.caption("선택지 정보가 없습니다.")
                for choice_index, choice in enumerate(choices):
                    label = choice.get("text") or f"선택지 {choice_index + 1}"
                    st.checkbox(
                        label,
                        key=choice_task_key(code, event_index, choice_index),
                    )
                    rewards = choice.get("rewards", [])
                    linked_skills = [
                        skill.get("name", "")
                        for skill in choice.get("skills", [])
                        if isinstance(skill, dict) and skill.get("name")
                    ]
                    detail_parts = []
                    if rewards:
                        detail_parts.append("보상: " + " / ".join(rewards))
                    if linked_skills:
                        detail_parts.append("스킬: " + ", ".join(linked_skills))
                    if detail_parts:
                        st.caption(" · ".join(detail_parts))

        with skill_column:
            st.markdown("#### 금색 스킬")
            skill_names = gold_skill_names(card)
            if not skill_names:
                st.caption("등록된 금색 스킬이 없습니다.")
            all_skills = [
                skill for skill in card.get("skills", [])
                if isinstance(skill, dict) and skill.get("is_gold")
            ]
            for skill_index, name in enumerate(skill_names):
                st.checkbox(
                    name,
                    key=skill_task_key(code, skill_index),
                )
                matching_skill = next((skill for skill in all_skills if skill.get("name") == name), None)
                if matching_skill and matching_skill.get("acquisition"):
                    st.caption(matching_skill["acquisition"])
