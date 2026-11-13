# app.py — 화면을 만드는 파일 (실행: streamlit run app.py)
import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analysis
import api
import config
import weather

KST = dt.timezone(dt.timedelta(hours=9))  # 한국 시간
LOOK_BACK_DAYS = 180  # 가장 최근 자료를 찾으려고 며칠 전까지 살펴볼까
SHOW_DAYS = 30         # 기본으로 보여 줄 날 수 (학생이 바꿔 볼 수 있는 숫자)
# 신호 색 → (배경색, 글자색, 한마디)
LAMPS = {
    "초록": ("#2e9e4f", "white", "평소와 비슷해요"),
    "노랑": ("#f2c200", "black", "주의해서 지켜봐요"),
    "주황": ("#f57c00", "white", "산소가 점점 빨리 줄고 있어요"),
    "빨강": ("#d93025", "white", "산소가 부족해요"),
    "회색": ("#8a8a8a", "white", "자료가 없어요"),
}


@st.cache_data(ttl=6 * 3600, show_spinner="자료를 불러오는 중이에요…")
def load_table(site_id, first_day, last_day):
    """기간 자료를 받아 깔끔한 표와 불러온 시각을 돌려준다. (6시간 동안 기억)"""
    start = api.day_before(first_day) + "000000"  # API는 시작일 당일을 빼고 준다
    rows = api.fetch_all_pages(site_id, start, last_day + "000000", num_of_rows=1000)
    fetched_at = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    if not rows:
        return None, fetched_at
    return analysis.make_table(pd.DataFrame(rows)), fetched_at


def load_days(site_id, first_day, last_day):
    """표에 신호를 붙인다. 신호는 기억해 두지 않고 매번 새로 계산한다.
    (규칙을 고쳤는데 예전 신호가 계속 보이는 일을 막으려고)"""
    table, fetched_at = load_table(site_id, first_day, last_day)
    if table is None:
        return None, fetched_at
    return analysis.signals_by_day(table), fetched_at


def safe_load(site_id, first, last):
    """자료를 불러오다 실패하면, 사람이 읽을 수 있는 안내를 보여 주고 멈춘다."""
    try:
        return load_days(site_id, first.strftime("%Y%m%d"), last.strftime("%Y%m%d"))
    except Exception:  # 오류 내용에 인증키가 섞일 수 있어서 화면에 그대로 보여 주지 않는다
        st.error("자료를 불러오지 못했어요. 인터넷 연결을 확인하고 잠시 뒤 다시 열어 주세요. "
                 "계속 안 되면 공공데이터포털이 점검 중이거나 인증키 설정에 문제가 있을 수 있어요.")
        st.stop()


def show_lamp(day_row):
    """큰 신호등과 이유 한 문장을 보여 준다."""
    back, text, word = LAMPS[day_row["신호"]]
    st.markdown(
        f'<div style="background:{back};color:{text};border-radius:24px;padding:28px 16px;'
        f'text-align:center;margin:8px 0 12px 0">'
        f'<div style="font-size:3.2rem;font-weight:800;line-height:1.2">{day_row["신호"]}</div>'
        f'<div style="font-size:1.4rem;font-weight:600">{word}</div></div>',
        unsafe_allow_html=True)
    st.markdown(f"#### {day_row['날짜']:%m월 %d일} 기준: {day_row['이유']}")


def make_chart(view, column, title, color, limit=None):
    """하루에 점 하나씩 찍는 그래프를 만든다. limit이 있으면 빨강 기준선을 긋는다."""
    fig = go.Figure()
    fig.add_scatter(x=view["날짜"], y=view[column], mode="lines+markers",
                    line=dict(color=color, width=3), marker=dict(size=10),
                    hovertemplate="%{x|%m월 %d일}: %{y:.1f}<extra></extra>")
    if limit is not None:
        fig.add_hline(y=limit, line_dash="dash", line_color="#d93025",
                      annotation_text=f"빨강 기준 {limit}", annotation_font_size=14)
    fig.update_layout(title=title, height=320, showlegend=False, font=dict(size=15),
                      margin=dict(l=10, r=10, t=50, b=10))
    fig.update_xaxes(tickformat="%m/%d")
    return fig


def pick_period(latest):
    """보여 줄 기간(첫날, 마지막 날)을 고르게 한다."""
    recent = (latest - dt.timedelta(days=SHOW_DAYS - 1), latest)
    if not st.toggle("과거 날짜 돌려보기"):
        return recent
    picked = st.date_input("보고 싶은 기간", value=recent, max_value=latest,
                           min_value=dt.date(2026, 1, 1), format="YYYY-MM-DD")
    if len(picked) < 2:  # 끝 날짜를 아직 안 골랐을 때
        st.info("끝 날짜도 골라 주세요.")
        st.stop()
    return picked


def score_sentence(daily, color):
    """성적표 한 줄을 만든다. 예: '주황: 켜진 8일 중 4일은 …'"""
    card = analysis.score_card(daily, color)
    line = (f"**{color}**: 켜진 {card['켜진 날']}일 중 **{card['빨강이 뒤따름']}일**은 "
            f"뒤 {config.SCORE_DAYS}일 안에 빨강이 왔어요.")
    if card["빨강 시작"] > 0:
        line += (f" 빨강이 시작된 {card['빨강 시작']}번 중 **{card['미리 켜짐']}번**은 "
                 f"{color}이 먼저 켜졌어요.")
    if card["켜진 날"] < config.SCORE_FEW or card["빨강 시작"] < config.SCORE_FEW:
        line += " (횟수가 적어서 믿기 어려워요)"
    return line


def show_score(station, site_id):
    """고른 측정소의 지난 성적표를 보여 준다. (정해 둔 기간의 자료로 계산)"""
    daily, first, last = load_score_days(site_id)
    with st.expander("이 신호를 얼마나 믿어도 될까요? (지난 성적표)", expanded=True):
        if daily is None:
            st.write("성적표를 만들 자료가 없어요.")
            return
        st.caption(f"{station} 측정소의 {first:%Y년 %m월 %d일}~{last:%m월 %d일} 자료에 "
                   "지금 규칙을 돌려 본 결과예요. 참고용입니다.")
        if not analysis.red_starts(daily):
            st.write("이 기간에 빨강이 한 번도 없었어요. 그래서 노랑·주황이 맞았는지 알 수 없어요.")
        for color in ["노랑", "주황"]:
            st.markdown("- " + score_sentence(daily, color))


# DO 그래프에 겹쳐 볼 수 있는 항목 → 선 색 (학생이 색을 바꿔 볼 수 있다)
OVERLAY_COLORS = {
    "수온": "#f57c00",
    "pH": "#8e44ad",
    "탁도": "#8d5a3b",
    "총유기탄소": "#222222",
}
OVERLAY_OPACITY = 0.6 # 겹친 선의 진하기 (1에 가까울수록 진하다. 학생이 바꿔 볼 수 있는 숫자)


# 날씨 항목 → 선 색 (처음에는 꺼져 있고, 글자를 누르면 켜진다)
WEATHER_COLORS = {"햇빛 시간": "#e6b800", "비": "#2e9e4f", "기온": "#d93025"}
# 글자 버튼 앞에 붙이는 색 동그라미. 선 색과 같은 색이어야 한다. (파랑은 용존산소 것이라 안 쓴다)
DOTS = {"수온": "🟠", "pH": "🟣", "탁도": "🟤", "총유기탄소": "⚫",
        "햇빛 시간": "🟡", "비": "🟢", "기온": "🔴"}


@st.cache_data(ttl=6 * 3600, show_spinner="날씨 자료를 불러오는 중이에요…")
def load_weather(stn, first_day, last_day):
    """기상 관측 지점 한 곳의 날씨 표. (6시간 동안 기억)"""
    return weather.load_weather(stn, first_day, last_day)


def add_weather(view, picked, station):
    """날씨 항목을 켰으면 관측 지점을 고르게 하고, 날씨 칸을 표 옆에 붙여 돌려준다."""
    if not any(name in WEATHER_COLORS for name in picked):
        return view
    places = list(config.WEATHER_STATIONS)
    default = station if station in places else places[0]
    place = st.segmented_control("날씨를 볼 기상 관측 지점", places, default=default) or default
    note = f"날씨는 기상청 {place} 관측 지점의 값이에요. 수질 측정소와 떨어져 있을 수 있어요."
    if place not in config.WEATHER_CHECKED:
        note += " (지점 번호와 이름이 맞는지는 아직 확인하지 못했어요.)"
    st.caption(note + " 비 값이 빈 날은 비가 오지 않았거나 값이 없는 날이에요.")
    try:
        table = load_weather(config.WEATHER_STATIONS[place],
                             f"{view['날짜'].min():%Y%m%d}", f"{view['날짜'].max():%Y%m%d}")
    except Exception:  # 오류 내용에 인증키가 섞일 수 있어서 그대로 보여 주지 않는다
        st.caption("날씨 자료를 불러오지 못했어요. 잠시 뒤 다시 해 보세요.")
        return view
    return view.merge(table, on="날짜", how="left")


def add_overlay(fig, view, name, number, color):
    """DO 그래프 위에 다른 항목의 선을 하나 겹쳐 그린다.
    항목마다 숫자 크기가 달라서, 선마다 보이지 않는 자기 눈금(세로축)을 따로 쓴다."""
    fig.add_scatter(x=view["날짜"], y=view[name], name=name, yaxis=f"y{number}",
                    mode="lines+markers", marker=dict(size=6), opacity=OVERLAY_OPACITY,
                    line=dict(color=color, width=2, dash="dot"),
                    hovertemplate=name + ": %{y:.1f}<extra></extra>")
    fig.update_layout({f"yaxis{number}": dict(overlaying="y", visible=False)})


def load_score_days(site_id):
    """성적표와 평소 범위를 계산할 때 쓰는, 정해 둔 기간(6~9월)의 자료."""
    first = dt.datetime.strptime(config.SCORE_FIRST_DAY, "%Y%m%d").date()
    last = dt.datetime.strptime(config.SCORE_LAST_DAY, "%Y%m%d").date()
    daily, _ = safe_load(site_id, first, last)
    return daily, first, last


def add_usual_band(fig, mean, sd):
    """평소 범위(평균 ± 표준편차)를 연한 파란 띠로 그린다."""
    fig.add_hrect(y0=mean - sd, y1=mean + sd, fillcolor="#1f77b4", opacity=0.10,
                  line_width=0, annotation_text="평소 범위", annotation_font_size=13,
                  annotation_position="top left")


def add_lost_area(fig, view, limit):
    """빨강 기준선 아래로 내려간 부분을 연한 빨강으로 칠한다."""
    fig.add_scatter(x=view["날짜"], y=[limit] * len(view), mode="lines",
                    line=dict(width=0), hoverinfo="skip", showlegend=False)
    fig.add_scatter(x=view["날짜"], y=view["DO"].clip(upper=limit), mode="lines",
                    line=dict(width=0), fill="tonexty", fillcolor="rgba(217,48,37,0.30)",
                    hoverinfo="skip", name="잃은 산소")


def show_do_notes(view, usual):
    """그래프 아래에 평소 범위와 잃은 산소 누적을 한 줄씩 적는다."""
    mean, sd = usual if usual is not None else (None, None)
    today_do = view["DO"].iloc[-1]
    if mean is not None and pd.notna(today_do):
        where = "아래" if today_do < mean - sd else ("위" if today_do > mean + sd else "안")
        st.markdown(f"- 마지막 날 값 **{today_do:.1f}**은 평소 범위"
                    f"({mean - sd:.1f}~{mean + sd:.1f}) **{where}**예요.")
    lost = analysis.lost_oxygen(view, config.DO_RED_LIMIT)
    st.markdown(f"- 이 기간에 빨강 기준선 아래로 내려간 넓이(잃은 산소 누적): **{lost:.2f}**")
    st.caption("평소 범위 = 이 측정소의 2026년 6~9월 하루 평균 용존산소의 평균 ± 표준편차. "
               "넓이 = (기준값보다 모자란 양 × 날 수)를 사다리꼴로 더한 값. "
               "둘 다 신호 계산에는 쓰지 않는 참고용이에요.")


def show_do_chart(view, usual, station):
    """DO 그래프를 그리고, 켜 둔 항목들을 연한 색 점선으로 겹쳐 보여 준다."""
    colors = {**OVERLAY_COLORS, **WEATHER_COLORS}  # 수질 항목 + 날씨 항목
    names = list(colors)
    picked = st.pills("함께 볼 항목 (글자를 누르면 꺼지고, 다시 누르면 켜져요)",
                      names, selection_mode="multi", default=list(OVERLAY_COLORS),
                      format_func=lambda name: f"{DOTS[name]} {name}")  # 색 동그라미 + 이름
    view = add_weather(view, picked, station)
    fig = make_chart(view, "DO", "하루 평균 용존산소(DO)", "#1f77b4", config.DO_RED_LIMIT)
    fig.data[0].name = "용존산소(DO)"
    fig.data[0].hovertemplate = "용존산소: %{y:.1f}<extra></extra>"
    if usual is not None:  # 6~9월 자료가 없는 측정소는 띠를 그리지 않는다
        add_usual_band(fig, *usual)
    add_lost_area(fig, view, config.DO_RED_LIMIT)
    for number, name in enumerate(names, start=2):  # 세로축 번호는 2번부터
        if name not in picked or name not in view.columns:
            continue
        if view[name].isna().all():
            st.caption(f"{name}: 이 기간에는 자료가 없어요.")
            continue
        add_overlay(fig, view, name, number, colors[name])
    fig.update_layout(showlegend=True, hovermode="x unified",
                      legend=dict(orientation="h", y=-0.15))
    fig.update_xaxes(hoverformat="%m월 %d일")
    st.caption("왼쪽 눈금은 용존산소의 눈금이에요. 연한 점선은 오르내리는 모양을 비교하려고 "
               "각자 크기에 맞춰 늘려 그린 것이라 높이끼리는 비교할 수 없어요. "
               "정확한 값은 그래프에 마우스를 올리면 보여요.")
    st.plotly_chart(fig, width="stretch")
    show_do_notes(view, usual)


def seen_lines(station, facts, latest):
    """'본 것' 칸에 적을 문장들. 모두 자료에서 센 숫자다."""
    lines = [f"용존산소 값이 있던 날: **{facts['값 있는 날']}일** (전체 {facts['전체 일수']}일 중)"]
    low = facts["최저"]
    if low is not None:
        lines.append(f"하루 평균 용존산소가 가장 낮았던 날: "
                     f"**{low['날짜']:%m월 %d일}, {low['DO']:.1f}**")
    lit = ", ".join(f"{color} {days}일" for color, days in facts["신호"].items())
    lines.append(f"신호가 켜진 날: {lit}")
    lines.append(f"공개된 마지막 날: **{latest:%Y년 %m월 %d일}**")
    lines.append(f"{station} 측정소 한 곳에서 잰 값")
    return lines


def unknown_lines(station, facts, latest, today):
    """'아직 모르는 것' 칸에 적을 문장들."""
    lines = []
    if facts["빈 날"] > 0:
        lines.append(f"값이 비어 있던 **{facts['빈 날']}일** 동안 무슨 일이 있었는지")
    lines.append("하루 중 산소가 가장 낮았던 순간(밤·새벽)의 값. "
                 "자료가 하루에 값 하나뿐이라 볼 수 없어요.")
    if config.DO_RED_LIMIT_IS_TEMPORARY:
        lines.append(f"빨강 기준값 {config.DO_RED_LIMIT}이 맞는 기준인지 (출처 미확인)")
    lines.append(f"{latest:%m월 %d일} 뒤부터 오늘까지 **{(today - latest).days}일** 동안의 강")
    if station not in config.LOCATION_CHECKED:
        lines.append("이 측정소의 정확한 위치")
    lines.append("측정소와 측정소 사이 구간의 물")
    lines.append("다른 해·다른 계절에도 신호 규칙이 같게 통하는지. "
                 "규칙을 점검한 자료는 2026년 6~9월뿐이에요.")
    return lines


def show_known(view, station, first, last, latest, today):
    """'본 것'과 '아직 모르는 것'을 두 칸으로 나란히 보여 준다."""
    st.markdown("##### 언제 위험해질지는 확신할 수 없어도, 무엇을 봤고 무엇을 아직 모르는지는 "
                "정확히 알려 드릴 수 있어요.")
    st.caption(f"{station} 측정소, {first:%Y년 %m월 %d일}~{last:%m월 %d일} 기준이에요.")
    facts = analysis.observed(view, first, last)
    left, right = st.columns(2)
    with left:
        st.markdown("#### 👀 본 것")
        st.markdown("\n".join("- " + line for line in seen_lines(station, facts, latest)))
    with right:
        st.markdown("#### ❓ 아직 모르는 것")
        unknown = unknown_lines(station, facts, latest, today)
        st.markdown("\n".join("- " + line for line in unknown))


def show_result(view, usual, station):
    """신호등, 겹쳐 그린 그래프, 날마다의 표를 보여 준다."""
    show_lamp(view.iloc[-1])
    if config.DO_RED_LIMIT_IS_TEMPORARY:
        st.caption(f"※ 빨강 기준값 {config.DO_RED_LIMIT}은 출처를 확인하기 전의 임시값이에요.")
    show_do_chart(view, usual, station)
    with st.expander("날마다의 숫자 보기"):
        table = view[["날짜", "DO", "수온", "신호"]].copy()
        table["날짜"] = table["날짜"].dt.strftime("%m/%d")
        st.dataframe(table.round(1), hide_index=True, width="stretch")


def event_row(event):
    """사건 하나를 표의 한 줄(사람이 읽는 글자)로 바꾼다."""
    if event["되돌아온 날"] is None:
        back, speed = event["메모"], "모름"
    else:
        back = f"{event['걸린 날']}일 뒤 ({event['되돌아온 날']:%m/%d})"
        speed = f"{event['하루에 오른 양']:.2f}"
    return {"시작": f"{event['시작']:%m/%d}", "이어진 날": f"{event['이어진 날']}일",
            "가장 낮은 값": f"{event['가장 낮은 값']:.1f} ({event['가장 낮은 날']:%m/%d})",
            "잃은 산소": f"{event['잃은 산소']:.2f}", "되돌아옴": back,
            "하루에 오른 양": speed, "앞선 신호": event["앞선 신호"]}


def show_events(station, site_id):
    """빨강 사건들을 시간순으로 보여 준다. (정해 둔 기간의 자료로 계산)"""
    daily, first, last = load_score_days(site_id)
    st.markdown("##### 빨강이 왔던 때마다 얼마나 깊었고, 얼마나 갔고, 얼마나 빨리 되돌아왔을까요?")
    st.caption(f"{station} 측정소의 {first:%Y년 %m월 %d일}~{last:%m월 %d일} 자료예요. "
               f"지나간 일을 정리한 것이고, 빨강 기준값 {config.DO_RED_LIMIT}은 임시값이에요.")
    if daily is None:
        st.write("사건을 찾을 자료가 없어요.")
        return
    fig = make_chart(daily, "DO", "하루 평균 용존산소(DO)", "#1f77b4", config.DO_RED_LIMIT)
    fig.update_traces(marker=dict(size=5), line=dict(width=2))
    add_lost_area(fig, daily, config.DO_RED_LIMIT)
    st.plotly_chart(fig, width="stretch")
    events = analysis.red_events(daily)
    if not events:
        st.write("이 기간에 빨강이 한 번도 없었어요. 그래서 되돌아오는 빠르기도 볼 수 없었어요.")
        return
    st.dataframe(pd.DataFrame([event_row(e) for e in events]), hide_index=True, width="stretch")
    st.caption("되돌아옴 = 가장 낮았던 날부터, 빨강이 끝난 다음 날까지 걸린 날 수. "
               "하루에 오른 양 = 그동안 오른 용존산소 ÷ 걸린 날 수. "
               "비커 실험(6시간)에서는 산소가 다시 오르는 것을 보지 못했어요. 강 자료에서는 볼 수 있었어요. "
               f"사건이 {len(events)}번뿐이라 평균을 내거나 일반적인 규칙으로 말하기는 어려워요.")


def show_tabs(view, station, site_id, period, latest, today):
    """측정소 한 곳의 화면을 탭 세 개로 나누어 보여 준다."""
    score_daily, _, _ = load_score_days(site_id)
    usual = None if score_daily is None else analysis.usual_range(score_daily)
    tab_signal, tab_events, tab_known = st.tabs(["오늘의 신호", "사건 기록", "본 것과 모르는 것"])
    with tab_signal:
        show_result(view, usual, station)
        show_score(station, site_id)
    with tab_events:
        show_events(station, site_id)
    with tab_known:
        show_known(view, station, period[0], period[1], latest, today)


def show_station(station, today):
    """측정소 한 곳을 자세히 보여 준다. 돌려주는 것: 자료를 불러온 시각"""
    site_id = config.STATIONS[station]
    if station not in config.LOCATION_CHECKED:
        st.caption("※ 이 측정소의 정확한 위치는 아직 확인하지 못했어요. (위치 미확인)")
    # ① 최근 자료를 받아 "공개된 가장 마지막 날"을 찾는다
    recent, fetched_at = safe_load(site_id, today - dt.timedelta(days=LOOK_BACK_DAYS), today)
    if recent is None:
        st.warning(f"최근 {LOOK_BACK_DAYS}일 동안 공개된 자료가 없어요.")
        return fetched_at
    latest = recent["날짜"].max().date()
    st.caption(f"지금 공개된 자료는 {latest:%Y년 %m월 %d일}까지예요. (오늘 자료는 아직 없어요)")
    # ② 기간을 고르고, 신호 계산에 앞의 며칠이 필요하니 조금 더 넉넉히 받는다
    first, last = pick_period(latest)
    table, fetched_at = safe_load(site_id, first - dt.timedelta(days=config.YELLOW_DAYS), last)
    view = None if table is None else table[table["날짜"].dt.date >= first]
    if view is None or view.empty:
        st.warning("고른 기간에는 자료가 없어요. 다른 날짜를 골라 주세요.")
    else:
        show_tabs(view, station, site_id, (first, last), latest, today)
    return fetched_at


def lamp_card(name, table):
    """'전체' 화면에 놓는 작은 신호등 카드 하나."""
    if table is None:
        back, text, line = "#8a8a8a", "white", "자료 없음"
    else:
        day = table.iloc[-1]
        back, text, _ = LAMPS[day["신호"]]
        line = f"{day['신호']} · {day['날짜']:%m/%d}"
    st.markdown(
        f'<div style="background:{back};color:{text};border-radius:14px;padding:10px 6px;'
        f'text-align:center;margin-bottom:10px"><div style="font-size:1.2rem;font-weight:800">'
        f'{name}</div><div style="font-size:0.9rem">{line}</div></div>',
        unsafe_allow_html=True)


def all_chart(tables):
    """여덟 측정소의 DO를 한 그래프에 선 하나씩 그린다."""
    fig = go.Figure()
    for name, table in tables.items():
        if table is not None:
            fig.add_scatter(x=table["날짜"], y=table["DO"], name=name, mode="lines",
                            hovertemplate=name + ": %{y:.1f}<extra></extra>")
    fig.add_hline(y=config.DO_RED_LIMIT, line_dash="dash", line_color="#d93025",
                  annotation_text=f"빨강 기준 {config.DO_RED_LIMIT}", annotation_font_size=14)
    fig.update_layout(title="측정소별 하루 평균 용존산소(DO)", height=380, font=dict(size=15),
                      hovermode="x unified", legend=dict(orientation="h", y=-0.15),
                      margin=dict(l=10, r=10, t=50, b=10))
    fig.update_xaxes(tickformat="%m/%d", hoverformat="%m월 %d일")
    return fig


def show_all(today):
    """모든 측정소의 가장 최근 신호와 최근 DO를 한 화면에 보여 준다."""
    st.caption(f"측정소마다 공개된 마지막 날의 신호와, 최근 {SHOW_DAYS}일의 용존산소예요. 참고용입니다.")
    tables, fetched_at = {}, ""
    for name, site_id in config.STATIONS.items():
        table, fetched_at = safe_load(site_id, today - dt.timedelta(days=LOOK_BACK_DAYS), today)
        tables[name] = None if table is None else table.tail(SHOW_DAYS)
    columns = st.columns(4)  # 한 줄에 카드 네 장
    for number, (name, table) in enumerate(tables.items()):
        with columns[number % 4]:
            lamp_card(name, table)
    if config.DO_RED_LIMIT_IS_TEMPORARY:
        st.caption(f"※ 빨강 기준값 {config.DO_RED_LIMIT}은 출처를 확인하기 전의 임시값이에요.")
    st.plotly_chart(all_chart(tables), width="stretch")
    st.caption("그래프 아래의 측정소 이름을 누르면 그 선을 끄고 켤 수 있어요.")
    return fetched_at


# ── 여기부터 화면 ─────────────────────────────────────
st.set_page_config(page_title="수질 조기 신호", page_icon="💧")
st.title("💧 수질 조기 신호")
st.markdown("##### 낙동강 물속 산소가 줄어드는 흐름을 일찍 알아차리도록 돕는 신호등이에요.")
st.info("참고용 자료입니다. 간단한 규칙 세 개로 계산한 것이라 실제 수질 상태와 다를 수 있어요.")

ALL = "전체"  # 측정소 버튼 맨 앞에 두는 '모두 보기' 버튼의 글자
names = [ALL] + list(config.STATIONS)
picked = st.segmented_control("측정소 (이름을 누르면 그곳만 볼 수 있어요)", names, default=ALL)
today = dt.datetime.now(KST).date()
if picked is None or picked == ALL:  # 고른 것을 다시 눌러 풀면 '전체'로 본다
    fetched_at = show_all(today)
else:
    fetched_at = show_station(picked, today)

st.divider()
st.caption("자료 출처: 공공데이터포털(data.go.kr) 「국립환경과학원_수질 DB」 수질자동측정망 운영결과, "
           "기상청 API허브 종관기상관측 일자료(날씨)  \n"
           f"마지막으로 불러온 시각: {fetched_at} (한국 시간)")
