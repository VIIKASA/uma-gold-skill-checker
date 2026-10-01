from difflib import SequenceMatcher
from typing import Any

from event_utils import display_event_name


def normalize_text(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def event_name_matches(event_name: str, screen_text: str) -> bool:
    target = normalize_text(display_event_name(event_name))
    observed = normalize_text(screen_text)
    if not target or not observed:
        return False
    if target in observed:
        return True
    if len(target) < 6:
        return False

    margin = max(2, round(len(target) * 0.18))
    shortest = max(1, len(target) - margin)
    longest = min(len(observed), len(target) + margin)
    best_ratio = 0.0
    for width in range(shortest, longest + 1):
        for start in range(len(observed) - width + 1):
            ratio = SequenceMatcher(None, target, observed[start : start + width]).ratio()
            best_ratio = max(best_ratio, ratio)
            if best_ratio >= 0.84:
                return True
    return False


def find_umamusume_windows() -> list[dict[str, Any]]:
    try:
        import pygetwindow
    except ImportError as error:
        raise RuntimeError(
            "pygetwindow가 설치되지 않았습니다. requirements.txt 설치 후 앱을 다시 시작하세요."
        ) from error

    try:
        windows = pygetwindow.getAllWindows()
    except Exception as error:
        raise RuntimeError("실행 중인 Windows 창 목록을 가져오지 못했습니다.") from error

    matches = []
    for window in windows:
        title = str(getattr(window, "title", "") or "").strip()
        normalized_title = title.casefold()
        if "우마무스메" not in normalized_title and "umamusume" not in normalized_title:
            continue

        try:
            matches.append(
                {
                    "handle": str(getattr(window, "_hWnd", title)),
                    "title": title,
                    "left": int(window.left),
                    "top": int(window.top),
                    "width": int(window.width),
                    "height": int(window.height),
                    "is_minimized": bool(getattr(window, "isMinimized", False)),
                }
            )
        except Exception:
            continue
    return matches


def capture_and_read_text(
    window: dict[str, Any],
    tesseract_cmd: str = "",
) -> str:
    if window.get("is_minimized"):
        raise RuntimeError("선택한 우마무스메 창이 최소화되어 있습니다. 창을 복원해 주세요.")
    if window.get("width", 0) <= 0 or window.get("height", 0) <= 0:
        raise RuntimeError("선택한 우마무스메 창의 캡처 영역이 유효하지 않습니다.")

    try:
        import cv2
        import mss
        import numpy as np
        import pytesseract
    except ImportError as error:
        raise RuntimeError(
            "화면 감지 패키지가 없습니다. requirements.txt 설치 후 앱을 다시 시작하세요."
        ) from error

    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd.strip() or "tesseract"

    try:
        with mss.mss() as screen_capture:
            capture_region = {
                "left": window["left"],
                "top": window["top"],
                "width": window["width"],
                "height": window["height"],
            }
            screenshot = np.asarray(screen_capture.grab(capture_region))
    except Exception as error:
        raise RuntimeError("화면 캡처에 실패했습니다. 캡처 영역의 위치와 크기를 확인하세요.") from error

    grayscale = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2GRAY)
    enlarged = cv2.resize(grayscale, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    processed = cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    try:
        return pytesseract.image_to_string(processed, lang="kor+eng", config="--psm 6")
    except pytesseract.TesseractNotFoundError as error:
        raise RuntimeError(
            "Tesseract OCR을 찾을 수 없습니다. Tesseract를 설치하거나 실행 파일 경로를 입력하세요."
        ) from error
    except pytesseract.TesseractError as error:
        raise RuntimeError(
            "한국어 OCR 데이터(kor.traineddata)를 확인하세요."
        ) from error