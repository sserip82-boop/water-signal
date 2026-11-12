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
    # 주황: DO가 이틀 연속 내려가고, 내려가는 양이 커진다(0.25 → 1.0). 수온은 그대로
    check("주황", do_values=[9.0, 8.75, 7.75], temp_values=[25.0, 25.0, 25.0], expected="주황"),
    # 주황과 노랑이 겹치면 주황 (DO는 0.5 → 1.5로 빨라지고, 수온도 계속 오름)
    check("주황이 노랑보다 먼저", do_values=[9.0, 8.5, 7.0], temp_values=[26.0, 27.0, 28.0], expected="주황"),
]


def check_speed(name, do_values, expected_a, expected_b):
    """속도 규칙 A, B가 기대한 대로 켜지는지 확인한다. (수온은 쓰지 않는다)"""
    table = make_fake_table(do_values, [25.0] * len(do_values))
    a = analysis.is_fast_drop(table, TEST_LIMIT)
    b = analysis.is_speeding_up(table)
    ok = (a == expected_a) and (b == expected_b)
    mark = "통과" if ok else "실패"
    print(f"[{mark}] {name}: 규칙A {a} (기대 {expected_a}) / 규칙B {b} (기대 {expected_b})")
    return ok


# ★ 시험에만 쓰는 가짜 기준 숫자. 진짜 기준(config.FAST_DROP_LIMIT)은 아직 안 정했다.
TEST_LIMIT = 1.5

results += [
    # 천천히 같은 양씩 떨어짐(0.5, 0.5): 둘 다 꺼짐
    check_speed("천천히 하락", [9.0, 8.5, 8.0], expected_a=False, expected_b=False),
    # 하루에 크게 떨어짐(0, 2.0): A만 켜짐 (어제는 안 떨어졌으니 B는 꺼짐)
    check_speed("하루 급락", [9.0, 9.0, 7.0], expected_a=True, expected_b=False),
    # 조금씩이지만 점점 더 많이 떨어짐(0.25, 1.0): B만 켜짐
    check_speed("점점 빨라짐", [9.0, 8.75, 7.75], expected_a=False, expected_b=True),
    # 점점 빨라지면서 크게 떨어짐(0.5, 2.0): 둘 다 켜짐
    check_speed("빨라지며 급락", [9.0, 8.5, 6.5], expected_a=True, expected_b=True),
    # DO가 오름: 둘 다 꺼짐
    check_speed("상승", [7.0, 8.0, 9.0], expected_a=False, expected_b=False),
    # 어제 값이 비어 있음: 판단할 수 없으니 둘 다 꺼짐
    check_speed("빈 값", [9.0, None, 6.0], expected_a=False, expected_b=False),
]

print("결과:", results.count(True), "개 통과 /", len(results), "개 중")
if not all(results):
    raise SystemExit(1)  # 하나라도 실패하면 실패로 끝낸다
