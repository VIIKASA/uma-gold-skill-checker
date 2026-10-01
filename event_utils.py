import re
from html import unescape
from typing import Any


CONTINUOUS_EVENT_PREFIX = re.compile(r"^\s*[①-⑳]\s*")


def is_continuous_event(event: Any) -> bool:
    if not isinstance(event, dict):
        return False
    return bool(CONTINUOUS_EVENT_PREFIX.match(str(event.get("name", ""))))


def continuous_events(card: dict[str, Any]) -> list[dict[str, Any]]:
    return [event for event in card.get("events", []) if is_continuous_event(event)]


def display_event_name(name: str) -> str:
    return CONTINUOUS_EVENT_PREFIX.sub("", unescape(name)).strip()