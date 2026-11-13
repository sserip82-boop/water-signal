# analysis.py — 받아 온 자료를 깔끔한 표로 바꾸는 파일
import pandas as pd

import api
import config

# 깔끔한 표의 칸 이름 → 원본에서 살펴볼 칸들(채널 1, 2, 3)
ITEMS = {
    "DO": config.DO_COLUMNS,
    "수온": config.TEMP_COLUMNS,
    "pH": config.PH_COLUMNS,
    "클로로필a": config.CHL_COLUMNS,
    "전기전도도": config.COND_COLUMNS,
    "탁도": config.TURB_COLUMNS,
    "총유기탄소": config.TOC_COLUMNS,
}


def clean_numbers(raw, columns):
    """칸들을 숫자로 바꾸고, 숫자가 아닌 값과 -999를 빈 값으로 만든다.
    돌려주는 것: (정리된 칸들, 숫자가 아니어서 버린 개수, -999여서 버린 개수)"""
    part = raw.reindex(columns=columns)  # 없는 칸은 빈 칸으로 채워진다
    numbers = part.apply(pd.to_numeric, errors="coerce")  # 글자는 빈 값이 됨
    not_number = int((part.notna() & numbers.isna()).sum().sum())
    below = numbers == config.BELOW_LIMIT
    return numbers.mask(below), not_number, int(below.sum().sum())


def first_filled(numbers):
    """채널 1→2→3 순서로 보고, 처음으로 값이 있는 칸의 값을 고른다."""
    return numbers.bfill(axis=1).iloc[:, 0]


def make_table(raw):
    """원본 표 → (날짜, DO, 수온, pH, 클로로필a) 표. 버린 개수도 출력한다."""
    table = pd.DataFrame({"날짜": pd.to_datetime(raw["MSR_DATE"])})
    for name, columns in ITEMS.items():
        numbers, not_number, below = clean_numbers(raw, columns)
        table[name] = first_filled(numbers).values
        empty_days = int(table[name].isna().sum())
        print(f"  {name}: 숫자 아님 {not_number}개, -999 {below}개 버림"
              f" / 값이 없는 날 {empty_days}일")
    return table.sort_values("날짜").reset_index(drop=True)


def recent_days(table, days):
    """표의 마지막 days일을 돌려준다. 날짜가 하루씩 이어지지 않거나
    DO·수온에 빈 값이 있으면 None(판단할 수 없음)을 돌려준다."""
    last = table.tail(days)
    if len(last) < days or last[["DO", "수온"]].isna().any().any():
        return None
    gaps = last["날짜"].diff().dropna()  # 날짜 사이 간격
    if (gaps != pd.Timedelta(days=1)).any():
        return None
    return last


def is_yellow(table):
    """노랑 규칙: 최근 며칠 동안 DO는 날마다 내려가고, 수온은 날마다 올랐는가?"""
    last = recent_days(table, config.YELLOW_DAYS)
    if last is None:
        return False
    do_falling = (last["DO"].diff().dropna() < 0).all()    # 전날보다 계속 작다
    temp_rising = (last["수온"].diff().dropna() > 0).all()  # 전날보다 계속 크다
    return bool(do_falling and temp_rising)


def recent_do(table, days):
    """마지막 days일의 DO 값들을 돌려준다. 빈 값이 있거나
    날짜가 하루씩 이어지지 않으면 None(판단할 수 없음)."""
    last = table.tail(days)
    if len(last) < days or last["DO"].isna().any():
        return None
    gaps = last["날짜"].diff().dropna()  # 날짜 사이 간격
    if (gaps != pd.Timedelta(days=1)).any():
        return None
    return last["DO"]


def do_change(table):
    """속도 = 오늘 DO − 어제 DO. 음수(-)면 떨어진 것. 못 구하면 None."""
    last = recent_do(table, 2)
    if last is None:
        return None
    return float(last.iloc[-1] - last.iloc[-2])


def is_fast_drop(table, limit):
    """속도 규칙 A: 하루 만에 DO가 limit 이상 떨어졌는가?"""
    change = do_change(table)
    if change is None:
        return False
    return -change >= limit  # 떨어진 양(-change)이 기준 이상인가


def is_speeding_up(table):
    """속도 규칙 B: 이틀 연속 떨어졌고, 오늘 떨어진 양이 어제보다 큰가?"""
    last = recent_do(table, 3)  # 그제, 어제, 오늘
    if last is None:
        return False
    drop_yesterday = last.iloc[0] - last.iloc[1]  # 어제 떨어진 양
    drop_today = last.iloc[1] - last.iloc[2]      # 오늘 떨어진 양
    return bool(drop_yesterday > 0 and drop_today > drop_yesterday)


def get_signal(table):
    """표의 마지막 날 신호를 (색, 이유 한 문장)으로 돌려준다."""
    today = table.iloc[-1]
    if pd.isna(today["DO"]):
        return "회색", "오늘 용존산소 값이 없어서 판단할 수 없어요."
    if today["DO"] < config.DO_RED_LIMIT:  # 빨강을 먼저 본다
        return "빨강", (f"하루 평균 용존산소({today['DO']:.1f})가 "
                      f"기준값({config.DO_RED_LIMIT})보다 낮아요.")
    if is_speeding_up(table):  # 주황(속도 규칙 B)을 노랑보다 먼저 본다
        do = recent_do(table, 3)
        return "주황", (f"용존산소가 이틀 연속 내려갔고, 내려가는 양이 더 커졌어요"
                      f"(어제 {do.iloc[0] - do.iloc[1]:.1f} → 오늘 {do.iloc[1] - do.iloc[2]:.1f}).")
    if is_yellow(table):
        last = recent_days(table, config.YELLOW_DAYS)
        return "노랑", (f"{config.YELLOW_DAYS}일 동안 용존산소는 계속 내려가고"
                      f"({last['DO'].iloc[0]:.1f}→{last['DO'].iloc[-1]:.1f}), "
                      f"수온은 계속 올랐어요"
                      f"({last['수온'].iloc[0]:.1f}→{last['수온'].iloc[-1]:.1f}).")
    return "초록", "용존산소가 기준값 이상이고, 계속 내려가거나 빨라지는 흐름도 없어요."


def signals_by_day(table):
    """날마다 '그날까지의 자료만 보고' 신호를 계산해 표에 붙인다."""
    result = table.copy()
    colors, reasons = [], []
    for i in range(len(table)):
        color, reason = get_signal(table.iloc[: i + 1])  # 그날까지만 잘라서
        colors.append(color)
        reasons.append(reason)
    result["신호"], result["이유"] = colors, reasons
    return result


def red_starts(daily):
    """빨강이 '새로 시작된 날'의 날짜들. (전날은 빨강이 아니었던 날)"""
    is_red = daily["신호"] == "빨강"
    return list(daily[is_red & ~is_red.shift(1, fill_value=False)]["날짜"])


def first_red_after(daily, day):
    """그날 뒤 SCORE_DAYS일 안에 처음 오는 빨강의 날짜. 없으면 None."""
    days_later = (daily["날짜"] - day).dt.days
    near = daily[(days_later >= 1) & (days_later <= config.SCORE_DAYS)
                 & (daily["신호"] == "빨강")]
    return None if near.empty else near["날짜"].iloc[0]


def score_card(daily, color):
    """그 색 신호의 성적표를 사전(dict)으로 돌려준다.
    켜진 날 / 그중 빨강이 뒤따른 날 / 빨강 시작 횟수 / 그중 이 신호가 먼저 켜진 횟수"""
    last_day = daily["날짜"].max()
    lit = daily[daily["신호"] == color]["날짜"]
    # 뒤 SCORE_DAYS일을 끝까지 지켜볼 수 있는 날만 센다
    lit = [day for day in lit if (last_day - day).days >= config.SCORE_DAYS]
    reds = [first_red_after(daily, day) for day in lit]  # 신호마다 뒤에 처음 온 빨강
    starts = red_starts(daily)
    warned = [day for day in starts if day in reds]  # 미리 신호가 있었던 빨강 시작
    return {"켜진 날": len(lit), "빨강이 뒤따름": sum(r is not None for r in reds),
            "빨강 시작": len(starts), "미리 켜짐": len(warned)}


def observed(view, first, last):
    """고른 기간(first~last)에 '본 것'을 세어 사전(dict)으로 돌려준다.
    전체 일수 / DO 값이 있는 날 / 빈 날 / DO가 가장 낮았던 날의 줄 / 색별 신호 일수"""
    total = (last - first).days + 1  # 달력으로 센 날 수
    have = view.dropna(subset=["DO"])  # DO 값이 있는 날만
    lowest = None if have.empty else have.loc[have["DO"].idxmin()]
    counts = view["신호"].value_counts()
    lit = {color: int(counts.get(color, 0)) for color in ["노랑", "주황", "빨강"]}
    return {"전체 일수": total, "값 있는 날": len(have), "빈 날": total - len(have),
            "최저": lowest, "신호": lit}


def usual_range(daily):
    """그 측정소의 '평소 범위'를 (평균, 표준편차)로 돌려준다.
    표준편차 = 값들이 평균에서 보통 얼마나 떨어져 있는지 나타내는 숫자."""
    return float(daily["DO"].mean()), float(daily["DO"].std())


def lost_oxygen(table, limit):
    """기준선 아래로 내려간 넓이(잃은 산소 누적)를 사다리꼴 넓이로 구한다.
    하루 간격으로 이어진 두 날만 잇는다. 빈 값이나 건너뛴 날은 넓이에 넣지 않는다."""
    lack = (limit - table["DO"]).clip(lower=0)  # 기준보다 모자란 양 (기준 이상이면 0)
    next_day = table["날짜"].diff() == pd.Timedelta(days=1)  # 바로 앞줄이 어제인가
    pieces = (lack + lack.shift(1)) / 2  # 사다리꼴 넓이 = (윗변 + 아랫변) ÷ 2 × 높이(1일)
    return float(pieces[next_day].sum())  # 빈 값이 낀 조각은 합에서 빠진다


def red_runs(daily):
    """빨강이 이어진 구간들을 (첫 줄 번호, 마지막 줄 번호) 목록으로 돌려준다."""
    runs, start = [], None
    for i, color in enumerate(daily["신호"]):
        if color == "빨강" and start is None:
            start = i  # 빨강이 시작됐다
        if color != "빨강" and start is not None:
            runs.append((start, i - 1))  # 빨강이 끝났다
            start = None
    if start is not None:  # 표가 끝날 때까지 빨강이 이어진 경우
        runs.append((start, len(daily) - 1))
    return runs


def came_back(daily, end):
    """빨강이 끝난 바로 다음 날의 줄을 돌려준다. 볼 수 없으면 (None, 왜 못 봤는지)."""
    if end + 1 >= len(daily):
        return None, "기간이 끝날 때까지 보지 못함"
    after = daily.iloc[end + 1]
    gap = (after["날짜"] - daily["날짜"].iloc[end]).days
    if pd.isna(after["DO"]) or gap > 1:
        return None, "바로 뒤에 값이 빈 날이 있어 모름"
    return after, ""


def signals_before(daily, start):
    """빨강이 시작되기 전 SCORE_DAYS일 안에 켜졌던 노랑·주황을 글자로 돌려준다.
    성적표와 같게, 그 사이에 다른 빨강이 끼어 있으면 그 앞의 신호는 세지 않는다."""
    days_ago = (daily["날짜"].iloc[start] - daily["날짜"]).dt.days
    near = daily[(days_ago >= 1) & (days_ago <= config.SCORE_DAYS)]["신호"]
    reds = near[near == "빨강"]
    if not reds.empty:  # 앞 사건의 빨강 뒤에 켜진 신호만 남긴다
        near = near.loc[reds.index[-1]:]
    found = [color for color in ["노랑", "주황"] if (near == color).any()]
    return ", ".join(found) if found else "없음"


def red_event(daily, start, end):
    """빨강 사건 하나를 잰다: 깊이, 기간, 잃은 산소, 되돌아온 빠르기."""
    part = daily.iloc[start:end + 1]
    low = part.loc[part["DO"].idxmin()]  # 가장 낮았던 날의 줄
    around = daily.iloc[max(start - 1, 0):end + 2]  # 앞뒤 하루씩 더해야 넓이가 맞다
    back, memo = came_back(daily, end)
    event = {"시작": part["날짜"].iloc[0], "이어진 날": len(part),
             "가장 낮은 값": float(low["DO"]), "가장 낮은 날": low["날짜"],
             "잃은 산소": lost_oxygen(around, config.DO_RED_LIMIT),
             "앞선 신호": signals_before(daily, start),
             "되돌아온 날": None, "걸린 날": None, "하루에 오른 양": None, "메모": memo}
    if back is not None:
        days = (back["날짜"] - low["날짜"]).days  # 가장 낮은 날부터 되돌아온 날까지
        event.update({"되돌아온 날": back["날짜"], "걸린 날": days,
                      "하루에 오른 양": float(back["DO"] - low["DO"]) / days})
    return event


def red_events(daily):
    """빨강 사건들을 시간순 목록으로 돌려준다."""
    return [red_event(daily, start, end) for start, end in red_runs(daily)]


if __name__ == "__main__":
    # 공개된 자료 중 가장 최근 14일 (2026-11-12 기준 8월 31일이 마지막)
    raw = api.load_period(config.STATIONS["양산"], "20260818", "20260831")
    print("받은 줄 수:", len(raw))
    table = make_table(raw)
    daily = signals_by_day(table)[["날짜", "DO", "수온", "신호"]]
    print(daily.to_string(index=False, float_format="%.2f"))  # 소수 둘째 자리까지
    print("마지막 날 신호:", *get_signal(table))
