# account.py — 회원가입·로그인·로그아웃·탈퇴를 Supabase에 부탁하는 파일 (5차 A단계)
# 비밀번호는 Supabase가 암호화해서 보관한다. 이 파일은 비밀번호를 저장하거나 출력하지 않는다.
# 아이디는 '아이디@users.water-signal.invalid' 꼴의 이메일로 바꿔 보낸다(.invalid는 실제로 없는 주소).
import re
import time
import tomllib

import requests

import api

DOMAIN = "@users.water-signal.invalid"
PASSWORD_MIN = 8  # 비밀번호 최소 글자 수 (학생이 바꿔 볼 수 있는 숫자)


def settings():
    """Supabase 주소와 공개용 키. (secrets.toml 또는 Streamlit 비밀 보관함)"""
    if api.SECRETS_FILE.exists():
        with open(api.SECRETS_FILE, "rb") as f:
            s = tomllib.load(f)
    else:
        import streamlit as st
        s = st.secrets
    return s["SUPABASE_URL"], s["SUPABASE_ANON_KEY"]


def headers(token=None):
    """요청에 붙이는 머리말. 로그인했으면 출입증(token)도 붙인다."""
    url, key = settings()
    head = {"apikey": key, "Content-Type": "application/json"}
    if token:
        head["Authorization"] = f"Bearer {token}"
    return url, head


def check_new(username, password, password2, nickname, age14):
    """가입 전에 우리 쪽에서 먼저 확인한다. 문제가 있으면 쉬운 말, 없으면 None."""
    if not re.fullmatch(r"[a-z0-9]{4,20}", username):
        return "아이디는 영어 소문자와 숫자로 4~20자여야 해요."
    if not 2 <= len(nickname) <= 12:
        return "별명은 2~12자여야 해요."
    if len(password) < PASSWORD_MIN:
        return f"비밀번호는 {PASSWORD_MIN}자 이상이어야 해요."
    if password != password2:
        return "비밀번호 두 칸이 서로 달라요."
    if not age14:
        return "만 14세 이상만 가입할 수 있어요."
    return None


def easy_message(response):
    """Supabase의 오류를 쉬운 말로 바꾼다. (오류 원문은 화면에 보여 주지 않는다)"""
    text = response.text
    if "user_already_exists" in text:
        return "이미 있는 아이디예요. 다른 아이디를 골라 주세요."
    if "invalid_credentials" in text:
        return "아이디나 비밀번호가 맞지 않아요."
    if "weak_password" in text:
        return "비밀번호가 너무 쉬워요. 더 길고 어렵게 만들어 주세요."
    if response.status_code == 429:
        return "요청이 너무 많아요. 잠시 뒤 다시 해 주세요."
    return "잠시 문제가 생겼어요. 조금 뒤 다시 해 주세요."


def signup(username, password, nickname):
    """회원가입. 돌려주는 것: (성공했나, 안내 문장)"""
    url, head = headers()
    r = requests.post(f"{url}/auth/v1/signup", headers=head, timeout=20, json={
        "email": username + DOMAIN, "password": password,
        "data": {"username": username, "nickname": nickname, "age14": True}})
    if r.ok:
        return True, f"가입했어요! 이제 '{username}'(으)로 로그인해 주세요."
    return False, easy_message(r)


def login(username, password):
    """로그인. 돌려주는 것: (회원 정보 사전 또는 None, 안내 문장)"""
    url, head = headers()
    r = requests.post(f"{url}/auth/v1/token?grant_type=password", headers=head, timeout=20,
                      json={"email": username + DOMAIN, "password": password})
    if not r.ok:
        return None, easy_message(r)
    data = r.json()
    meta = data["user"].get("user_metadata", {})
    user = {"username": username, "nickname": meta.get("nickname", username),
            "id": data["user"]["id"]}
    keep_tokens(user, data)
    user["is_admin"] = is_admin(user["token"])
    return user, f"{user['nickname']}님, 반가워요!"


def keep_tokens(user, data):
    """출입증(1시간짜리)과, 출입증을 다시 받을 때 쓰는 교환권을 저장한다."""
    user["token"] = data["access_token"]
    user["refresh"] = data["refresh_token"]
    user["expires_at"] = time.time() + data["expires_in"] - 60  # 1분 일찍 바꾼다


def valid_token(user):
    """쓸 수 있는 출입증을 돌려준다. 시간이 다 됐으면 교환권으로 새로 받는다. 실패하면 None."""
    if time.time() < user["expires_at"]:
        return user["token"]
    url, head = headers()
    r = requests.post(f"{url}/auth/v1/token?grant_type=refresh_token", headers=head,
                      timeout=20, json={"refresh_token": user["refresh"]})
    if not r.ok:
        return None
    keep_tokens(user, r.json())
    return user["token"]


def is_admin(token):
    """지금 로그인한 사람이 관리자인가? (Supabase에 물어본다)"""
    url, head = headers(token)
    r = requests.post(f"{url}/rest/v1/rpc/is_admin", headers=head, timeout=20, json={})
    return r.ok and r.json() is True


def logout(token):
    """로그아웃: Supabase에 출입증을 반납한다. 실패해도 화면에서는 로그아웃된다."""
    url, head = headers(token)
    try:
        requests.post(f"{url}/auth/v1/logout", headers=head, timeout=20)
    except requests.RequestException:
        pass


def delete_account(token):
    """탈퇴: 내 계정과 내 글을 지운다. 돌려주는 것: 성공했나"""
    url, head = headers(token)
    r = requests.post(f"{url}/rest/v1/rpc/delete_my_account", headers=head, timeout=20, json={})
    return r.ok
