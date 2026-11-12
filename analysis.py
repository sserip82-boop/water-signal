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


def get_signal(table):
    """표의 마지막 날 신호를 (색, 이유 한 문장)으로 돌려준다."""
    today = table.iloc[-1]
    if pd.isna(today["DO"]):
        return "회색", "오늘 용존산소 값이 없어서 판단할 수 없어요."
    if today["DO"] < config.DO_RED_LIMIT:  # 빨강을 먼저 본다
        return "빨강", (f"하루 평균 용존산소({today['DO']:.1f})가 "
                      f"기준값({config.DO_RED_LIMIT})보다 낮아요.")
    if is_yellow(table):
        last = recent_days(table, config.YELLOW_DAYS)
        return "노랑", (f"{config.YELLOW_DAYS}일 동안 용존산소는 계속 내려가고"
                      f"({last['DO'].iloc[0]:.1f}→{last['DO'].iloc[-1]:.1f}), "
                      f"수온은 계속 올랐어요"
                      f"({last['수온'].iloc[0]:.1f}→{last['수온'].iloc[-1]:.1f}).")
    return "초록", "용존산소가 기준값 이상이고, 계속 내려가는 흐름도 없어요."


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


if __name__ == "__main__":
    # 공개된 자료 중 가장 최근 14일 (2026-11-12 기준 8월 31일이 마지막)
    raw = api.load_period(config.STATIONS["양산"], "20260818", "20260831")
    print("받은 줄 수:", len(raw))
    table = make_table(raw)
    daily = signals_by_day(table)[["날짜", "DO", "수온", "신호"]]
    print(daily.to_string(index=False, float_format="%.2f"))  # 소수 둘째 자리까지
    print("마지막 날 신호:", *get_signal(table))
