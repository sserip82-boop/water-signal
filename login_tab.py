# login_tab.py — "로그인" 탭 화면 (5차 A단계)
# 로그인한 사람의 정보는 st.session_state["user"]에 둔다. (새로 고침하면 로그아웃된다)
import streamlit as st

import account


def current_user():
    """지금 로그인한 사람. 없으면 None."""
    return st.session_state.get("user")


def login_form():
    """아이디·비밀번호를 받아 로그인한다."""
    with st.form("login_form"):
        username = st.text_input("아이디").strip()
        password = st.text_input("비밀번호", type="password")
        if not st.form_submit_button("로그인", type="primary"):
            return
    try:
        user, message = account.login(username, password)
    except Exception:  # 오류 내용에 키가 섞일 수 있어서 그대로 보여 주지 않는다
        user, message = None, "잠시 문제가 생겼어요. 조금 뒤 다시 해 주세요."
    if user is None:
        st.error(message)
        return
    st.session_state["user"] = user
    st.rerun()  # 화면을 다시 그려 '로그인됨' 화면으로 바꾼다


def signup_form():
    """회원가입: 아이디·별명·비밀번호 두 번·14세 확인."""
    with st.form("signup_form", clear_on_submit=False):
        username = st.text_input("아이디 (영어 소문자·숫자 4~20자)").strip()
        nickname = st.text_input("별명 (2~12자, 게시판에 보여요)").strip()
        password = st.text_input(f"비밀번호 ({account.PASSWORD_MIN}자 이상)", type="password")
        password2 = st.text_input("비밀번호 한 번 더", type="password")
        age14 = st.checkbox("만 14세 이상입니다.")
        st.caption("이름·이메일·전화번호는 받지 않아요. 아이디와 별명에 실명이나 학교를 쓰지 마세요.")
        if not st.form_submit_button("가입하기", type="primary"):
            return
    problem = account.check_new(username, password, password2, nickname, age14)
    if problem:
        st.error(problem)
        return
    try:
        ok, message = account.signup(username, password, nickname)
    except Exception:
        ok, message = False, "잠시 문제가 생겼어요. 조금 뒤 다시 해 주세요."
    (st.success if ok else st.error)(message)


def logged_in_view(user):
    """로그인한 뒤의 화면: 인사, 로그아웃, 탈퇴."""
    badge = " (관리자)" if user["is_admin"] else ""
    st.success(f"**{user['nickname']}**님으로 로그인했어요{badge}. 아이디: {user['username']}")
    if st.button("로그아웃"):
        account.logout(user["token"])
        del st.session_state["user"]
        st.rerun()
    with st.expander("회원 탈퇴"):
        st.write("탈퇴하면 내 아이디·별명과 **내가 쓴 글이 모두 지워지고** 되돌릴 수 없어요.")
        sure = st.checkbox("네, 탈퇴하고 내 정보와 글을 모두 지울게요.")
        if not st.button("탈퇴하기", disabled=not sure):
            return
        if account.delete_account(user["token"]):
            del st.session_state["user"]
            st.success("탈퇴했어요. 그동안 고마웠어요.")
        else:
            st.error("탈퇴하지 못했어요. 로그아웃했다가 다시 로그인한 뒤 해 주세요.")


def privacy_note():
    """개인정보 처리방침 (짧은 안내)."""
    with st.expander("개인정보 처리방침"):
        st.markdown(
            "- **받는 것**: 아이디, 별명, 비밀번호, 만 14세 이상 확인, 가입한 날, 내가 쓴 글.\n"
            "- **받지 않는 것**: 이름, 이메일, 전화번호, 나이, 학교.\n"
            "- **왜**: 게시판에 글을 쓰고 내 글을 지울 수 있게 하려고.\n"
            "- **어디에**: Supabase(서울 지역) 데이터베이스. 비밀번호는 암호화되어 아무도 원문을 볼 수 없어요.\n"
            "- **누가 보나**: 게시판에는 별명만 보여요. 아이디는 다른 사람에게 보이지 않아요.\n"
            "- **언제 지우나**: 탈퇴하면 바로 지워요. 아래 '회원 탈퇴'에서 직접 할 수 있어요.\n"
            "- **만 14세 미만**은 가입할 수 없어요. 가입하지 않아도 신호등·그래프·게시판 읽기는 모두 쓸 수 있어요.\n"
            "- 이 앱은 중학생이 공부하며 만든 참고용 앱이에요.")


def show_login():
    """'로그인' 탭 전체."""
    user = current_user()
    if user:
        logged_in_view(user)
    else:
        tab_in, tab_new = st.tabs(["로그인", "회원가입"])
        with tab_in:
            login_form()
        with tab_new:
            signup_form()
    privacy_note()
