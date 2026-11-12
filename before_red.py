# before_red.py — 빨강이 시작되기 전 3일 동안 다른 항목들이 평소와 달랐는지 보는 파일
# 실행: .venv\Scripts\python.exe before_red.py   (먼저 station_survey.py를 한 번 실행해야 한다)
import contextlib
import io

import pandas as pd

import analysis
import api
import config
import station_survey

DAYS_BEFORE = 3  # 빨강이 시작되기 전 며칠을 볼까
ITEMS = ["DO", "수온", "pH", "전기전도도", "탁도", "총유기탄소"]


def station_table(raw, site_id):
    """측정소 한 곳의 신호가 붙은 표. (make_table이 출력하는 글은 숨긴다)"""
    with contextlib.redirect_stdout(io.StringIO()):
        return analysis.signals_by_day(analysis.make_table(raw[raw["SITE_ID"] == site_id]))


def before_days(daily, day):
    """빨강이 시작된 날의 앞 DAYS_BEFORE일 줄들."""
    days_ago = (day - daily["날짜"]).dt.days
    return daily[(days_ago >= 1) & (days_ago <= DAYS_BEFORE)]


def compare(name, daily):
    """빨강 시작마다: 앞 3일 평균이 그 측정소의 가운데 값(중앙값)보다 높은가 낮은가."""
    lines = []
    for day in analysis.red_starts(daily):
        before = before_days(daily, day)
        line = {"측정소": name, "빨강 시작": day.strftime("%m/%d")}
        for item in ITEMS:
            usual, mean = daily[item].median(), before[item].mean()
            line[item] = "없음" if pd.isna(mean) else ("높음" if mean > usual else "낮음")
            line[item + " 앞3일"], line[item + " 평소"] = mean, usual
        lines.append(line)
    return lines


if __name__ == "__main__":
    raw = station_survey.load_all_sites()
    lines = []
    for name, site_id in config.STATIONS.items():
        lines += compare(name, station_table(raw, site_id))
    table = pd.DataFrame(lines)
    print(table[["측정소", "빨강 시작"] + ITEMS].to_string(index=False))
    print("\n빨강 시작", len(table), "번 중 '앞 3일 평균이 평소보다 높았던' 횟수")
    for item in ITEMS:
        have = table[table[item] != "없음"]
        print(f"  {item}: {int((have[item] == '높음').sum())}번 / 값이 있던 {len(have)}번")
    table.to_csv(api.SAMPLES_FOLDER / "before_red.csv", index=False,
                 encoding="utf-8-sig", float_format="%.2f")
