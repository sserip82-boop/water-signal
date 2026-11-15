# explore_tab.py — "🔬 탐구" 탭: 남조류와 용존산소(DO) (6차 T2단계)
# 신호등 규칙은 바꾸지 않는다. 자료에서 센 것과, 아직 확인하지 않은 가설을 나눠 보여 준다.
import plotly.graph_objects as go
import streamlit as st

import algae_history
import config
import hourly_summary

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
    down, n, mean = algae_history.down_count(events)
    cold = (events["수온 변화"] < 0).sum()
    st.markdown(f"이런 때가 **{n}번** 있었고, 그중 **{down}번({down / n:.0%})** DO가 내려갔어요 "
                f"(평균 {mean:+.2f}㎎/ℓ). 그때 수온도 내려간 때가 {cold}번이에요. "
                "물이 차가워지면 산소는 더 잘 녹는 쪽인데도 DO가 내려간 때가 많았어요.")
    k_down, k_n, k_mean = algae_history.down_count(algae_history.drop_events(table, dropped=False))
    if k_n:
        st.markdown(f"**비교 집단**: 남조류가 {config.ALGAE_MANY:,}개 이상이었는데 그만큼 줄지 **않은** 때는 "
                    f"{k_n}번 중 {k_down}번({k_down / k_n:.0%}) DO가 내려갔어요(평균 {k_mean:+.2f}㎎/ℓ).")
    st.info("💡 **대조군(비교 집단)**: 약이 효과가 있는지 알려면 약을 먹은 사람과 먹지 않은 사람을 견줘야 해요. "
            "DO는 원래도 오르내리니까, '줄지 않은 때'보다 더 자주 내려가야 특별하다고 말할 수 있어요.")
    st.dataframe(events_table(events), hide_index=True, width="stretch")
    st.caption("❓ 가설 두 가지(어느 쪽인지 이 자료로는 가를 수 없어요): "
               "(가) 줄어든 조류가 분해될 때 산소를 쓴다 — 비커 연구의 '잃은 산소'와 이어 볼 수 있어요. "
               "(나) ②처럼 조류가 많던 날은 광합성으로 DO가 덤으로 높았는데, 조류가 줄며 그 덤이 사라졌다. "
               "남조류가 왜 줄었는지(비, 수온, 방류 등)도 알 수 없어요.")


@st.cache_data(ttl=24 * 3600)
def load_summary():
    """④ 12곳 표. 저장해 둔 파일로 계산하니 하루 동안 기억한다."""
    return algae_history.site_summary()


def show_sites():
    """④ 다른 지점에서도? — 12곳의 사건과 비교 집단."""
    st.markdown("#### ④ 다른 지점에서도 그럴까? — 낙동강 12곳")
    summary = load_summary()
    shown = summary.copy()
    for key in ["사건", "비교"]:
        shown[key + " (DO 내려감)"] = shown.apply(
            lambda r: f"{r[key + ' 내려감']}/{r[key]} ({r[key + ' 내려감'] / r[key]:.0%})" if r[key] else "-", axis=1)
        shown[key + " 평균"] = shown[key + " 평균"].map(lambda v: f"{v:+.2f}" if v == v else "-")
    st.dataframe(shown[["지점", "사건 (DO 내려감)", "사건 평균", "비교 (DO 내려감)", "비교 평균"]],
                 hide_index=True, width="stretch", height=36 * (len(shown) + 1) + 4)  # 12곳이 한 번에 보이게
    total = summary[["사건 내려감", "사건", "비교 내려감", "비교"]].sum()
    higher = (summary["사건 내려감"] / summary["사건"] > summary["비교 내려감"] / summary["비교"]).sum()
    st.markdown(f"12곳을 합치면 사건 때 **{total['사건']}번 중 {total['사건 내려감']}번"
                f"({total['사건 내려감'] / total['사건']:.0%})**, 비교 집단은 {total['비교']}번 중 "
                f"{total['비교 내려감']}번({total['비교 내려감'] / total['비교']:.0%}) DO가 내려갔어요. "
                f"사건 때 더 자주 내려간 곳은 12곳 중 **{higher}곳**이에요.")
    st.caption("위에서 아래로 상류 → 하류 순서예요. 이름에 '보'가 붙은 곳(조류 관찰 지점)은 DO가 내려간 폭이 더 컸는데, 이유는 몰라요. "
               "평균은 ㎎/ℓ. 두 측정 사이가 " + f"{config.DROP_GAP_DAYS}일 이하일 때만 셌어요.")


@st.cache_data(ttl=24 * 3600)
def load_pairs():
    """⑤ 짝마다 사건·비교 집단 결과. 저장해 둔 파일로 계산하니 하루 동안 기억한다."""
    return hourly_summary.pair_results()


def example_chart():
    """⑤ 예시: 사건 앞날과 뒷날의 24시간 DO."""
    name, first, second = config.HOURLY_EXAMPLE
    station = config.HOURLY_PAIRS[name][1]
    example = hourly_summary.load_example()
    fig = go.Figure()
    for day, color, label in [(first, "#1565c0", "남조류가 많던 날"), (second, "#9e9e9e", "남조류가 줄어든 뒤")]:
        part = example[example["시각"].dt.strftime("%Y-%m-%d") == day]
        fig.add_scatter(x=part["시각"].dt.hour, y=part["DO"], mode="lines+markers", name=f"{day} ({label})",
                        line=dict(color=color, width=2), marker=dict(size=5),
                        hovertemplate="%{x}시: %{y:.1f}㎎/ℓ<extra></extra>")
    fig.update_xaxes(title="시각 (0시 ~ 23시)", dtick=3)
    fig.update_yaxes(title="DO (㎎/ℓ)")
    fig.update_layout(title=f"예시: {station} 측정소의 하루 DO ({name} 근처)", height=340, font=dict(size=14),
                      legend=dict(orientation="h", y=-0.3), margin=dict(l=10, r=10, t=50, b=10))
    return fig


def pair_table(result):
    """⑤ 짝마다 '최저 내려감', '폭 줄어듦' 표를 화면용으로."""
    rows = []
    for pair, part in result.groupby("짝", sort=False):
        row = {"짝 (녹조 지점↔자동측정소)": pair}
        for _, r in part.iterrows():
            n = r["횟수"]
            row[f"{r['무리']}: 최저 내려감"] = f"{r['최저 내려감']}/{n}" if n else "-"
            row[f"{r['무리']}: 폭 줄어듦"] = f"{r['폭 줄어듦']}/{n}" if n else "-"
        rows.append(row)
    import pandas as pd
    return pd.DataFrame(rows)


def show_hourly():
    """⑤ 하루 중 DO로 가설 (가)·(나) 가르기."""
    st.markdown("#### ⑤ 하루 중 DO로 가설 가르기 — 시간별 자료")
    st.markdown("③의 두 가설은 **하루 중 DO 모습**이 서로 다르게 예상돼요. "
                "물환경정보시스템의 자동측정소 **1시간 간격** 자료(2022~2025년)로 확인해 봤어요.")
    st.markdown("- **(가) 분해로 산소를 씀** → 사건 뒤 **하루 최저**(밤~새벽)가 내려가요.\n"
                "- **(나) 광합성 덤이 사라짐** → 사건 뒤 **하루 오르내림 폭**(최고 − 최저)이 줄어요.")
    st.plotly_chart(example_chart(), width="stretch")
    result = load_pairs()
    total = result.groupby("무리")[["횟수", "최저 내려감", "폭 줄어듦"]].sum()
    ev, cp = total.loc["사건"], total.loc["비교"]
    st.markdown(f"5곳을 합치면 남조류가 갑자기 줄었을 때(**{ev['횟수']}번**) "
                f"**폭이 줄어든 때 {ev['폭 줄어듦']}번({ev['폭 줄어듦'] / ev['횟수']:.0%})**, "
                f"최저가 내려간 때 {ev['최저 내려감']}번({ev['최저 내려감'] / ev['횟수']:.0%})이에요. "
                f"비교 집단({cp['횟수']}번)은 폭 줄어듦 {cp['폭 줄어듦']}번({cp['폭 줄어듦'] / cp['횟수']:.0%}), "
                f"최저 내려감 {cp['최저 내려감']}번({cp['최저 내려감'] / cp['횟수']:.0%})이었어요.")
    st.success("이 자료에서는 **폭이 줄어드는 모습**이 비교 집단보다 훨씬 자주 보였어요. 가설 **(나)에 더 가까워요.** "
               "최저가 내려간 때도 조금 더 많아서 (가)가 틀렸다고 말할 수는 없어요. 둘이 함께 일어날 수도 있어요.")
    st.dataframe(pair_table(result), hide_index=True, width="stretch")
    st.caption(f"자동측정소는 녹조 지점에서 2.5~5km 떨어져 있어요(공식 측정소 정보로 짝지음). 앞·뒤 측정일 모두 "
               f"{config.HOURLY_MIN_HOURS}시간 이상 잰 때만 셌어요. 사건이 몇십 번뿐이라 참고용이에요. "
               "출처: 물환경정보시스템 국가수질자동측정망 시간자료(파일셋 다운로드).")


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
    show_sites()
    try:
        show_hourly()
    except Exception:
        st.warning("시간별 자료를 불러오지 못했어요.")
    st.markdown("#### ❓ 아직 모르는 것")
    st.markdown("\n".join("- " + line for line in [
        "측정 시각(낮인지 밤인지)과, 측정하지 않은 날의 DO 최저값",
        "남조류가 줄어든 이유 (비, 수온, 댐·보 방류 등)",
        "⑤에서 (나)에 더 가까운 모습이 보였지만, 짝지은 측정소가 몇 km 떨어져 있고 사건이 적어서 확실하지 않아요",
        "낙동강 12곳 말고 다른 강(한강·금강 등)에서도 같을지",
        "함께 움직였다고 해서 한쪽이 다른 쪽의 원인이라고 말할 수는 없어요.",
    ]))
    st.caption("출처: 국립환경과학원 조류경보제 조회서비스(공공데이터포털). 항목 뜻은 물환경정보시스템 화면과 값을 맞춰 확인했어요.")
