# board.py — 공지사항·게시글을 Supabase에서 읽고 쓰는 파일 (5차 B단계)
# "누가 무엇을 할 수 있나"는 Supabase 표의 규칙(RLS)이 지킨다. 여기서 막지 못해도 표가 막는다.
import requests

import account

LIST_SIZE = 20  # 한 쪽에 보여 줄 글 수 (학생이 바꿔 볼 수 있는 숫자)


def read(table, select, page=0):
    """표에서 최신 글부터 한 쪽만 읽는다. (로그인 없이도 된다)"""
    url, head = account.headers()
    params = {"select": select, "order": "created_at.desc",
              "limit": LIST_SIZE, "offset": page * LIST_SIZE}
    r = requests.get(f"{url}/rest/v1/{table}", headers=head, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def list_notices(page=0):
    """공지사항 목록."""
    return read("notices", "id,title,body,created_at", page)


def list_posts(page=0):
    """게시글 목록. 쓴 사람의 별명도 함께 가져온다."""
    return read("posts", "id,title,body,created_at,user_id,profiles(nickname)", page)


def add(table, token, title, body):
    """글 하나를 쓴다. 돌려주는 것: 성공했나"""
    url, head = account.headers(token)
    r = requests.post(f"{url}/rest/v1/{table}", headers=head, timeout=20,
                      json={"title": title, "body": body})
    return r.ok


def remove(table, token, row_id):
    """글 하나를 지운다. 돌려주는 것: 정말 지워졌나 (규칙에 막히면 0줄이 지워진다)"""
    url, head = account.headers(token)
    head["Prefer"] = "return=representation"  # 지운 줄을 돌려받아 정말 지워졌는지 본다
    r = requests.delete(f"{url}/rest/v1/{table}", headers=head, timeout=20,
                        params={"id": f"eq.{row_id}"})
    return r.ok and len(r.json()) == 1


def check_text(title, body):
    """쓰기 전에 길이를 확인한다. 문제가 있으면 쉬운 말, 없으면 None."""
    if not 1 <= len(title) <= 50:
        return "제목은 1~50자여야 해요."
    if not 1 <= len(body) <= 2000:
        return "내용은 1~2,000자여야 해요."
    return None
