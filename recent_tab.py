# recent_tab.py — "최근 자료" 탭 화면 (5차)
# 수질 자료는 늦게 공개되지만 날씨는 어제까지 온다. 요즘 날씨가 평년과 다른지 오늘 기준으로 보여 준다.
import datetime as dt

import plotly.graph_objects as go
import streamlit as st

import algae_tab
import config
import forecast
import normals
import weather

RECENT_DAYS = 30  # 최근 며칠을 보여 줄까 (학생이 바꿔 볼 수 있는 숫자)
ITEMS = {"기온": ("#d93025", "℃"), "햇빛 시간": ("#e6b800", "시간")}  # 항목 → (선 색, 단위)


@st.cache_data(ttl=24 * 3600, show_spinner="지난 10년 날씨를 불러오는 중이에요…")
def load_past(stn):
    """지난 10년 날씨. 하루 동안 기억한다. (지난 자료는 바뀌지 않으니까)"""
    return normals.load_past_years(stn)


@st.cache_data(ttl=3 * 3600, show_spinner="최근 날씨를 불러오는 중이에요…")
def load_recent(stn, first_day, last_day):
    """최근 날씨. 3시간 동안 기억한다."""
    return weather.load_weather(stn, first_day, last_day)


def band_chart(recent, band, item):
    """실제 값(실선)과 평년 범위(연한 띠, 가운데 점선)를 한 그래프에 그린다."""
    color, unit = ITEMS[item]
    fig = go.Figure()
    fig.add_scatter(x=band["날짜"], y=band["위"], mode="lines", line=dict(width=0),
                    hoverinfo="skip", showlegend=False)
    fig.add_scatter(x=band["날짜"], y=band["아래"], mode="lines", line=dict(width=0),
                    fill="tonexty", fillcolor="rgba(120,120,120,0.18)", name="평년 범위",
                    hoverinfo="skip")
    fig.add_scatter(x=band["날짜"], y=band["평균"], mode="lines", name="평년 평균",
                    line=dict(color="#888888", dash="dot", width=1.5), hoverinfo="skip")
    fig.add_scatter(x=recent["날짜"], y=recent[item], mode="lines+markers", name=f"올해 {item}",
                    line=dict(color=color, width=3), marker=dict(size=7),
                    hovertemplate="%{x|%m월 %d일}: %{y:.1f}" + unit + "<extra></extra>")
    fig.update_layout(title=f"하루 {item} ({unit})", height=300, font=dict(size=14),
                      legend=dict(orientation="h", y=-0.2), margin=dict(l=10, r=10, t=50, b=10))
    fig.update_xaxes(tickformat="%m/%d")
    return fig


def streak_card(recent, band, item):
    """'평년보다 높은 날이 ○일째' 같은 한 줄을 만든다."""
    state, days = normals.end_streak(recent, band, item)
    last = recent["날짜"].max()
    if state is None:
        return f"**{item}**: {last:%m월 %d일} 값이 없어서 알 수 없어요."
    if state == "안":
        return f"**{item}**: 평년 범위 안이에요. ({days}일째)"
    word = "높은" if state == "높음" else "낮은"
    mark = "🔺" if state == "높음" else "🔻"
    return f"{mark} **{item}**: 평년 범위보다 {word} 날이 **{days}일째**예요."


def rain_chart(recent):
    """하루 비의 양을 막대로 그린다. (비가 기록된 날만 막대가 생긴다)"""
    fig = go.Figure()
    fig.add_bar(x=recent["날짜"], y=recent["비"], marker_color="#2e9e4f",
                hovertemplate="%{x|%m월 %d일}: %{y:.1f}mm<extra></extra>")
    fig.update_layout(title="하루 비 (mm)", height=260, font=dict(size=14),
                      margin=dict(l=10, r=10, t=50, b=10))
    fig.update_xaxes(tickformat="%m/%d")
    return fig


def rain_cards(recent, past, first, last):
    """최근 비를 평년과 견주는 문장들."""
    count, total = normals.rain_days(recent)
    usual_count, usual_total, usual_sd = normals.rain_normal(past, first, last)
    dry = normals.dry_streak(recent)
    lines = [f"**비**: 최근 {RECENT_DAYS}일 동안 비가 온 날 **{count}일**, 합 **{total:.0f}mm**. "
             f"평년 같은 기간에는 평균 {usual_count:.1f}일, {usual_total:.0f}mm였어요.",
             f"**비가 오지 않은 날**: 마지막으로 비가 온 뒤 **{dry}일째**예요." if dry > 0
             else "**비가 오지 않은 날**: 마지막 날에도 비가 왔어요."]
    if total < usual_total - usual_sd:
        lines[0] = "🔻 " + lines[0] + " (평년 범위보다 적어요)"
    elif total > usual_total + usual_sd:
        lines[0] = "🔺 " + lines[0] + " (평년 범위보다 많아요)"
    return lines


@st.cache_data(ttl=3600, show_spinner="기상청 예보를 불러오는 중이에요…")
def load_forecast(place):
    """기상청 단기·중기 예보. 1시간 동안 기억한다. (예보는 하루에 여러 번 새로 나온다)"""
    return forecast.forecast_days(place)


def forecast_chart(days, bands):
    """예보한 아침 최저·낮 최고(점선)와 그날의 평년 범위(띠)를 함께 그린다."""
    fig = go.Figure()
    for item, column, color in [("최고기온", "최고", "#d93025"), ("최저기온", "최저", "#1f77b4")]:
        band = bands[item]
        fig.add_scatter(x=band["날짜"], y=band["위"], mode="lines", line=dict(width=0),
                        hoverinfo="skip", showlegend=False)
        fig.add_scatter(x=band["날짜"], y=band["아래"], mode="lines", line=dict(width=0),
                        fill="tonexty", fillcolor="rgba(120,120,120,0.15)",
                        name=f"평년 {item} 범위", hoverinfo="skip")
        fig.add_scatter(x=days["날짜"], y=days[column], mode="lines+markers",
                        name=f"예보 {'낮 최고' if column == '최고' else '아침 최저'}",
                        line=dict(color=color, dash="dash", width=2), marker=dict(size=8),
                        hovertemplate="%{x|%m월 %d일}: %{y:.0f}℃<extra></extra>")
    fig.update_layout(title="기상청 예보 기온 (℃)", height=320, font=dict(size=14),
                      legend=dict(orientation="h", y=-0.2), margin=dict(l=10, r=10, t=50, b=10))
    fig.update_xaxes(tickformat="%m/%d")
    return fig


def forecast_cards(days, bands):
    """예보한 기온이 평년 범위 밖인 날을 문장으로."""
    lines = []
    for item, column, word in [("최고기온", "최고", "낮 최고기온"), ("최저기온", "최저", "아침 최저기온")]:
        joined = days.merge(bands[item], on="날짜")
        high = joined[joined[column] > joined["위"]]["날짜"]
        low = joined[joined[column] < joined["아래"]]["날짜"]
        if len(high):
            lines.append(f"🔺 {word}이 평년보다 **높을 수 있는 날**: " + ", ".join(f"{d:%m/%d}" for d in high))
        if len(low):
            lines.append(f"🔻 {word}이 평년보다 **낮을 수 있는 날**: " + ", ".join(f"{d:%m/%d}" for d in low))
    return lines or ["예보한 기온은 모두 평년 범위 안이에요."]


def show_forecast(place, past):
    """기상청 예보를 평년과 견주어 보여 준다."""
    days = load_forecast(place)
    bands = {item: normals.normal_table(past, list(days["날짜"].dt.date), item)
             for item in ["최고기온", "최저기온"]}
    st.markdown(f"#### 📅 앞으로 {len(days)}일 — 기상청 예보 ({place})")
    st.markdown("\n".join("- " + line for line in forecast_cards(days, bands)))
    st.plotly_chart(forecast_chart(days, bands), width="stretch")
    table = days[["날짜", "최저", "최고", "강수확률", "하늘", "출처"]].copy()
    table["날짜"] = table["날짜"].dt.strftime("%m/%d")
    st.dataframe(table.astype(object).fillna("-"), hide_index=True, width="stretch")  # 빈 값은 '-'로
    st.caption("우리가 맞힌 것이 아니라 기상청이 발표한 예보예요. 먼 날일수록 틀릴 수 있어요. "
               "단기예보(약 3일)의 0시·12시 기온을 아침 최저·낮 최고로 보았어요(기상청 문서로는 확인 전). "
               "중기 하늘·강수확률은 부산·울산·경남 전체 예보예요.")


def show_unknowns(water_latest, today):
    """이 탭에서 '아직 모르는 것'."""
    st.markdown("#### ❓ 아직 모르는 것")
    st.markdown("\n".join("- " + line for line in [
        f"매일의 강물 용존산소·수온. 수질 자동측정 자료는 {water_latest:%m월 %d일}까지라 "
        f"그 뒤 {(today - water_latest).days}일 동안은 위의 녹조 측정(주 1~2번)으로만 볼 수 있어요.",
        "날씨가 평년과 달라도 수질이 나빠질지는 알 수 없어요. "
        "지난여름 빨강 전 3일은 14번 중 12번이 수온이 높았지만, 날씨와 수질의 관계는 아직 확인하지 않은 가설이에요.",
        "비 값이 빈 날(-9)이 '비가 안 온 날'인지 '기록이 없는 날'인지. 여기서는 비가 안 온 날로 보았어요.",
        "관측 지점 번호와 이름이 맞는지 (아직 확인하지 못했어요)",
    ]))


def show_weather(place, today):
    """관측 지점 한 곳의 최근 날씨, 평년 범위, 이상 징후 문장을 보여 준다."""
    stn = config.WEATHER_STATIONS[place]
    first, last = today - dt.timedelta(days=RECENT_DAYS), today - dt.timedelta(days=1)
    recent = load_recent(stn, f"{first:%Y%m%d}", f"{last:%Y%m%d}")
    past = load_past(stn)
    days = list(recent["날짜"].dt.date)
    bands = {item: normals.normal_table(past, days, item) for item in ITEMS}
    st.markdown(f"#### 🔎 {recent['날짜'].max():%m월 %d일}까지의 이상 징후 ({place})")
    lines = [streak_card(recent, bands[item], item) for item in ITEMS]
    lines += rain_cards(recent, past, first, last)
    st.markdown("\n".join("- " + line for line in lines))
    for item in ITEMS:
        st.plotly_chart(band_chart(recent, bands[item], item), width="stretch")
    st.plotly_chart(rain_chart(recent), width="stretch")
    st.caption(f"평년 범위 = 이 관측 지점의 {config.NORMAL_FIRST_YEAR}~{config.NORMAL_LAST_YEAR}년 "
               f"같은 날짜 앞뒤 {config.NORMAL_HALF_WINDOW}일 값의 평균 ± 표준편차. "
               "비는 평년 같은 기간의 합과 견주었어요.")
    try:
        show_forecast(place, past)
    except Exception:  # 오류 내용에 인증키가 섞일 수 있어서 그대로 보여 주지 않는다
        st.warning("기상청 예보를 불러오지 못했어요. 잠시 뒤 다시 열어 주세요.")


def show_recent(today, water_latest):
    """'최근 자료' 탭 전체."""
    st.markdown("##### 강물 자료는 늦게 공개되지만, 날씨는 어제까지 볼 수 있어요. "
                "요즘 날씨가 평년과 다른지 살펴보며 이상 징후를 일찍 알아차려요.")
    st.info(f"수질 자동측정 자료는 **{water_latest:%m월 %d일}**까지, 녹조 측정은 약 1주 전까지(주 1~2번), "
            f"날씨는 어제인 **{today - dt.timedelta(days=1):%m월 %d일}**까지, "
            "기상청 예보는 약 10일 뒤까지 있어요. "
            "참고용이며, 날씨가 평년과 다르다고 수질이 나빠진다는 뜻은 아니에요.")
    places = list(config.WEATHER_STATIONS)
    place = st.segmented_control("기상 관측 지점", places, default="양산",
                                 key="recent_place") or "양산"
    try:
        show_weather(place, today)
    except Exception:  # 오류 내용에 인증키가 섞일 수 있어서 그대로 보여 주지 않는다
        st.error("날씨 자료를 불러오지 못했어요. 잠시 뒤 다시 열어 주세요.")
    st.divider()
    algae_tab.show_algae(today)
    st.divider()
    show_unknowns(water_latest, today)
