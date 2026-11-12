# app.py — 화면을 만드는 파일 (실행: streamlit run app.py)
import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analysis
import api
import config

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


def show_result(view):
    """신호등, 그래프 두 개, 날마다의 표를 보여 준다."""
    show_lamp(view.iloc[-1])
    if config.DO_RED_LIMIT_IS_TEMPORARY:
        st.caption(f"※ 빨강 기준값 {config.DO_RED_LIMIT}은 출처를 확인하기 전의 임시값이에요.")
    st.plotly_chart(make_chart(view, "DO", "하루 평균 용존산소(DO)", "#1f77b4",
                               config.DO_RED_LIMIT), width="stretch")
    st.plotly_chart(make_chart(view, "수온", "하루 평균 수온(℃)", "#e8743b"), width="stretch")
    with st.expander("날마다의 숫자 보기"):
        table = view[["날짜", "DO", "수온", "신호"]].copy()
        table["날짜"] = table["날짜"].dt.strftime("%m/%d")
        st.dataframe(table.round(1), hide_index=True, width="stretch")


# ── 여기부터 화면 ─────────────────────────────────────
st.set_page_config(page_title="수질 조기 신호", page_icon="💧")
st.title("💧 수질 조기 신호")
st.markdown("##### 낙동강 물속 산소가 줄어드는 흐름을 일찍 알아차리도록 돕는 신호등이에요.")
st.info("참고용 자료입니다. 간단한 규칙 세 개로 계산한 것이라 실제 수질 상태와 다를 수 있어요.")

station = st.selectbox("측정소", list(config.STATIONS))
site_id = config.STATIONS[station]
today = dt.datetime.now(KST).date()

# ① 최근 자료를 받아 "공개된 가장 마지막 날"을 찾는다
recent_table, fetched_at = safe_load(site_id, today - dt.timedelta(days=LOOK_BACK_DAYS), today)
if recent_table is None:
    st.warning(f"최근 {LOOK_BACK_DAYS}일 동안 공개된 자료가 없어요.")
    st.stop()
latest = recent_table["날짜"].max().date()
st.caption(f"지금 공개된 자료는 {latest:%Y년 %m월 %d일}까지예요. (오늘 자료는 아직 없어요)")

# ② 기간을 고르고, 신호 계산에 앞의 며칠이 필요하니 조금 더 넉넉히 받는다
first, last = pick_period(latest)
table, fetched_at = safe_load(site_id, first - dt.timedelta(days=config.YELLOW_DAYS), last)
view = None if table is None else table[table["날짜"].dt.date >= first]
if view is None or view.empty:
    st.warning("고른 기간에는 자료가 없어요. 다른 날짜를 골라 주세요.")
else:
    show_result(view)

st.divider()
st.caption("자료 출처: 공공데이터포털(data.go.kr) 「국립환경과학원_수질 DB」 수질자동측정망 운영결과  \n"
           f"마지막으로 불러온 시각: {fetched_at} (한국 시간)")
