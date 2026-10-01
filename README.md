# 우마무스메 서포트 카드 이벤트 및 금색 스킬 체커

## 실행

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python make_json.py
streamlit run app.py
```

`make_json.py`는 최초 데이터 생성 또는 개발자 수동 갱신 시 한 번만 실행합니다. `app.py`는 로컬 JSON만 읽으며 크롤링하지 않습니다.

화면 OCR 자동 체크는 앱의 사이드바에서 켤 수 있습니다. `우마무스메 창 자동 선택` 버튼을 누르거나 감지된 게임 창을 드롭다운에서 선택하면 해당 창 영역만 캡처합니다. 게임 창이 실행되지 않았거나 최소화된 경우 안내가 표시됩니다. Python 패키지 외에 Tesseract OCR 실행 파일과 한국어 학습 데이터(`kor.traineddata`)가 필요합니다. Tesseract가 `PATH`에 없으면 앱의 경로 입력란에 `tesseract.exe` 경로를 지정하세요.

앱과 데이터 생성기는 이름 앞에 번호(①, ②, ③ 등)가 붙은 서포트 카드 연속 이벤트만 표시하고 저장합니다. 기존 `support_cards.json`에도 같은 필터가 적용됩니다.

## 데이터 형식

`data/support_cards.json`은 카드별 연속 이벤트 `events[]`, `skills[]`, `gold_skills[]`를 포함하는 JSON 배열입니다. 앱은 여기서 선택한 최대 6장의 이벤트 및 금색 스킬 체크 상태를 세션 동안 유지합니다.

```json
[
  {
    "code": "카드 코드",
    "name": "카드 이름",
    "type": "스피드",
    "events": [
      {
        "name": "이벤트 이름",
        "choices": [
          {"text": "선택지", "rewards": [], "skills": []}
        ]
      }
    ],
    "skills": [],
    "gold_skills": ["금색 스킬 이름"]
  }
]
```

## scraper 캐시 갱신

```bash
python scraper.py
python scraper.py --refresh
python scraper.py --limit 1
```

기본 실행은 `data/cards.json`의 캐시가 24시간 이내이면 재사용합니다. `--refresh`는 캐시를 무시하고 다시 수집하며, `--limit 1`은 테스트용으로 카드 한 장만 읽고 캐시는 변경하지 않습니다. 카드 요청 사이에는 간격을 두며, 사이트의 접근 정책과 이용 조건을 준수하세요.
