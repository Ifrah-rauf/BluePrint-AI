from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

AUTH_REFRESH_COOKIE = "sb_refresh_token"
AUTH_REFRESH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30


def set_auth_user(user, profile):
    st.session_state["auth_user"] = user
    st.session_state["profile"] = profile


def get_auth_user():
    return st.session_state.get("auth_user")


def get_profile():
    return st.session_state.get("profile")


def clear_auth_session():
    st.session_state.pop("auth_user", None)
    st.session_state.pop("profile", None)
    st.session_state.pop("auth_restore_attempted", None)
    st.session_state.pop("auth_restore_retry_pending", None)


def is_authenticated():
    return "auth_user" in st.session_state


def get_refresh_token_cookie() -> str | None:
    try:
        cookies = st.context.cookies
    except Exception:
        return None

    return cookies.get(AUTH_REFRESH_COOKIE)


def set_refresh_token_cookie(refresh_token: str) -> None:
    cookie_name = json.dumps(AUTH_REFRESH_COOKIE)
    cookie_value = json.dumps(refresh_token)
    cookie_max_age = AUTH_REFRESH_COOKIE_MAX_AGE_SECONDS
    components.html(
        f"""
        <script>
            document.cookie = {cookie_name} + "=" + encodeURIComponent({cookie_value})
                + "; Path=/; Max-Age={cookie_max_age}; SameSite=Lax";
        </script>
        """,
        height=0,
        width=0,
    )


def clear_refresh_token_cookie() -> None:
    cookie_name = json.dumps(AUTH_REFRESH_COOKIE)
    components.html(
        f"""
        <script>
            document.cookie = {cookie_name} + "=; Path=/; Max-Age=0; SameSite=Lax";
        </script>
        """,
        height=0,
        width=0,
    )
