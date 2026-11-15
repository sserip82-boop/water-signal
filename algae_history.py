# algae_history.py — 🔬 탐구 탭: 2020년부터의 녹조 측정으로 "남조류와 DO" 살펴보기 (6차 T1단계)
# 실행: .venv\Scripts\python.exe algae_history.py   (자료를 새로 받아 samples/에 저장하고 결과를 출력한다)
# 앱은 매번 받지 않고, 여기서 저장해 둔 파일을 읽는다. (요청이 160번 넘게 필요해서 느리기 때문)
import datetime as dt

import pandas as pd

import algae
import api
import config


def history_file(site):
    return api.SAMPLES_FOLDER / f"algae_history_{site}.csv"


def download_history(site, today):
    """HISTORY_FIRST 달부터 이번 달까지 받아 CSV로 저장한다. 첫 줄에 받은 날을 적는다."""
    year, month = config.HISTORY_FIRST
    months = (today.year - year) * 12 + today.month - month + 1
    table = algae.load_algae(site, today, months)
    path = history_file(site)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(f"# 받은 날: {today:%Y-%m-%d} / 국립환경과학원 조류경보제 조회서비스 / 지점 {site}\n")
        table.to_csv(f, index=False)
    return table


def load_history(site):
    """저장해 둔 표와 받은 날('2026-11-15')을 돌려준다."""
    path = history_file(site)
    first_line = path.read_text(encoding="utf-8-sig").splitlines()[0]
    got = first_line.split("받은 날: ")[1][:10]
    table = pd.read_csv(path, comment="#", parse_dates=["날짜"], encoding="utf-8-sig")
    table["계절"] = table["날짜"].dt.month.map(config.SEASONS)
    return table, got


def many_vs_few(table, months=None):
    """남조류가 많은 날과 적은 날의 DO 평균을 견준다. months를 주면 그 달들만.
    돌려주는 것: {"많은 날": (DO 평균, 횟수), "적은 날": (DO 평균, 횟수), "뺀 측정": 빈 값이라 뺀 횟수}"""
    if months:
        table = table[table["날짜"].dt.month.isin(months)]
    usable = table.dropna(subset=["남조류", "DO"])
    many = usable[usable["남조류"] >= config.ALGAE_MANY]["DO"]
    few = usable[usable["남조류"] < config.ALGAE_MANY]["DO"]
    return {"많은 날": (many.mean(), len(many)), "적은 날": (few.mean(), len(few)),
            "뺀 측정": len(table) - len(usable)}


def drop_events(table):
    """③ 바로 앞 측정의 남조류가 ALGAE_MANY 이상이고, 이번에 DROP_RATIO 배 이하로 줄어든 때.
    두 측정 사이가 DROP_GAP_DAYS일 이하일 때만 본다. 돌려주는 것: 사건 표(날짜순)"""
    usable = table.dropna(subset=["남조류", "DO"]).sort_values("날짜").reset_index(drop=True)
    before = usable.shift(1)  # 바로 앞 측정 줄
    gap = (usable["날짜"] - before["날짜"]).dt.days
    found = ((before["남조류"] >= config.ALGAE_MANY)
             & (usable["남조류"] <= before["남조류"] * config.DROP_RATIO)
             & (gap <= config.DROP_GAP_DAYS))
    return pd.DataFrame({
        "앞 측정": before["날짜"][found], "이번 측정": usable["날짜"][found], "사이(일)": gap[found],
        "남조류 앞": before["남조류"][found], "남조류 이번": usable["남조류"][found],
        "DO 앞": before["DO"][found], "DO 이번": usable["DO"][found],
        "DO 변화": (usable["DO"] - before["DO"])[found].round(2),
        "수온 변화": (usable["수온"] - before["수온"])[found].round(1),
    }).reset_index(drop=True)


if __name__ == "__main__":
    today = dt.date.today()
    for name, site in config.ALGAE_SITES.items():
        download_history(site, today)
        table, got = load_history(site)
        print(f"== {name} ({site}) {len(table)}번, {table['날짜'].min():%Y-%m-%d} ~ {table['날짜'].max():%Y-%m-%d}, 받은 날 {got}")
        for label, months in [("① 한 해 전체", None), ("② 7~9월", config.SUMMER_MONTHS)]:
            r = many_vs_few(table, months)
            print(f"  {label}: 많은 날 DO {r['많은 날'][0]:.2f} ({r['많은 날'][1]}번) / "
                  f"적은 날 {r['적은 날'][0]:.2f} ({r['적은 날'][1]}번) / 뺀 측정 {r['뺀 측정']}")
        events = drop_events(table)
        down = (events["DO 변화"] < 0).sum()
        print(f"  ③ 갑자기 줄어든 때 {len(events)}번, DO 내려감 {down}번, DO 변화 평균 {events['DO 변화'].mean():.2f}")
