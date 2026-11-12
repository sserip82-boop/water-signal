# sept_check.py — 새로 공개된 9월 자료로 주황 규칙을 점검하는 파일
# 실행: .venv\Scripts\python.exe sept_check.py
# 9월 자료는 규칙을 만들 때 한 번도 보지 않았다. 규칙과 숫자는 고치지 않고 그대로 돌린다.
import analysis
import api
import config
import past_check

STATION = "양산"
FIRST_DAY, LAST_DAY = "20260601", "20260930"  # 앞의 흐름이 필요해서 6월부터 받는다
CHECK_FROM = "2026-09-01"                      # 점검하는 달의 첫날


def lit_before(daily, day, color):
    """그날 앞 7일 안에 그 색 신호가 켜진 날짜들을 돌려준다."""
    days_ago = (day - daily["날짜"]).dt.days
    near = daily[(days_ago >= 1) & (days_ago <= past_check.LOOK_BACK) & (daily["신호"] == color)]
    return list(near["날짜"].dt.strftime("%m/%d"))


def days_left(daily, day):
    """그날 뒤로 자료가 며칠 더 있는가? (7일보다 적으면 끝까지 지켜보지 못한 것)"""
    return int((daily["날짜"].max() - day).days)


if __name__ == "__main__":
    raw = api.load_period(config.STATIONS[STATION], FIRST_DAY, LAST_DAY)
    daily = analysis.signals_by_day(analysis.make_table(raw))
    month = daily[daily["날짜"] >= CHECK_FROM]
    print("9월에 자료가 있는 날:", len(month), "일 /",
          f"{month['날짜'].min():%m/%d} ~ {month['날짜'].max():%m/%d}")
    print(month["신호"].value_counts().to_string())
    print(f"9월 DO 가장 낮은 날: {month['DO'].min():.2f} / 가장 높은 날: {month['DO'].max():.2f}")
    for color in ["노랑", "주황"]:
        for _, row in month[month["신호"] == color].iterrows():
            after = "있음" if past_check.red_after(daily, row["날짜"]) else "없음"
            print(f"{color} {row['날짜']:%m/%d} DO {row['DO']:.2f} → 뒤 7일 안에 빨강: {after}"
                  f" (뒤에 남은 자료 {days_left(daily, row['날짜'])}일)")
    for _, row in past_check.red_starts(month).iterrows():
        print(f"빨강 시작 {row['날짜']:%m/%d} DO {row['DO']:.2f}",
              "← 앞 7일 안의 주황:", lit_before(daily, row["날짜"], "주황") or "없음",
              "/ 노랑:", lit_before(daily, row["날짜"], "노랑") or "없음")
    month.drop(columns=["이유"]).to_csv(api.SAMPLES_FOLDER / "sept_check.csv", index=False,
                                      encoding="utf-8-sig", float_format="%.2f")
