import streamlit as st


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


def is_authenticated():
    return "auth_user" in st.session_state