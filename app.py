from datetime import datetime
import inspect
import json
from pathlib import Path
from typing import Any

import streamlit as st

from event_utils import continuous_events, display_event_name
from screen_ocr import capture_and_read_text, event_name_matches, find_umamusume_windows


BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "support_cards.json"
MAX_SELECTED_CARDS = 6
TRACK_KEY_PREFIX = "track::"


def load_cards(path: Path = DATA_FILE) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as data_file:
        cards = json.load(data_file)
    if not isinstance(cards, list):
        raise ValueError("support_cards.json은 JSON 배열이어야 합니다.")
    support_cards = [card for card in cards if isinstance(card, dict) and card.get("code")]
    for card in support_cards:
        card["events"] = continuous_events(card)
    return support_cards


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


def event_task_key(card_code: str, event_index: int) -> str:
    return f"{TRACK_KEY_PREFIX}event::{card_code}::{event_index}"


def skill_task_key(card_code: str, skill_index: int) -> str:
    return f"{TRACK_KEY_PREFIX}skill::{card_code}::{skill_index}"


def build_tasks(cards: list[dict[str, Any]]) -> list[str]:
    task_keys = []
    for card in cards:
        code = str(card["code"])
        for event_index, _ in enumerate(card.get("events", [])):
            task_keys.append(event_task_key(code, event_index))
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
                    if state.get(event_task_key(code, event_index), False):
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
                                "event": display_event_name(str(event.get("name", "이름 없는 이벤트"))),
                                "choice": str(choice.get("text") or f"선택지 {choice_index + 1}"),
                            }
                        )
    return missed


def card_label(card: dict[str, Any]) -> str:
    card_type = card.get("type", "")
    suffix = f" · {card_type}" if card_type else ""
    return f"{card.get('name', '이름 없는 카드')}{suffix}"


@st.fragment(run_every=2)
def render_ocr_monitor(selected_cards: list[dict[str, Any]]) -> None:
    enabled = st.toggle("화면 OCR 자동 체크", key="ocr_enabled")
    if not enabled:
        st.caption("꺼짐")
        return

    with st.expander("게임 창 선택", expanded=False):
        try:
            windows = find_umamusume_windows()
        except RuntimeError as error:
            st.warning(str(error))
            return

        if not windows:
            st.warning("우마무스메 창을 찾지 못했습니다. 게임을 실행한 뒤 다시 시도하세요.")
            st.session_state.pop("ocr_selected_window", None)
            return

        windows_by_handle = {window["handle"]: window for window in windows}
        window_handles = list(windows_by_handle)
        if st.session_state.get("ocr_selected_window") not in windows_by_handle:
            available_window = next(
                (window for window in windows if not window["is_minimized"]),
                windows[0],
            )
            st.session_state["ocr_selected_window"] = available_window["handle"]

        if st.button("우마무스메 창 자동 선택", use_container_width=True):
            available_window = next(
                (window for window in windows if not window["is_minimized"]),
                windows[0],
            )
            st.session_state["ocr_selected_window"] = available_window["handle"]

        selected_handle = st.selectbox(
            "감지된 게임 창",
            options=window_handles,
            format_func=lambda handle: windows_by_handle[handle]["title"],
            key="ocr_selected_window",
        )
        selected_window = windows_by_handle[selected_handle]

    if selected_window["is_minimized"]:
        st.warning("선택한 우마무스메 창이 최소화되어 있습니다. 창을 복원하면 자동 감지가 재개됩니다.")
        return

    with st.expander("OCR 설정", expanded=False):
        tesseract_cmd = st.text_input(
            "Tesseract 경로 (선택)",
            placeholder="PATH에 등록되어 있으면 비워 두세요",
            key="ocr_tesseract_cmd",
        )

    try:
        recognized_text = capture_and_read_text(selected_window, tesseract_cmd)
    except RuntimeError as error:
        st.warning(str(error))
        return

    detected = []
    for card in selected_cards:
        code = str(card["code"])
        for event_index, event in enumerate(card.get("events", [])):
            if not event_name_matches(str(event.get("name", "")), recognized_text):
                continue
            task_key = event_task_key(code, event_index)
            if not st.session_state.get(task_key, False):
                st.session_state[task_key] = True
                detected.append(display_event_name(str(event.get("name", "이벤트"))))

    if detected:
        st.session_state["ocr_last_detected"] = ", ".join(detected)
        st.session_state["ocr_last_detected_at"] = datetime.now().strftime("%H:%M:%S")
        st.rerun(scope="app")

    last_detected = st.session_state.get("ocr_last_detected", "")
    if last_detected:
        st.caption(f"감지 {st.session_state.get('ocr_last_detected_at', '')} · {last_detected}")
    else:
        st.caption("감지 대기 중")


st.set_page_config(
    page_title="육성 체크보드 | 우마무스메",
    page_icon="🏇",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 다크 모드 전용 커스텀 스타일 적용
st.markdown(
    """
    <style>
    :root {
        --ink: #f1f5f9;
        --muted: #94a3b8;
        --paper: #0f172a;
        --panel: #1e293b;
        --line: #334155;
        --leaf: #34d399;
        --coral: #fbbf24;
    }
    .stApp { background: var(--paper); color: var(--ink); }
    .block-container { max-width: 1360px; padding-top: 2rem; padding-bottom: 3rem; }
    [data-testid="stSidebar"] { background: #090d16; border-right: 1px solid var(--line); }
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
event_total = sum(len(card.get("events", [])) for card in selected_cards)
event_completed = sum(
    bool(st.session_state.get(event_task_key(str(card["code"]), event_index), False))
    for card in selected_cards
    for event_index, _ in enumerate(card.get("events", []))
)
missed_gold_events = missed_gold_skill_events(selected_cards, st.session_state)

with st.sidebar:
    render_ocr_monitor(selected_cards)
    if missed_gold_events:
        with st.expander(f"금색 스킬 연결 이벤트 {len(missed_gold_events)}개"):
            for missed_event in missed_gold_events:
                st.caption(f"{missed_event['card']} · {missed_event['skill']} · {missed_event['event']}")

metric_columns = st.columns(2)
metric_columns[0].metric("선택 카드", f"{len(selected_cards)} / {MAX_SELECTED_CARDS}")
metric_columns[1].metric("완료 항목", f"{event_completed} / {event_total}")
st.progress(event_completed / event_total if event_total else 0.0)
st.divider()

if not selected_cards:
    st.info("사이드바에서 현재 육성 중인 서포트 카드를 선택하세요.")
    st.stop()

card_tabs = st.tabs([card.get("name", "이름 없는 카드") for card in selected_cards])
for card, card_tab in zip(selected_cards, card_tabs):
    code = str(card["code"])
    with card_tab:
        st.markdown(f"### {card.get('name', '이름 없는 카드')}")
        events = card.get("events", [])
        skill_names = gold_skill_names(card)
        card_event_done = sum(
            bool(st.session_state.get(event_task_key(code, index), False))
            for index in range(len(events))
        )
        card_skill_done = sum(
            bool(st.session_state.get(skill_task_key(code, index), False))
            for index in range(len(skill_names))
        )
        st.caption(
            f"{card.get('type', '')} · 연속 이벤트 {card_event_done}/{len(events)}"
            f" · 금색 스킬 {card_skill_done}/{len(skill_names)}"
        )
        st.progress(card_event_done / len(events) if events else 0.0)
        event_column, skill_column = st.columns([1.7, 1], gap="medium")

        with event_column:
            st.markdown("#### 연속 이벤트")
            if not events:
                st.caption("등록된 연속 이벤트가 없습니다.")
            for event_index, event in enumerate(events):
                st.checkbox(
                    display_event_name(str(event.get("name", "이름 없는 이벤트"))),
                    key=event_task_key(code, event_index),
                )

        with skill_column:
            st.markdown("#### 금색 스킬")
            if not skill_names:
                st.caption("등록된 금색 스킬이 없습니다.")
            for skill_index, name in enumerate(skill_names):
                st.checkbox(
                    name,
                    key=skill_task_key(code, skill_index),
                )
