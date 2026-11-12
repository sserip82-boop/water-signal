# api.py — 공공데이터 API에 "자료 주세요" 하고 요청을 보내는 파일
import json
import tomllib  # secrets.toml 파일을 읽는 파이썬 기본 도구
from pathlib import Path

import pandas as pd  # 표를 다루는 도구
import requests  # 인터넷으로 요청을 보내는 도구

import config

FOLDER = Path(__file__).parent  # 이 파일이 들어 있는 폴더
SECRETS_FILE = FOLDER / ".streamlit" / "secrets.toml"
SAMPLES_FOLDER = FOLDER / "samples"
DATA_FOLDER = FOLDER / "data"  # 받아 둔 자료(캐시)를 넣는 폴더


def read_key():
    """secrets.toml에서 인증키를 꺼낸다. (streamlit 없이도 동작)"""
    with open(SECRETS_FILE, "rb") as f:
        secrets = tomllib.load(f)
    return secrets["WATER_API_KEY"]


def request_water_data(site_id, start_date, end_date, page_no=1):
    """측정소 한 곳의 자료를 요청하고, 응답(requests 응답 객체)을 돌려준다."""
    url = f"{config.BASE_URL}/{config.OPERATION}"
    # 요청변수 = 식당 주문서의 칸들 (무엇을, 얼마나, 언제 것을)
    params = {
        "serviceKey": read_key(),         # 인증키 (화면에 출력하지 않는다!)
        "pageNo": page_no,                # 몇 번째 쪽
        "numOfRows": config.NUM_OF_ROWS,  # 한 쪽에 몇 줄
        "resultType": "JSON",             # 응답 형식
        "siteId": site_id,                # 측정소 번호
        "startDate": start_date,          # 시작 시각 (14자리)
        "endDate": end_date,              # 끝 시각 (14자리)
    }
    return requests.get(url, params=params, timeout=30)


def save_response(response, name):
    """응답 원문을 samples 폴더에 저장하고, 저장한 파일 경로를 돌려준다."""
    try:
        data = response.json()  # JSON으로 읽히면 보기 좋게 정리해서 저장
        path = SAMPLES_FOLDER / f"{name}.json"
        text = json.dumps(data, ensure_ascii=False, indent=2)
    except ValueError:  # JSON이 아니면(오류 응답은 XML일 수 있음) 그대로 저장
        path = SAMPLES_FOLDER / f"{name}.xml"
        text = response.text
    path.write_text(text, encoding="utf-8")
    return path


# 오류 코드별 "무엇을 확인할지" (공공데이터포털 공통 오류 코드)
ERROR_HINTS = {
    "22": "하루 호출 한도를 넘었어요. 내일 다시 해 보세요.",
    "30": "등록되지 않은 키예요. secrets.toml의 키를 다시 확인하세요.",
    "31": "키 사용 기간이 끝났어요. 포털에서 활용기간을 확인하세요.",
}


def print_summary(response):
    """결과코드, 결과메시지, 받은 건수만 화면에 출력한다."""
    try:
        body = response.json()[config.OPERATION]
    except (ValueError, KeyError):  # 예상한 모양이 아니면 오류 응답이다
        print("오류: 예상과 다른 응답입니다. HTTP 상태:", response.status_code)
        print("확인할 것: samples에 저장된 파일을 열어 오류 내용을 보세요.")
        return
    code = body["header"]["code"]
    print("결과코드:", code, "/ 결과메시지:", body["header"]["message"])
    if code != "00":
        print("확인할 것:", ERROR_HINTS.get(code, "포털의 오류 코드 표를 보세요."))
        return
    print("전체 건수:", body["totalCount"], "/ 이번에 받은 건수:", len(body["item"]))
    if body["totalCount"] == 0:
        print("확인할 것: 그 기간에 자료가 없어요. 날짜를 더 예전으로 바꿔 보세요.")


def fetch_all_pages(site_id, start_date, end_date):
    """쪽(page)이 여러 개여도 끝까지 받아서, 모든 줄을 리스트 하나로 돌려준다."""
    rows, page = [], 1
    while True:
        response = request_water_data(site_id, start_date, end_date, page)
        body = response.json()[config.OPERATION]
        if body["header"]["code"] != "00":
            raise RuntimeError("API 오류 코드 " + body["header"]["code"])
        rows += body["item"]
        print(f"  {page}쪽: {len(body['item'])}줄 받음 (전체 {body['totalCount']}줄)")
        if len(rows) >= body["totalCount"] or not body["item"]:
            return rows  # 다 받았거나 더 올 것이 없으면 끝
        page += 1


def day_before(day):
    """'20260818' → '20260817'. API가 시작일 당일은 빼고 주기 때문에 쓴다."""
    one_day = pd.Timedelta(days=1)
    return (pd.to_datetime(day, format="%Y%m%d") - one_day).strftime("%Y%m%d")


def load_period(site_id, first_day, last_day):
    """first_day~last_day('20260818' 꼴) 자료를 표로 돌려준다. 받아 둔 게 있으면 재사용."""
    cache = DATA_FOLDER / f"{site_id}_{first_day}_{last_day}.csv"
    if cache.exists():  # 캐시 = 한 번 받은 자료를 넣어 두는 서랍
        print("저장해 둔 파일을 다시 씀:", cache.name)
        return pd.read_csv(cache)
    print("API에서 새로 받는 중:", site_id, first_day, "~", last_day)
    # 실제로 확인한 사실: 시작일 당일은 안 오고, 종료일 당일은 온다.
    rows = fetch_all_pages(site_id, day_before(first_day) + "000000", last_day + "000000")
    table = pd.DataFrame(rows)  # 데이터프레임 = 파이썬 안의 엑셀 표
    DATA_FOLDER.mkdir(exist_ok=True)
    table.to_csv(cache, index=False, encoding="utf-8-sig")
    return table


def run_once(name, site_id, start_date, end_date):
    """요청 한 번 보내기 → 저장 → 요약 출력."""
    response = request_water_data(site_id, start_date, end_date)
    saved = save_response(response, name)
    print(f"[{saved.name}] {site_id} {start_date[:8]}~{end_date[:8]}")
    print_summary(response)


if __name__ == "__main__":
    # ① 포털 미리보기에서 성공한 요청을 그대로 다시 보낸다
    run_once("first_response", "S03002", "20261105000000", "20261112000000")
    # ② 자료가 있는 기간(2026년 8월 첫 주)으로 한 번 더 보낸다
    run_once("august_response", "S03002", "20260801000000", "20260808000000")
