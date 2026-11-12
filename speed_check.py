# speed_check.py — 속도 규칙 A·B를 지난여름 자료로 점검하는 파일
# 실행: .venv\Scripts\python.exe speed_check.py
# 순서: ① 6~7월 자료로 기준 숫자를 계산한다 → config.py에 적는다
#       ② 보지 않은 8월 자료에 규칙을 돌려 본다
import analysis
import api
import config
import past_check

STATION = "양산"
TOP_SHARE = 0.10          # 크게 떨어진 순서로 위에서 몇 %를 "빠른 하락"으로 볼까 (10%)
TRAIN_LAST_DAY = "2026-07-31"  # 이날까지(6~7월)로 숫자를 정하고, 그 뒤(8월)로 점검한다


def add_speed(daily):
    """날마다 '그날까지의 자료만 보고' 속도와 규칙 B를 계산해 표에 붙인다."""
    result = daily.copy()
    parts = [daily.iloc[: i + 1] for i in range(len(daily))]  # 그날까지만 자른 표들
    result["변화"] = [analysis.do_change(part) for part in parts]
    result["규칙B"] = [analysis.is_speeding_up(part) for part in parts]
    return result


def find_limit(train):
    """DO가 떨어진 날들의 하락폭 중 위에서 TOP_SHARE(10%)에 드는 경계값을 구한다."""
    drops = -train["변화"][train["변화"] < 0]  # 떨어진 날만, 떨어진 양(양수)으로
    print(f"6~7월에 DO가 떨어진 날: {len(drops)}일")
    return round(float(drops.quantile(1 - TOP_SHARE)), 2)


def lit_before(daily, day, rule):
    """그날 앞 7일 안에 그 규칙이 켜진 날짜들. (이미 빨강인 날은 뺀다)"""
    days_ago = (day - daily["날짜"]).dt.days
    near = daily[(days_ago >= 1) & (days_ago <= past_check.LOOK_BACK)
                 & daily[rule] & (daily["신호"] != "빨강")]
    return list(near["날짜"].dt.strftime("%m/%d"))


def report(daily, test, rule):
    """8월 자료에서 규칙 하나의 성적을 출력한다."""
    lit = test[test[rule] & (test["신호"] != "빨강")]  # 빨강이 아닌데 켜진 날
    print(f"\n[{rule}] 8월에 켜진 날(빨강인 날 제외): {len(lit)}일")
    for _, row in lit.iterrows():
        after = "있음" if past_check.red_after(daily, row["날짜"]) else "없음"
        print(f"  {row['날짜']:%m/%d} DO {row['DO']:.2f} (변화 {row['변화']:+.2f})"
              f" → 뒤 7일 안에 빨강: {after}")
    for _, row in past_check.red_starts(test).iterrows():
        print(f"  빨강 시작 {row['날짜']:%m/%d} ← 앞 7일 안에 켜진 날:",
              lit_before(daily, row["날짜"], rule) or "없음")


if __name__ == "__main__":
    raw = api.load_period(config.STATIONS[STATION], past_check.FIRST_DAY, past_check.LAST_DAY)
    daily = add_speed(analysis.signals_by_day(analysis.make_table(raw)))
    train = daily[daily["날짜"] <= TRAIN_LAST_DAY]  # 6~7월
    test = daily[daily["날짜"] > TRAIN_LAST_DAY]    # 8월
    print("① 6~7월로 계산한 기준 숫자:", find_limit(train))
    if config.FAST_DROP_LIMIT is None:
        raise SystemExit("config.py의 FAST_DROP_LIMIT에 위 숫자를 적고 다시 실행하세요.")
    print("② config.py에 적힌 기준 숫자:", config.FAST_DROP_LIMIT, "→ 8월 자료로 점검")
    daily["규칙A"] = (-daily["변화"]) >= config.FAST_DROP_LIMIT  # 변화가 없으면 False
    test = daily[daily["날짜"] > TRAIN_LAST_DAY]
    for rule in ["규칙A", "규칙B"]:
        report(daily, test, rule)
    columns = ["날짜", "DO", "수온", "변화", "신호", "규칙A", "규칙B"]
    daily[columns].to_csv(api.SAMPLES_FOLDER / "speed_check.csv", index=False,
                          encoding="utf-8-sig", float_format="%.2f")
