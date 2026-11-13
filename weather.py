# weather.py — 기상청 API허브에 "날씨 자료 주세요" 하고 요청을 보내는 파일
# 실행: .venv\Scripts\python.exe weather.py
import tomllib

import pandas as pd
import requests

import api
import config

# 기상청 API허브의 주소 (실제 응답을 받아 확인한 것만 여기에 적는다)
KMA_URL = "https://apihub.kma.go.kr/api/typ01/url"


def read_kma_key():
    """secrets.toml에서 기상청 인증키를 꺼낸다. (화면에 출력하지 않는다!)"""
    if api.SECRETS_FILE.exists():
        with open(api.SECRETS_FILE, "rb") as f:
            return tomllib.load(f)["KMA_API_KEY"]
    import streamlit as st
    return st.secrets["KMA_API_KEY"]


def request_weather(page, params):
    """기상청에 요청을 보내고 응답 글(text)을 돌려준다. 실패하면 오류를 낸다."""
    params = dict(params, authKey=read_kma_key())
    try:
        response = requests.get(f"{KMA_URL}/{page}", params=params, timeout=30)
    except requests.RequestException:  # 오류 내용에 인증키가 섞일 수 있어 그대로 보여 주지 않는다
        raise RuntimeError("기상청에 연결하지 못했어요.") from None
    response.encoding = response.apparent_encoding  # 한글이 깨지지 않게 글자 방식을 맞춘다
    if response.status_code != 200:
        raise RuntimeError(f"기상청 오류: HTTP {response.status_code} / {response.text[:200]}")
    return response.text


def save_sample(text, name):
    """응답 글을 samples 폴더에 저장한다. (응답에는 인증키가 들어 있지 않다)"""
    path = api.SAMPLES_FOLDER / f"{name}.txt"
    path.write_text(text, encoding="utf-8")
    print("저장:", path.name, "/", len(text.splitlines()), "줄")


def parse_weather(text):
    """응답 글 → (날짜, 기온, 햇빛 시간, 비) 표. '#'으로 시작하는 줄은 설명이라 건너뛴다."""
    rows = []
    for line in text.splitlines():
        parts = line.split()  # 기간 조회는 칸이 빈칸으로 나뉘어 온다
        if line.startswith("#") or len(parts) < max(config.WEATHER_PLACES.values()):
            continue
        row = {"날짜": pd.to_datetime(parts[0], format="%Y%m%d")}
        for name, place in config.WEATHER_PLACES.items():
            row[name] = float(parts[place - 1])  # 3번째 칸은 parts[2]에 있다
        rows.append(row)
    table = pd.DataFrame(rows, columns=["날짜"] + list(config.WEATHER_PLACES))
    return table.replace(config.WEATHER_EMPTY, float("nan"))  # 값 없음 표시는 빈 값으로


def load_weather(stn, first_day, last_day):
    """지점 한 곳의 first_day~last_day('20260801' 꼴) 날씨 표. 두 날 모두 포함해서 온다."""
    text = request_weather("kma_sfcdd3.php", {"tm1": first_day, "tm2": last_day,
                                              "stn": stn, "help": "0"})
    return parse_weather(text)


if __name__ == "__main__":
    # ① 종관기상관측(ASOS) 일자료: 하루 치, 모든 지점, 항목 설명(help=1) 포함
    text = request_weather("kma_sfcdd.php", {"tm": "20260815", "stn": "0", "help": "1"})
    save_sample(text, "weather_asos_day")
    # ② 기간으로 한 번에 받는 주소(kma_sfcdd3.php)는 2026-11-13에 불러 보니
    #    처음엔 "활용신청이 필요한 API"(HTTP 403)였고, 신청한 뒤에 받을 수 있었다.
    text = request_weather("kma_sfcdd3.php", {"tm1": "20260801", "tm2": "20260803",
                                              "stn": "159", "help": "1"})
    save_sample(text, "weather_asos_period")
    print(load_weather("159", "20260814", "20260816").to_string(index=False))
