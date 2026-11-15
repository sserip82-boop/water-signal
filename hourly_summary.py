# hourly_summary.py — 국가수질자동측정망 시간자료(zip)에서 하루 요약표(평균·최저·최고)를 만든다 (6차 V1단계)
# 실행: .venv\Scripts\python.exe hourly_summary.py <zip들이 있는 폴더>
#   zip 이름은 hourly_2022.zip … hourly_2025.zip (물환경정보시스템 → 자동측정망 → 파일셋 다운로드에서 받음)
# zip은 너무 커서 깃에 올리지 않는다. 여기서 만든 하루 요약표만 samples/에 저장한다.
# 엑셀은 새 라이브러리 없이 파이썬 기본 도구(zipfile, xml)로 읽는다.
import datetime as dt
import io
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

import api
import config

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def excel_rows(data):
    """엑셀 파일(바이트)의 첫 시트를 줄(글자 목록)로 하나씩 돌려준다."""
    book = zipfile.ZipFile(io.BytesIO(data))
    shared = []
    if "xl/sharedStrings.xml" in book.namelist():
        for item in ET.fromstring(book.read("xl/sharedStrings.xml")).iter(NS + "si"):
            shared.append("".join(t.text or "" for t in item.iter(NS + "t")))
    for row in ET.fromstring(book.read("xl/worksheets/sheet1.xml")).iter(NS + "row"):
        cells = []
        for cell in row.findall(NS + "c"):
            place = column_number(cell.get("r", ""))  # 빈 칸은 엑셀에서 빠져 있을 수 있어 칸 이름(A1, C1…)으로 자리를 찾는다
            while place is not None and len(cells) < place:
                cells.append("")
            cells.append(cell_text(cell, shared))
        yield cells


def column_number(ref):
    """'C12' → 2 (A=0). 칸 이름이 없으면 None."""
    letters = re.match(r"[A-Z]+", ref)
    if not letters:
        return None
    number = 0
    for letter in letters.group():
        number = number * 26 + ord(letter) - ord("A") + 1
    return number - 1


def cell_text(cell, shared):
    """칸 하나의 글자. 공유 글자(s), 칸 안에 바로 적힌 글자(inlineStr), 숫자를 모두 읽는다."""
    kind = cell.get("t")
    if kind == "inlineStr":
        return "".join(t.text or "" for t in cell.iter(NS + "t"))
    value = cell.find(NS + "v")
    text = value.text if value is not None else ""
    return shared[int(text)] if kind == "s" and text else (text or "")


def find_excel(year_zip, station):
    """zip 안에서 '[낙동강_<측정소>]' 엑셀을 찾아 바이트로 돌려준다. 없으면 None."""
    for info in year_zip.infolist():
        if f"낙동강_{station}]" in info.filename or f"낙동강_{station}]" in _korean(info.filename):
            return year_zip.read(info)
    return None


def _korean(name):
    """옛날 방식으로 저장된 zip 파일 이름을 한글로 바꿔 본다."""
    try:
        return name.encode("cp437").decode("cp949")
    except UnicodeError:
        return name


def hourly_do(data):
    """엑셀 → (시각, DO) 표. DO 칸은 머리글 '용존산소'로 찾는다(해마다 칸 순서가 다를 수 있어서)."""
    rows, do_place = [], None
    for cells in excel_rows(data):
        if do_place is None and any(c.startswith("용존산소") for c in cells):
            do_place = next(i for i, c in enumerate(cells) if c.startswith("용존산소"))
        elif do_place is not None and re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", cells[0] if cells else ""):
            value = cells[do_place] if len(cells) > do_place else ""
            rows.append((cells[0], pd.to_numeric(value, errors="coerce")))
    table = pd.DataFrame(rows, columns=["시각", "DO"])
    table["시각"] = pd.to_datetime(table["시각"])
    return table


def daily_summary(hourly):
    """시간 표 → 하루 요약표 (날짜, 평균, 최저, 최고, 시간 수). 값이 빈 시간은 세지 않는다."""
    hourly = hourly.dropna(subset=["DO"])
    day = hourly.groupby(hourly["시각"].dt.normalize())["DO"].agg(["mean", "min", "max", "count"])
    day = day.reset_index().rename(columns={"시각": "날짜", "mean": "평균", "min": "최저",
                                            "max": "최고", "count": "시간 수"})
    day["평균"] = day["평균"].round(3)
    return day


def summary_file(code):
    return api.SAMPLES_FOLDER / f"hourly_daily_{code}.csv"


def save_station(folder, station, code, today):
    """측정소 한 곳의 여러 해 하루 요약표를 저장한다. 돌려주는 것: 요약표"""
    parts = []
    for year in config.HOURLY_YEARS:
        data = find_excel(zipfile.ZipFile(Path(folder) / f"hourly_{year}.zip"), station)
        if data is not None:
            parts.append(daily_summary(hourly_do(data)))
    table = pd.concat(parts, ignore_index=True)
    with open(summary_file(code), "w", encoding="utf-8-sig", newline="") as f:
        f.write(f"# 만든 날: {today:%Y-%m-%d} / 물환경정보시스템 국가수질자동측정망 시간자료 "
                f"{config.HOURLY_YEARS[0]}~{config.HOURLY_YEARS[-1]}년 / 측정소 {station} {code} / 용존산소(mg/L) 하루 요약\n")
        table.to_csv(f, index=False)
    return table


EXAMPLE_FILE = api.SAMPLES_FOLDER / "hourly_example.csv"


def save_example(folder, today):
    """⑤ 예시 그래프에 쓸 두 날의 시간 값만 저장한다 (config.HOURLY_EXAMPLE)."""
    name, first, second = config.HOURLY_EXAMPLE
    _, station, code = config.HOURLY_PAIRS[name]
    parts = []
    for day in [first, second]:
        data = find_excel(zipfile.ZipFile(Path(folder) / f"hourly_{day[:4]}.zip"), station)
        hourly = hourly_do(data)
        parts.append(hourly[hourly["시각"].dt.strftime("%Y-%m-%d") == day])
    with open(EXAMPLE_FILE, "w", encoding="utf-8-sig", newline="") as f:
        f.write(f"# 만든 날: {today:%Y-%m-%d} / 물환경정보시스템 국가수질자동측정망 시간자료 / 측정소 {station} {code} / {first}, {second}\n")
        pd.concat(parts).to_csv(f, index=False)


def load_example():
    return pd.read_csv(EXAMPLE_FILE, comment="#", parse_dates=["시각"], encoding="utf-8-sig")


def load_summary(code):
    """저장해 둔 하루 요약표."""
    return pd.read_csv(summary_file(code), comment="#", parse_dates=["날짜"], encoding="utf-8-sig")


def event_days(events, summary):
    """사건 표의 '앞 측정일'과 '이번 측정일'에 자동측정소의 하루 최저·최고·평균을 붙인다.
    두 날 모두 HOURLY_MIN_HOURS 시간 이상 잰 사건만 남긴다. 돌려주는 것: 사건마다 변화량 표"""
    day = summary.set_index("날짜")
    day = day[day["시간 수"] >= config.HOURLY_MIN_HOURS]
    day["폭"] = day["최고"] - day["최저"]
    rows = []
    for _, e in events.iterrows():
        if e["앞 측정"] in day.index and e["이번 측정"] in day.index:
            a, b = day.loc[e["앞 측정"]], day.loc[e["이번 측정"]]
            rows.append({"앞 측정": e["앞 측정"], "이번 측정": e["이번 측정"],
                         "최저 앞": a["최저"], "최저 이번": b["최저"], "최저 변화": round(b["최저"] - a["최저"], 2),
                         "폭 앞": round(a["폭"], 2), "폭 이번": round(b["폭"], 2), "폭 변화": round(b["폭"] - a["폭"], 2),
                         "평균 변화": round(b["평균"] - a["평균"], 2)})
    return pd.DataFrame(rows, columns=["앞 측정", "이번 측정", "최저 앞", "최저 이번", "최저 변화",
                                       "폭 앞", "폭 이번", "폭 변화", "평균 변화"])


def count_changes(days):
    """{'횟수', '최저 내려감', '폭 줄어듦', '최저 변화 평균', '폭 변화 평균'}"""
    return {"횟수": len(days), "최저 내려감": int((days["최저 변화"] < 0).sum()),
            "폭 줄어듦": int((days["폭 변화"] < 0).sum()),
            "최저 변화 평균": days["최저 변화"].mean(), "폭 변화 평균": days["폭 변화"].mean()}


def pair_results():
    """⑤ 짝마다 사건·비교 집단의 하루 최저·폭 변화 횟수 표."""
    import algae_history  # 이 파일을 혼자 실행할 때도 쓰려고 여기서 부른다
    rows = []
    for algae_name, (algae_code, station, code) in config.HOURLY_PAIRS.items():
        table, _ = algae_history.load_history(algae_code)
        summary = load_summary(code)
        for group, dropped in [("사건", True), ("비교", False)]:
            days = event_days(algae_history.drop_events(table, dropped), summary)
            rows.append({"짝": f"{algae_name}↔{station}", "무리": group, **count_changes(days)})
    return pd.DataFrame(rows)


if __name__ == "__main__" and len(sys.argv) == 1:
    result = pair_results()
    print(result.round(2).to_string(index=False))
    for group in ["사건", "비교"]:
        part = result[result["무리"] == group]
        n = part["횟수"].sum()
        print(f"합계 {group}: {n}번, 최저 내려감 {part['최저 내려감'].sum()}, 폭 줄어듦 {part['폭 줄어듦'].sum()}")
    sys.exit()

if __name__ == "__main__":
    folder = sys.argv[1]
    for algae_name, (algae_code, station, code) in config.HOURLY_PAIRS.items():
        table = save_station(folder, station, code, dt.date.today())
        full = table[table["시간 수"] >= config.HOURLY_MIN_HOURS]
        print(f"{station}({code}) ↔ {algae_name}: {len(table)}일, {config.HOURLY_MIN_HOURS}시간 이상인 날 {len(full)}일, "
              f"{table['날짜'].min():%Y-%m-%d} ~ {table['날짜'].max():%Y-%m-%d}")
    save_example(folder, dt.date.today())
    example = load_example()
    print("예시:", example.groupby(example["시각"].dt.date)["DO"].agg(["min", "max", "count"]).to_dict("index"))
