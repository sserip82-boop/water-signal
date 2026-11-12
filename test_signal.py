# test_signal.py — 신호 규칙이 맞게 동작하는지 가짜 숫자로 확인한다
# 실행: .venv\Scripts\python.exe test_signal.py
# ★ 아래 DO, 수온 숫자를 직접 바꿔 보세요. (지금 빨강 기준값은 config.py의 DO_RED_LIMIT)
import pandas as pd

import analysis


def make_fake_table(do_values, temp_values):
    """가짜 숫자로 '하루에 한 줄' 표를 만든다. (2026-08-01부터 하루씩)"""
    days = pd.date_range("2026-08-01", periods=len(do_values))
    return pd.DataFrame({"날짜": days, "DO": do_values, "수온": temp_values})


def check(name, do_values, temp_values, expected):
    """신호를 계산해서 기대한 색과 같은지 확인하고 결과를 출력한다."""
    color, reason = analysis.get_signal(make_fake_table(do_values, temp_values))
    mark = "통과" if color == expected else "실패"
    print(f"[{mark}] {name}: 기대 {expected} / 실제 {color} — {reason}")
    return color == expected


results = [
    # 초록: DO가 오르락내리락, 기준값보다 높다
    check("초록", do_values=[8.0, 8.5, 8.2], temp_values=[25.0, 25.5, 25.2], expected="초록"),
    # 노랑: DO는 3일 계속 내려가고(9→8→7), 수온은 3일 계속 오른다(26→27→28)
    check("노랑", do_values=[9.0, 8.0, 7.0], temp_values=[26.0, 27.0, 28.0], expected="노랑"),
    # 빨강: 마지막 날 DO(3.0)가 기준값보다 낮다
    check("빨강", do_values=[8.0, 6.0, 3.0], temp_values=[26.0, 27.0, 28.0], expected="빨강"),
]

print("결과:", results.count(True), "개 통과 /", len(results), "개 중")
if not all(results):
    raise SystemExit(1)  # 하나라도 실패하면 실패로 끝낸다
