# explore_tab.py — "🔬 탐구" 탭: 남조류와 용존산소(DO) (6차 T2단계)
# 신호등 규칙은 바꾸지 않는다. 자료에서 센 것과, 아직 확인하지 않은 가설을 나눠 보여 준다.
import plotly.graph_objects as go
import streamlit as st

import algae_history
import config

SEASON_COLORS = {"봄": "#43a047", "여름": "#e53935", "가을": "#fb8c00", "겨울": "#1e88e5"}


def scatter(table, title, colors_by_season=True):
    """가로 남조류(10배씩 커지는 눈금), 세로 DO인 점 그래프. 세로 점선은 '많은 날' 기준."""
    fig = go.Figure()
    groups = table.groupby("계절") if colors_by_season else [("7~9월", table)]
    for season, part in groups:
        fig.add_scatter(x=part["남조류"] + 1, y=part["DO"], mode="markers", name=season,
                        marker=dict(size=7, opacity=0.7, color=SEASON_COLORS.get(season, "#e53935")),
                        customdata=part["날짜"].dt.strftime("%Y-%m-%d"),
                        hovertemplate="%{customdata}<br>남조류 %{x:,.0f}개/㎖<br>DO %{y:.1f}㎎/ℓ<extra></extra>")
    fig.add_vline(x=config.ALGAE_MANY, line=dict(color="#555555", dash="dot", width=1),
                  annotation_text=f"{config.ALGAE_MANY:,}개", annotation_position="top")
    fig.update_xaxes(type="log", title="남조류 (개/㎖, 눈금이 10배씩 커져요)")
    fig.update_yaxes(title="DO (㎎/ℓ)")
    fig.update_layout(title=title, height=380, font=dict(size=14),
                      legend=dict(orientation="h", y=-0.3), margin=dict(l=10, r=10, t=50, b=10))
    return fig


def compare_text(result, where):
    """'많은 날 DO 평균 ○.○(○번), 적은 날 ○.○(○번)' 문장."""
    (many, n_many), (few, n_few) = result["많은 날"], result["적은 날"]
    return (f"{where} 남조류 {config.ALGAE_MANY:,}개 이상인 날 DO 평균 **{many:.2f}㎎/ℓ**({n_many}번), "
            f"그보다 적은 날 **{few:.2f}㎎/ℓ**({n_few}번)이에요. (남조류나 DO가 빈 측정 {result['뺀 측정']}번은 뺐어요)")


def show_season(table):
    """① 계절이 만든 '가짜 관계'."""
    st.markdown("#### ① 한 해 전체로 보면 — 계절이 만든 '가짜 관계'")
    st.markdown(compare_text(algae_history.many_vs_few(table), "한 해 전체로 보면"))
    st.plotly_chart(scatter(table, "모든 측정 (점 색 = 계절)"), width="stretch")
    st.markdown("남조류가 많을 때 DO가 낮아 보여요. 그런데 남조류가 많은 점은 대부분 **여름** 점(빨강)이고, "
                "물이 따뜻하면 산소가 덜 녹아요. 그래서 이 차이를 **남조류 때문이라고 말할 수 없어요.**")
    st.info("💡 **숨은 원인(교란 변수)**: 여름에는 아이스크림도 많이 팔리고 물놀이 사고도 많아요. "
            "그렇다고 아이스크림이 사고의 원인은 아니죠. 둘 다 '더운 날씨'라는 숨은 원인 때문에 함께 늘어요.")


def show_summer(table):
    """② 같은 계절(7~9월)끼리만 견주기."""
    months = config.SUMMER_MONTHS
    label = f"{months[0]}~{months[-1]}월"
    summer = table[table["날짜"].dt.month.isin(months)]
    st.markdown(f"#### ② 같은 계절({label})끼리만 견주면")
    st.markdown(compare_text(algae_history.many_vs_few(table, months), f"{label}끼리 보면"))
    st.plotly_chart(scatter(summer, f"{label} 측정만", colors_by_season=False), width="stretch")
    st.markdown("같은 계절끼리 보니 남조류가 많은 날 DO가 **조금 더 높거나 비슷**했어요. 한 해 전체로 볼 때와 달라요.")
    st.caption("❓ 가설(확인하지 않음): 조류는 낮에 광합성으로 산소를 만든다. 측정 시각이 자료에 없어서 확인할 수 없어요.")


def events_table(events):
    """③ 사건 표를 화면용으로 다듬는다."""
    shown = events.copy()
    shown["날짜"] = shown["앞 측정"].dt.strftime("%Y-%m-%d") + " → " + shown["이번 측정"].dt.strftime("%m-%d")
    shown["남조류"] = shown.apply(lambda r: f"{r['남조류 앞']:,.0f} → {r['남조류 이번']:,.0f}", axis=1)
    shown["DO"] = shown.apply(lambda r: f"{r['DO 앞']:.1f} → {r['DO 이번']:.1f}", axis=1)
    return shown[["날짜", "남조류", "DO", "DO 변화", "수온 변화"]]


def show_drops(table):
    """③ 남조류가 갑자기 줄어든 뒤 DO."""
    events = algae_history.drop_events(table)
    st.markdown("#### ③ 남조류가 갑자기 줄어든 뒤 DO는?")
    st.caption(f"바로 앞 측정의 남조류가 {config.ALGAE_MANY:,}개 이상이었는데, 이번 측정에서 그 "
               f"{config.DROP_RATIO:g}배 이하가 된 때예요. 두 측정 사이가 {config.DROP_GAP_DAYS}일 이하일 때만 셌어요.")
    if events.empty:
        st.info("이런 때가 없었어요.")
        return
    down, cold = (events["DO 변화"] < 0).sum(), (events["수온 변화"] < 0).sum()
    st.markdown(f"이런 때가 **{len(events)}번** 있었고, 그중 **{down}번** DO가 내려갔어요 "
                f"(평균 {events['DO 변화'].mean():+.2f}㎎/ℓ). 그때 수온도 내려간 때가 {cold}번이에요. "
                "물이 차가워지면 산소는 더 잘 녹는 쪽인데도 DO가 내려간 때가 많았어요.")
    st.dataframe(events_table(events), hide_index=True, width="stretch")
    st.caption("❓ 가설(확인하지 않음): 줄어든 조류가 분해될 때 산소를 쓴다. 비커 연구의 '잃은 산소'와 이어 볼 수 있어요. "
               "남조류가 왜 줄었는지(비, 수온, 방류 등)는 이 자료로 알 수 없어요.")


def show_explore():
    """'🔬 탐구' 탭 전체."""
    st.markdown("##### 녹조(남조류)가 많아지면 강물의 산소는 어떻게 될까? 2020년부터의 조류경보 측정으로 살펴봐요.")
    place = st.segmented_control("측정 지점", list(config.ALGAE_SITES), default="물금·매리",
                                 key="explore_place") or "물금·매리"
    table, got = algae_history.load_history(config.ALGAE_SITES[place])
    st.info(f"{place}: {table['날짜'].min():%Y년 %m월 %d일} ~ {table['날짜'].max():%Y년 %m월 %d일}, "
            f"{len(table)}번 측정 ({got}에 받은 자료). 참고용 탐구이며, 신호등 규칙과는 이어지지 않아요.")
    show_season(table)
    show_summer(table)
    show_drops(table)
    st.markdown("#### ❓ 아직 모르는 것")
    st.markdown("\n".join("- " + line for line in [
        "측정 시각(낮인지 밤인지)과, 측정하지 않은 날의 DO 최저값",
        "남조류가 줄어든 이유 (비, 수온, 댐·보 방류 등)",
        "두 지점만 본 결과라 낙동강 전체에서도 같을지",
        "함께 움직였다고 해서 한쪽이 다른 쪽의 원인이라고 말할 수는 없어요.",
    ]))
    st.caption("출처: 국립환경과학원 조류경보제 조회서비스(공공데이터포털). 항목 뜻은 물환경정보시스템 화면과 값을 맞춰 확인했어요.")
