# normals.py — 날씨의 "평년 범위"를 계산하는 파일 (5차 "최근 자료" 탭)
# 평년 범위 = 지난 10년 동안 같은 날짜 앞뒤 7일의 값으로 구한 평균 ± 표준편차
# 실행: .venv\Scripts\python.exe normals.py
import datetime as dt

import pandas as pd

import api
import config
import weather


def load_past_years(stn):
    """관측 지점 한 곳의 지난 10년 날씨 표. (요청 한 번)"""
    first = f"{config.NORMAL_FIRST_YEAR}0101"
    last = f"{config.NORMAL_LAST_YEAR}1231"
    return weather.load_weather(stn, first, last)


def same_season(past, day):
    """지난 해마다 'day와 같은 날짜 앞뒤 며칠'에 들어가는 줄만 골라 돌려준다."""
    half = dt.timedelta(days=config.NORMAL_HALF_WINDOW)
    chosen = pd.Series(False, index=past.index)
    for year in range(config.NORMAL_FIRST_YEAR, config.NORMAL_LAST_YEAR + 1):
        month, date = (2, 28) if (day.month, day.day) == (2, 29) else (day.month, day.day)
        center = pd.Timestamp(year, month, date)  # 그해의 '같은 날짜'
        chosen |= (past["날짜"] >= center - half) & (past["날짜"] <= center + half)
    return past[chosen]


def normal_range(past, day, item):
    """그날의 평년 범위: (평균, 표준편차, 쓴 값의 개수)."""
    values = same_season(past, day)[item].dropna()
    return float(values.mean()), float(values.std()), len(values)


def normal_table(past, days, item):
    """여러 날의 평년 범위를 표로 만든다. (그래프에 띠를 그릴 때 쓴다)"""
    rows = []
    for day in days:
        mean, sd, count = normal_range(past, day, item)
        rows.append({"날짜": pd.Timestamp(day), "평균": mean, "아래": mean - sd,
                     "위": mean + sd, "개수": count})
    return pd.DataFrame(rows)


def end_streak(recent, band, item):
    """마지막 날부터 거꾸로 세어, 평년 범위보다 '높음/낮음'이 며칠째 이어지는지.
    돌려주는 것: ("높음" / "낮음" / "안", 이어진 날 수). 값이 빈 날을 만나면 멈춘다."""
    joined = recent.merge(band, on="날짜")
    where = []
    for value, low, high in zip(joined[item], joined["아래"], joined["위"]):
        where.append(None if pd.isna(value) else
                     "높음" if value > high else "낮음" if value < low else "안")
    if not where or where[-1] is None:
        return None, 0
    count = 0
    for state in reversed(where):  # 마지막 날부터 거꾸로
        if state != where[-1]:
            break
        count += 1
    return where[-1], count


def rain_days(table):
    """비가 기록된 날 수와 비의 합. 비 값이 빈 날(-9)은 비가 안 온 날로 본다(확인 전)."""
    rain = table["비"].fillna(0)
    return int((rain > 0).sum()), float(rain.sum())


def dry_streak(table):
    """마지막 날부터 거꾸로, 비가 기록되지 않은 날이 며칠째인지."""
    count = 0
    for value in reversed(list(table["비"].fillna(0))):
        if value > 0:
            break
        count += 1
    return count


def rain_normal(past, first_day, last_day):
    """지난 10년 동안 같은 날짜 구간(first_day~last_day)의 '비 온 날 수'와 '비의 합'을 해마다 구해
    평균을 돌려준다: (비 온 날 수 평균, 비의 합 평균, 비의 합 표준편차)"""
    counts, totals = [], []
    for year in range(config.NORMAL_FIRST_YEAR, config.NORMAL_LAST_YEAR + 1):
        shift = pd.DateOffset(years=year - last_day.year)  # 그해의 같은 날짜로 옮긴다
        start, end = pd.Timestamp(first_day) + shift, pd.Timestamp(last_day) + shift
        part = past[(past["날짜"] >= start) & (past["날짜"] <= end)]
        count, total = rain_days(part)
        counts.append(count)
        totals.append(total)
    totals = pd.Series(totals)
    return float(pd.Series(counts).mean()), float(totals.mean()), float(totals.std())


if __name__ == "__main__":
    # 네 관측 지점의 "11월 14일 기온·햇빛 시간" 평년 범위를 계산해 저장한다
    day = dt.date(2026, 11, 14)
    lines = []
    for name, stn in config.WEATHER_STATIONS.items():
        past = load_past_years(stn)
        for item in ["기온", "햇빛 시간"]:
            mean, sd, count = normal_range(past, day, item)
            lines.append({"지점": name, "번호": stn, "항목": item, "날짜": "11/14",
                          "평균": mean, "표준편차": sd, "아래": mean - sd, "위": mean + sd, "개수": count})
    table = pd.DataFrame(lines)
    print(table.to_string(index=False, float_format="%.2f"))
    table.to_csv(api.SAMPLES_FOLDER / "weather_normals.csv", index=False,
                 encoding="utf-8-sig", float_format="%.2f")
