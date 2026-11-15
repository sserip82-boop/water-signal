# algae.py — 녹조(조류경보) 측정 자료를 불러오는 파일 (5차 G1단계)
# 실행: .venv\Scripts\python.exe algae.py
# 조류경보 측정은 매일이 아니라 주 1~2번이다. 그래서 '하루 평균' 표가 아니라 '측정한 날' 표를 만든다.
import datetime as dt
import json

import pandas as pd
import requests

import api
import config

# 실제 응답을 받아 확인한 주소 (2026-11-15)
ALGAE_URL = "https://apis.data.go.kr/1480523/nieragainstalgae/algaePreMeasure"


def request_algae(site, year, month):
    """지점 한 곳의 한 달 치 측정 줄(목록)을 받는다. 문제가 있으면 쉬운 말로 오류를 낸다."""
    params = {"serviceKey": api.read_key(), "pageNo": 1, "numOfRows": 100, "resultType": "JSON",
              "ptNoList": site, "wmyrList": str(year), "wmodList": f"{month:02d}"}
    try:
        response = requests.get(ALGAE_URL, params=params, timeout=30)
        body = response.json()["algaePreMeasure"]
    except (requests.RequestException, ValueError, KeyError):  # 오류 글에 인증키가 섞일 수 있다
        raise RuntimeError("녹조 자료를 받지 못했어요.") from None
    code = body["header"]["code"]
    if code != "00":
        raise RuntimeError(f"녹조 자료 오류 {code}: {api.ERROR_HINTS.get(code, body['header']['message'])}")
    return body.get("item") or []  # 자료가 없으면 item이 비어 온다


def to_number(text):
    """'7165' → 7165.0. 글자('정량한계미만')나 빈 값(null)은 빈 값(NaN)으로 둔다."""
    try:
        return float(text)
    except (TypeError, ValueError):
        return float("nan")


def make_table(items):
    """응답 줄 목록 → (날짜, DO, 남조류, 수온, 클로로필-a) 표. 날짜순, 같은 날은 하나만."""
    rows = []
    for item in items:
        row = {"날짜": pd.to_datetime(item["CHCK_DE"], format="%Y.%m.%d")}  # '2026.11.09' 꼴
        for code, name in config.ALGAE_ITEMS.items():
            row[name] = to_number(item.get(code))
        rows.append(row)
    table = pd.DataFrame(rows, columns=["날짜"] + list(config.ALGAE_ITEMS.values()))
    # 한 달씩 요청하면 전달 마지막 며칠이 섞여 와서 같은 날이 두 번 나올 수 있다
    return table.drop_duplicates("날짜").sort_values("날짜").reset_index(drop=True)


def recent_months(today, months):
    """오늘이 든 달부터 거꾸로 months개월의 (연, 월) 목록. 예: 11월, 3개월 → 9·10·11월"""
    year, month = today.year, today.month
    result = []
    for _ in range(months):
        result.insert(0, (year, month))
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    return result


def load_algae(site, today, months=config.ALGAE_MONTHS):
    """지점 한 곳의 최근 months개월 측정 표."""
    items = []
    for year, month in recent_months(today, months):
        items += request_algae(site, year, month)
    return make_table(items)


if __name__ == "__main__":
    today = dt.date.today()
    for name, site in config.ALGAE_SITES.items():
        table = load_algae(site, today)
        print(f"== {name} ({site}) {len(table)}번 측정")
        print(table.tail(4).to_string(index=False))
    # 이번 달 물금·매리 응답을 그대로 저장해 둔다 (응답에는 인증키가 들어 있지 않다)
    sample = request_algae(config.ALGAE_SITES["물금·매리"], today.year, today.month)
    path = api.SAMPLES_FOLDER / "algae_sample.json"
    path.write_text(json.dumps(sample, ensure_ascii=False, indent=1), encoding="utf-8")
    print("저장:", path.name)
