# algae_tab.py — "최근 자료" 탭 안의 녹조(조류경보) 칸 (5차 G2단계)
# 수질 자동측정 자료는 늦게 공개되지만, 조류경보 측정은 약 1주 늦게 공개된다. 그 '강물의 최근 모습'을 보여 준다.
import plotly.graph_objects as go
import streamlit as st

import algae
import config

# 항목 → (선 색, 단위, 소수 자리)
LOOKS = {"DO": ("#1565c0", "㎎/ℓ", 1), "남조류": ("#00897b", "개/㎖", 0),
         "수온": ("#f57c00", "℃", 1), "클로로필-a": ("#2e7d32", "㎎/㎥", 1)}


@st.cache_data(ttl=6 * 3600, show_spinner="녹조 측정 자료를 불러오는 중이에요…")
def load_algae(site, today):
    """최근 몇 달 녹조 측정 표. 6시간 동안 기억한다. (일주일에 1~2번만 새 자료가 생긴다)"""
    return algae.load_algae(site, today)


@st.cache_data(ttl=24 * 3600, show_spinner="지난해 녹조 측정 자료를 불러오는 중이에요…")
def load_last_year(site, today):
    """지난해 같은 기간의 측정 표. 하루 동안 기억한다. (지난 자료는 바뀌지 않으니까)"""
    return algae.load_last_year(site, today)


LAST_YEAR_ITEMS = ["DO", "수온", "클로로필-a"]  # 지난해와 견주는 항목 (남조류는 해마다 차이가 너무 커서 뺐다)


def compare_lines(table, last):
    """가장 최근 측정을 지난해 같은 무렵과 견주는 문장들. 본 숫자만 쓴다."""
    day = table["날짜"].iloc[-1]
    lines = []
    for item in LAST_YEAR_ITEMS:
        now = table[item].iloc[-1]
        row = algae.last_year_near(last, day, item)
        if row is None or now != now:
            lines.append(f"**{item}**: 지난해 같은 무렵에는 견줄 측정 값이 없어요.")
            continue
        change = now - row[item]
        word = "같아요" if change == 0 else f"{number(abs(change), item)} {'높아요' if change > 0 else '낮아요'}"
        lines.append(f"**{item}** {number(now, item)}는 지난해 같은 무렵"
                     f"({row['날짜']:%Y년 %m월 %d일} {number(row[item], item)})보다 {word}.")
    return lines


def number(value, item):
    """숫자를 단위와 함께 글자로. 빈 값이면 '값 없음'."""
    color, unit, digits = LOOKS[item]
    if value != value:  # 빈 값(NaN)은 자기 자신과 같지 않다
        return "값 없음"
    return f"{value:,.{digits}f}{unit}"


def latest_lines(table, today):
    """가장 최근 측정과 그 앞 측정을 견주는 문장들. 본 것만 쓴다."""
    last, before = table.iloc[-1], table.iloc[-2]
    gap = (today - last["날짜"].date()).days
    lines = [f"가장 최근 측정은 **{last['날짜']:%m월 %d일}**이에요 ({gap}일 전). "
             f"그 앞 측정은 {before['날짜']:%m월 %d일}이었어요."]
    for item in LOOKS:
        change = last[item] - before[item]
        if change != change:  # 둘 중 하나가 빈 값
            word = ""
        elif change == 0:
            word = " (그 앞 측정과 같아요)"
        else:
            word = f" (그 앞보다 {number(abs(change), item)} {'올랐' if change > 0 else '내려갔'}어요)"
        lines.append(f"**{item}**: {number(last[item], item)}{word}")
    return lines


def algae_chart(table, item, moved=None):
    """측정한 날만 점으로 찍고 선으로 잇는다. 남조류에는 기준선, 나머지에는 지난해 선(회색)을 더한다."""
    color, unit, digits = LOOKS[item]
    fig = go.Figure()
    if moved is not None and item in LAST_YEAR_ITEMS:
        fig.add_scatter(x=moved["날짜"], y=moved[item], mode="lines+markers", name="지난해",
                        line=dict(color="#9e9e9e", dash="dot", width=1.5), marker=dict(size=5),
                        customdata=moved["지난해 날짜"],
                        hovertemplate="지난해 %{customdata}: %{y:,." + str(digits) + "f}" + unit + "<extra></extra>")
    fig.add_scatter(x=table["날짜"], y=table[item], mode="lines+markers", name="올해",
                    line=dict(color=color, width=2), marker=dict(size=8),
                    hovertemplate="%{x|%m월 %d일}: %{y:,." + str(digits) + "f}" + unit + "<extra></extra>")
    if item == "남조류":
        # 두 선이 가까워서 글자가 겹치지 않게 하나는 왼쪽, 하나는 오른쪽에 쓴다
        for value, word, side in [(config.ALGAE_WATCH, f"관심 기준 {config.ALGAE_WATCH:,}", "top right"),
                                  (config.ALGAE_ALERT, f"경계 기준 {config.ALGAE_ALERT:,}", "top left")]:
            fig.add_hline(y=value, line=dict(color="#c62828", dash="dot", width=1),
                          annotation_text=word, annotation_position=side)
    fig.update_layout(title=f"{item} ({unit})", height=300, font=dict(size=14),
                      showlegend=moved is not None and item in LAST_YEAR_ITEMS,
                      legend=dict(orientation="h", y=-0.2), margin=dict(l=10, r=10, t=50, b=10))
    fig.update_xaxes(tickformat="%m/%d")
    return fig


def show_unknowns(place):
    """녹조 칸에서 '아직 모르는 것'."""
    st.markdown("\n".join("- " + line for line in [
        "❓ 재지 않은 날의 강. 그래프의 선은 측정한 날의 점을 이은 것일 뿐, 그 사이 날들의 값이 아니에요.",
        "❓ 실제 조류경보 발령 단계. 이 자료에는 발령 칸이 없어요. 빨간 점선은 기준 숫자일 뿐이에요.",
        "❓ 남조류가 많아지면 DO가 어떻게 되는지. 아직 확인하지 않은 가설이에요.",
        f"❓ {place} 지점이 우리 앱의 수질 측정소와 같은 곳인지 (확인하지 못했어요)",
    ]))


def show_algae(today):
    """'최근 자료' 탭의 녹조 칸 전체."""
    st.markdown("#### 🦠 강물의 최근 모습 — 녹조 측정 (주 1~2번)")
    place = st.segmented_control("녹조 측정 지점", list(config.ALGAE_SITES), default="물금·매리",
                                 key="algae_place") or "물금·매리"
    try:
        table = load_algae(config.ALGAE_SITES[place], today)
    except Exception:  # 오류 내용에 인증키가 섞일 수 있어서 그대로 보여 주지 않는다
        st.warning("녹조 측정 자료를 불러오지 못했어요. 잠시 뒤 다시 열어 주세요.")
        return
    if len(table) < 2:
        st.info(f"최근 {config.ALGAE_MONTHS}개월 동안 {place}의 측정 자료가 두 번보다 적어요.")
        return
    st.markdown("\n".join("- " + line for line in latest_lines(table, today)))
    moved = None
    try:
        last = load_last_year(config.ALGAE_SITES[place], today)
        st.markdown("**📆 지난해 같은 무렵과 견주면**")
        st.markdown("\n".join("- " + line for line in compare_lines(table, last)))
        moved = algae.shift_year(last)
        moved["지난해 날짜"] = last["날짜"].dt.strftime("%Y년 %m월 %d일")
        moved = moved[(moved["날짜"] >= table["날짜"].min()) & (moved["날짜"].dt.date <= today)]
    except Exception:  # 지난해 자료가 없어도 올해 그래프는 보여 준다
        st.caption("지난해 자료를 불러오지 못했어요.")
    for row in [["DO", "남조류"], ["수온", "클로로필-a"]]:
        for column, item in zip(st.columns(2), row):
            column.plotly_chart(algae_chart(table, item, moved), width="stretch")
    st.caption(f"최근 {config.ALGAE_MONTHS}개월, {len(table)}번 측정. 출처: 국립환경과학원 조류경보제 조회서비스(공공데이터포털). "
               "남조류 기준선은 물환경정보시스템 범례의 상수원구간 숫자이며 실제 발령과 다를 수 있어요. "
               f"회색 점선은 지난해 같은 기간 값을 1년 뒤로 옮겨 그린 것이고, 문장은 1년 전 날짜 앞뒤 {config.ALGAE_NEAR_DAYS}일 안에서 "
               "가장 가까운 측정과 견준 거예요. 지난해 한 해와 견준 것일 뿐 '평소'는 아니에요. 참고용이에요.")
    show_unknowns(place)
