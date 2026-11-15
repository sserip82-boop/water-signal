# board_tab.py — "공지사항"과 "게시판" 탭 화면 (5차 B단계)
import datetime as dt
import re

import streamlit as st

import account
import board

KST = dt.timezone(dt.timedelta(hours=9))


def plain(text):
    """글을 '글자 그대로' 보여 주려고 꾸밈 기호(링크·그림·굵게 등)를 무력하게 만든다."""
    escaped = re.sub(r"([\\`*_{}\[\]()#+\-.!|>~<:$])", r"\\\1", text)
    return escaped.replace("\n", "  \n")  # 줄바꿈은 그대로 살린다


def when(stamp):
    """'2026-11-15T04:14:44+00:00' → '11월 15일 13:14' (한국 시간)"""
    return dt.datetime.fromisoformat(stamp).astimezone(KST).strftime("%m월 %d일 %H:%M")


def token_or_warn(user):
    """글을 쓰거나 지울 때 쓸 출입증. 로그인이 풀렸으면 안내하고 None."""
    token = account.valid_token(user)
    if token is None:
        st.warning("로그인이 풀렸어요. 로그인 탭에서 다시 로그인해 주세요.")
    return token


def write_form(table, user, label):
    """제목·내용을 받아 글을 쓴다."""
    with st.form(f"{table}_form", clear_on_submit=True):
        title = st.text_input("제목 (50자까지)").strip()
        body = st.text_area("내용 (2,000자까지)", height=150).strip()
        if not st.form_submit_button(label, type="primary"):
            return
    problem = board.check_text(title, body)
    if problem:
        st.error(problem)
        return
    token = token_or_warn(user)
    if token and board.add(table, token, title, body):
        st.success("올렸어요!")
    elif token:
        st.error("올리지 못했어요. 잠시 뒤 다시 해 주세요.")


def delete_button(table, user, row):
    """지우기 버튼. 누르면 지우고 화면을 다시 그린다."""
    if not st.button("🗑️ 지우기", key=f"del_{table}_{row['id']}"):
        return
    token = token_or_warn(user)
    if token and board.remove(table, token, row["id"]):
        st.rerun()
    elif token:
        st.error("지우지 못했어요.")


def show_row(table, row, writer, can_delete, user):
    """글 하나를 상자에 담아 보여 준다."""
    with st.container(border=True):
        st.markdown(f"**{plain(row['title'])}**")
        st.caption(f"{plain(writer)} · {when(row['created_at'])}")
        st.markdown(plain(row["body"]))
        if can_delete:
            delete_button(table, user, row)


def page_number(key):
    """몇 번째 쪽을 볼지. (처음은 1쪽)"""
    return st.number_input("쪽", min_value=1, value=1, step=1, key=key) - 1


def show_notices(user):
    """'공지사항' 탭 전체."""
    st.markdown("##### 📢 공지사항")
    st.caption("앱을 만든 사람이 쓰는 소식이에요. 누구나 읽을 수 있어요.")
    admin = bool(user and user["is_admin"])
    if admin:
        with st.expander("✏️ 공지 쓰기 (관리자)"):
            write_form("notices", user, "공지 올리기")
    try:
        rows = board.list_notices(page_number("notice_page"))
    except Exception:  # 오류 내용에 키가 섞일 수 있어서 그대로 보여 주지 않는다
        st.error("공지를 불러오지 못했어요. 잠시 뒤 다시 열어 주세요.")
        return
    if not rows:
        st.info("아직 공지가 없어요.")
    for row in rows:
        show_row("notices", row, "관리자", admin, user)


def show_posts(user):
    """'게시판' 탭 전체."""
    st.markdown("##### 💬 게시판")
    st.caption("앱을 써 본 의견이나 궁금한 점을 남겨 주세요. 읽기는 누구나, 쓰기는 회원만 할 수 있어요.")
    st.warning("이름, 학교, 전화번호, 사는 곳 같은 개인정보는 쓰지 마세요.")
    if user:
        with st.expander("✏️ 글쓰기"):
            write_form("posts", user, "글 올리기")
    else:
        st.info("글을 쓰려면 🔐 로그인 탭에서 로그인해 주세요.")
    try:
        rows = board.list_posts(page_number("post_page"))
    except Exception:
        st.error("글을 불러오지 못했어요. 잠시 뒤 다시 열어 주세요.")
        return
    if not rows:
        st.info("아직 글이 없어요. 첫 글을 남겨 주세요!")
    for row in rows:
        nickname = (row.get("profiles") or {}).get("nickname", "알 수 없음")
        mine = bool(user and (row["user_id"] == user["id"] or user["is_admin"]))
        show_row("posts", row, nickname, mine, user)
