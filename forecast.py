# forecast.py — 기상청 단기·중기 예보를 불러 "날짜마다 한 줄" 표로 만드는 파일 (5차 R3)
# 우리가 맞히는 것이 아니라, 기상청이 발표한 예보를 옮겨 오는 것이다.
# 칸 순서는 samples/forecast_*.txt의 실제 응답으로 확인했다. (CLAUDE.md "기상청 예보")
# 실행: .venv\Scripts\python.exe forecast.py
import pandas as pd

import config
import weather

EMPTY = [-99, -999]  # 값 없음 표시


def data_lines(text):
    """'#'으로 시작하지 않는 줄(자료 줄)만 돌려준다."""
    return [line for line in text.splitlines() if line.strip() and not line.startswith("#")]


def short_rows(reg):
    """단기 육상예보: 12시간마다 (발효시각, 기온, 강수확률, 예보 글)."""
    text = weather.request_weather("fct_afs_dl.php", {"reg": reg, "disp": "0", "help": "0"})
    rows = []
    for line in data_lines(text):
        parts = line.split(maxsplit=16)  # 앞 16칸은 빈칸으로 나뉘고, 17번째(예보 글)는 띄어쓰기를 품는다
        rows.append({"시각": pd.to_datetime(parts[2], format="%Y%m%d%H%M"),
                     "기온": float(parts[12]), "강수확률": float(parts[13]),
                     "하늘": parts[16].strip('"')})
    return pd.DataFrame(rows).replace(EMPTY, float("nan"))


def short_days(reg):
    """단기예보를 날짜마다 한 줄로: 0시 칸 기온 → 아침 최저, 12시 칸 기온 → 낮 최고 (확인 전)."""
    rows = short_rows(reg)
    rows["날짜"] = rows["시각"].dt.normalize()
    morning = rows[rows["시각"].dt.hour == 0].set_index("날짜")
    noon = rows[rows["시각"].dt.hour == 12].set_index("날짜")
    days = pd.DataFrame({"최저": morning["기온"], "최고": noon["기온"]})
    days["강수확률"] = rows.groupby("날짜")["강수확률"].max()
    days["하늘"] = noon["하늘"].reindex(days.index).fillna(morning["하늘"])
    return days


def mid_temp_days(reg):
    """중기 기온: 날짜마다 아침 최저·낮 최고. (실제 자료 줄은 12칸)"""
    text = weather.request_weather("fct_afs_wc.php", {"reg": reg, "disp": "0", "help": "0"})
    rows = []
    for line in data_lines(text):
        parts = line.split()
        rows.append({"날짜": pd.to_datetime(parts[2][:8], format="%Y%m%d"),
                     "최저": float(parts[6]), "최고": float(parts[7])})
    return pd.DataFrame(rows).set_index("날짜").replace(EMPTY, float("nan"))


def mid_land_days():
    """중기 육상예보(넓은 구역): 날짜마다 강수확률(가장 높은 값)과 예보 글."""
    text = weather.request_weather("fct_afs_wl.php", {"reg": config.FORECAST_WIDE_REGION,
                                                      "disp": "0", "help": "0"})
    rows = []
    for line in data_lines(text):
        head, rest = line.split(maxsplit=9)[:9], line.split(maxsplit=9)[9]
        sky, chance = rest.rsplit(maxsplit=1)  # 예보 글은 띄어쓰기를 품고, 마지막 칸이 강수확률
        rows.append({"날짜": pd.to_datetime(head[2][:8], format="%Y%m%d"),
                     "강수확률": float(chance), "하늘": sky.strip('"')})
    table = pd.DataFrame(rows)
    return table.groupby("날짜").agg({"강수확률": "max", "하늘": "last"})


def forecast_days(place):
    """한 지역의 앞으로 며칠 예보 표. 단기와 중기가 겹치는 날은 단기를 쓴다."""
    reg = config.FORECAST_REGIONS[place]
    short = short_days(reg)
    short["출처"] = "단기"
    mid = mid_temp_days(reg).join(mid_land_days(), how="left")
    mid["출처"] = "중기"
    mid = mid[~mid.index.isin(short.index)]  # 단기에 있는 날은 빼고
    days = pd.concat([short, mid]).sort_index()
    return days.rename_axis("날짜").reset_index()


if __name__ == "__main__":
    print(forecast_days("양산").to_string(index=False))
