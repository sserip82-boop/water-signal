# past_check.py — 지난여름 자료에 신호 규칙을 돌려 보는 파일 (규칙 점검)
# 실행: .venv\Scripts\python.exe past_check.py
import plotly.graph_objects as go

import analysis
import api
import config

STATION = "양산"
FIRST_DAY, LAST_DAY = "20260601", "20260831"  # 9월 이후 자료는 아직 없다
LOOK_BACK = 7  # 빨강이 시작되기 전 며칠 안에 노랑이 있었는지 볼까
COLORS = {"초록": "green", "노랑": "gold", "주황": "darkorange","빨강": "red", "회색": "gray"}


def red_starts(daily):
    """빨강이 '새로 시작된 날'만 고른다. (전날은 빨강이 아니었던 날)"""
    is_red = daily["신호"] == "빨강"
    return daily[is_red & ~is_red.shift(1, fill_value=False)]


def yellow_before(daily, day):
    """그날 앞 LOOK_BACK일 안에 노랑이 켜진 날짜들을 돌려준다."""
    days_ago = (day - daily["날짜"]).dt.days
    near = daily[(days_ago >= 1) & (days_ago <= LOOK_BACK) & (daily["신호"] == "노랑")]
    return list(near["날짜"].dt.strftime("%m/%d"))


def red_after(daily, day):
    """그날 뒤 LOOK_BACK일 안에 빨강이 켜진 적이 있는가?"""
    days_later = (daily["날짜"] - day).dt.days
    near = daily[(days_later >= 1) & (days_later <= LOOK_BACK)]
    return bool((near["신호"] == "빨강").any())


def draw(daily, path):
    """DO와 수온 그래프를 그리고, 신호 색으로 점을 찍어 HTML 파일로 저장한다."""
    fig = go.Figure()
    fig.add_scatter(x=daily["날짜"], y=daily["수온"], name="수온(℃)",
                    line=dict(color="lightgray"), yaxis="y2")
    fig.add_scatter(x=daily["날짜"], y=daily["DO"], name="용존산소(DO)",
                    mode="lines+markers", line=dict(color="steelblue"),
                    marker=dict(color=daily["신호"].map(COLORS), size=9))
    fig.add_hline(y=config.DO_RED_LIMIT, line_dash="dash", line_color="red",
                  annotation_text=f"빨강 기준 {config.DO_RED_LIMIT} (임시값)")
    fig.update_layout(title=f"{STATION} 2026년 6~8월 (점 색 = 그날의 신호, 참고용)",
                      yaxis=dict(title="DO"),
                      yaxis2=dict(title="수온(℃)", overlaying="y", side="right"))
    fig.write_html(path, include_plotlyjs="cdn")


if __name__ == "__main__":
    raw = api.load_period(config.STATIONS[STATION], FIRST_DAY, LAST_DAY)
    daily = analysis.signals_by_day(analysis.make_table(raw))
    print("자료가 있는 날:", len(daily), "일")
    print(daily["신호"].value_counts().to_string())
    for color in ["노랑", "빨강", "회색"]:
        days = daily[daily["신호"] == color]["날짜"].dt.strftime("%m/%d")
        print(f"{color} {len(days)}일:", ", ".join(days))
    for _, row in red_starts(daily).iterrows():
        print("빨강 시작", row["날짜"].strftime("%m/%d"),
              f"DO {row['DO']:.2f} / 앞 {LOOK_BACK}일 안의 노랑:",
              yellow_before(daily, row["날짜"]) or "없음")
    for _, row in daily[daily["신호"] == "노랑"].iterrows():
        print("노랑", row["날짜"].strftime("%m/%d"),
              f"→ 뒤 {LOOK_BACK}일 안에 빨강:", "있음" if red_after(daily, row["날짜"]) else "없음")
    draw(daily, api.SAMPLES_FOLDER / "past_check.html")
    daily.drop(columns=["이유"]).to_csv(api.SAMPLES_FOLDER / "past_check.csv",
                                      index=False, encoding="utf-8-sig", float_format="%.2f")
