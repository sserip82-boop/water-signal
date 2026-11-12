# station_survey.py — 낙동강 측정소마다 자료가 얼마나 차 있는지 조사하는 파일
# 실행: .venv\Scripts\python.exe station_survey.py
import pandas as pd

import analysis
import api
import config

FIRST_DAY, LAST_DAY = "20260601", "20260930"  # 6~9월 (122일)
RIVER_PREFIX = "S02"  # 낙동강 측정소 코드는 S02로 시작한다
ITEMS = {  # 조사할 항목 → 살펴볼 칸들
    "DO": config.DO_COLUMNS, "수온": config.TEMP_COLUMNS, "pH": config.PH_COLUMNS,
    "전기전도도": config.COND_COLUMNS, "탁도": config.TURB_COLUMNS,
    "총유기탄소": config.TOC_COLUMNS,
}


def load_all_sites():
    """모든 측정소의 6~9월 자료를 한 번에 받는다. (받아 둔 게 있으면 재사용)"""
    cache = api.DATA_FOLDER / f"ALL_{FIRST_DAY}_{LAST_DAY}.csv"
    if cache.exists():
        return pd.read_csv(cache, low_memory=False)
    start = api.day_before(FIRST_DAY) + "000000"
    # 측정소 번호를 비우면(None) 모든 측정소 자료가 온다
    rows = api.fetch_all_pages(None, start, LAST_DAY + "000000", num_of_rows=1000)
    table = pd.DataFrame(rows)
    api.DATA_FOLDER.mkdir(exist_ok=True)
    table.to_csv(cache, index=False, encoding="utf-8-sig")
    return table


def survey_one(site_rows):
    """측정소 한 곳: 항목마다 값이 있는 날 수, 빨강인 날 수, 가장 낮은 DO."""
    result = {}
    for name, columns in ITEMS.items():
        numbers, _, _ = analysis.clean_numbers(site_rows, columns)
        values = analysis.first_filled(numbers)
        result[name] = int(values.notna().sum())
        if name == "DO":
            result["빨강인 날"] = int((values < config.DO_RED_LIMIT).sum())
            result["DO 최저"] = values.min()
    return result


if __name__ == "__main__":
    raw = load_all_sites()
    river = raw[raw["SITE_ID"].str.startswith(RIVER_PREFIX)]
    print("전체 측정소:", raw["SITE_ID"].nunique(), "곳 / 낙동강:", river["SITE_ID"].nunique(), "곳")
    lines = []
    for (site_id, name), site_rows in river.groupby(["SITE_ID", "SITE_NAME"]):
        lines.append({"코드": site_id, "이름": name, "받은 날": len(site_rows),
                      **survey_one(site_rows)})
    table = pd.DataFrame(lines).sort_values("DO", ascending=False)
    print(table.to_string(index=False, float_format="%.2f"))
    table.to_csv(api.SAMPLES_FOLDER / "station_survey.csv", index=False,
                 encoding="utf-8-sig", float_format="%.2f")
