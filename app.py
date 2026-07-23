# 1. Load the environment variables FIRST
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import json
import re

# 2. Import regular libraries
from tools.diagram_renderer import render_mermaid_chart
from auth.auth import (
    sign_in,
    sign_up,
    sign_out,
    get_profile,
)
from auth.session import (
    set_auth_user,
    get_auth_user,
    get_profile as session_profile,
    clear_auth_session,
    is_authenticated,
    get_refresh_token_cookie,
    set_refresh_token_cookie,
    clear_refresh_token_cookie,
)
from auth.supabase_client import supabase
from llm_client import stream_llm
from prompts import ANSWER_PROMPT
from rag.query import (
    fetch_attached_documents,
    search_relevant_docs,
    fetch_recent_blueprints,
    fetch_chat_sessions,
    save_chat_message,
    fetch_chat_messages,
    build_document_rag_context,
)
from rag.ingest import ingest_uploaded_files, save_generated_blueprint_to_db
from graph import generate_design_stream
from state import DesignState
from uuid import uuid4
from utils.report_generator import create_pdf_report

# --- STREAMLIT PAGE CONFIG (Must be the very first Streamlit command) ---
st.set_page_config(page_title="BluePrint-AI Workplace", layout="wide", initial_sidebar_state="expanded")


def _extract_session(response):
    session = getattr(response, "session", None)
    if session is not None:
        return session

    if getattr(response, "access_token", None) and getattr(response, "refresh_token", None):
        return response

    return None


def restore_auth_session_from_cookie() -> bool:
    refresh_token = get_refresh_token_cookie()
    if not refresh_token:
        return False

    try:
        response = supabase.auth.refresh_session(refresh_token)
        session = _extract_session(response)
        if session is None:
            return False

        access_token = getattr(session, "access_token", None)
        new_refresh_token = getattr(session, "refresh_token", None)

        if access_token and new_refresh_token:
            try:
                supabase.auth.set_session(access_token, new_refresh_token)
            except Exception:
                supabase.postgrest.auth(access_token)
        elif access_token:
            supabase.postgrest.auth(access_token)

        user = getattr(response, "user", None) or getattr(session, "user", None)
        if user is None:
            user_response = supabase.auth.get_user()
            user = getattr(user_response, "user", None)

        if user is None:
            return False

        profile_response = get_profile(user.id)
        set_auth_user(user, profile_response.data)

        if new_refresh_token and new_refresh_token != refresh_token:
            set_refresh_token_cookie(new_refresh_token)

        return True
    except Exception:
        clear_refresh_token_cookie()
        return False


def render_auth_gate(message: str | None = None) -> None:
    st.title("🔐 BluePrint-AI Login")
    if message:
        st.info(message)
    else:
        st.info("No active user session found. Sign in or create an account to continue.")

    if st.session_state.get("show_signup_inline"):
        st.subheader("Create Account")
        email = st.text_input("Email", key="inline_signup_email")
        password = st.text_input("Password", type="password", key="inline_signup_password")
        full_name = st.text_input("Full Name", key="inline_signup_full_name")
        organization = st.text_input("Organization", key="inline_signup_organization")

        col_create, col_back = st.columns(2)
        with col_create:
            if st.button("Create Account", key="inline_create_account"):
                try:
                    sign_up(email, password, full_name, organization)
                    st.success("Account created. Check your email if confirmation is enabled.")
                    st.session_state.show_signup_inline = False
                except Exception as e:
                    st.error(str(e))
        with col_back:
            if st.button("Back to Login", key="inline_back_to_login"):
                st.session_state.show_signup_inline = False
                st.rerun()
    else:
        st.subheader("Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        remember_me = st.checkbox("Remember me on this device", value=True, key="remember_me")

        col_login, col_signup = st.columns(2)
        with col_login:
            if st.button("Login", key="login_button"):
                try:
                    response = sign_in(
                        email,
                        password,
                        remember_me=remember_me,
                    )

                    user = response.user
                    profile_response = get_profile(user.id)
                    set_auth_user(user, profile_response.data)
                    st.success("Login successful")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        with col_signup:
            if st.button("Create Account", key="switch_to_signup"):
                st.session_state.show_signup_inline = True
                st.rerun()


refresh_token_cookie = get_refresh_token_cookie()
restore_attempted = st.session_state.get("auth_restore_attempted", False)
retry_pending = st.session_state.get("auth_restore_retry_pending", False)

if refresh_token_cookie and (not restore_attempted or retry_pending):
    st.session_state["auth_restore_attempted"] = True
    restored = restore_auth_session_from_cookie()
    if restored:
        st.session_state.pop("auth_restore_retry_pending", None)
    else:
        st.session_state["auth_restore_retry_pending"] = True

if not is_authenticated():
    render_auth_gate()
    st.stop()

user = get_auth_user()
profile = session_profile()

if user is None or profile is None:
    clear_auth_session()
    render_auth_gate("Your session is no longer valid. Sign in again or create a new account.")
    st.stop()

USER_ID = user.id
PROFILE_ID = profile["profile_id"]


def _empty_design_result() -> dict:
    return {
        "problem_statement": "",
        "requirements": None,
        "techstack": None,
        "architecture": None,
        "diagram": None,
        "critic_verdict": None,
        "critic_history": [],
        "revision_count": 0,
    }


def _is_generate_command(user_input: str) -> bool:
    text = user_input.strip().lower()
    if not text:
        return False

    command_patterns = (
        r"\bgenerate\s+(the\s+)?design\b",
        r"\bgenerate\s+(the\s+)?blueprint\b",
        r"\bgenerate\s+(the\s+)?architecture\b",
        r"\bcreate\s+(the\s+)?design\b",
        r"\bbuild\s+(the\s+)?design\b",
        r"\bmake\s+(the\s+)?design\b",
    )
    return any(re.search(pattern, text) for pattern in command_patterns)


def _is_document_request(user_input: str) -> bool:
    text = user_input.strip().lower()
    if not text:
        return False

    document_patterns = (
        r"\bread\b.*\b(file|files|document|documents|attachment|attachments)\b",
        r"\b(search|find|show|summarize|inspect|review|retrieve)\b.*\b(file|files|document|documents|attachment|attachments)\b",
        r"\b(uploaded files?)\b",
        r"\b(my|the)\s+(file|files|document|documents|attachment|attachments)\b",
    )
    return any(re.search(pattern, text) for pattern in document_patterns)


def _resolve_generation_prompt(user_input: str, fallback_prompt: str | None = None) -> str | None:
    text = user_input.strip()
    if not text:
        return fallback_prompt.strip() if fallback_prompt else None

    if not _is_generate_command(text):
        return None

    command_only = re.sub(
        r"(?i)\b(generate|create|build|make)\b\s+(?:the\s+)?(design|blueprint|architecture)\b",
        "",
        text,
    ).strip(" \t\n\r:,-")
    command_only = re.sub(r"(?i)^(?:for|about|to|of|on|with|please)\b\s*", "", command_only).strip()

    if command_only:
        return command_only

    if fallback_prompt and fallback_prompt.strip():
        return fallback_prompt.strip()

    return None


def _summarize_current_design(result: dict) -> str:
    if not result or not any(result.values()):
        return ""

    summary = {
        "problem_statement": result.get("problem_statement"),
        "requirements": result.get("requirements"),
        "techstack": result.get("techstack"),
        "architecture": result.get("architecture"),
        "diagram": result.get("diagram"),
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)


def _build_answer_context(user_input: str) -> str:
    design_context = _summarize_current_design(st.session_state.result)

    blocks = []
    if design_context:
        blocks.append("Current Design Context:\n" + design_context)
    if _is_document_request(user_input):
        rag_context = build_document_rag_context(
            user_query=user_input,
            user_id=USER_ID,
            profile_id=PROFILE_ID,
            session_id=st.session_state.session_id,
        )
        if rag_context and rag_context != "No relevant retrieved documents.":
            blocks.append("Relevant Documents:\n" + rag_context)

    return "\n\n".join(blocks)


def _answer_user_message(user_input: str) -> str:
    answer_context = _build_answer_context(user_input)
    with st.chat_message("assistant"):
        stream = stream_llm(
            ANSWER_PROMPT,
            {
                "user_input": user_input,
                "answer_context": answer_context,
            },
        )
        answer_text = st.write_stream(stream)

    if isinstance(answer_text, str):
        return answer_text.strip()

    if isinstance(answer_text, list):
        return "".join(str(part) for part in answer_text).strip()

    return ""


def _run_design_generation(prompt: str) -> None:
    if not prompt:
        st.error("No generation prompt was available.")
        return

    final_state = _empty_design_result()
    revision_pass = 0
    for update in generate_design_stream(
        prompt,
        user_id=USER_ID,
        profile_id=PROFILE_ID,
        session_id=st.session_state.session_id,
    ):
        for node_name, node_output in update.items():
            final_state.update(node_output)
            if node_name == "requirements":
                print("✅ Requirements drafted")
            elif node_name == "techstack":
                print("✅ Tech stack chosen")
            elif node_name == "architecture":
                revision_pass += 1
                label = "✅ Architecture blueprint ready" if revision_pass == 1 else f"🔁 Architecture revised (pass {revision_pass})"
                print(label)
            elif node_name == "critic":
                verdict = node_output.get("critic_verdict", {}).get("verdict", "?")
                print(f"🔍 Critic verdict: {verdict}")
            elif node_name == "diagram":
                print("✅ Diagram generated")

    st.session_state.result = final_state
    print("Design complete")

    save_chat_message(
        st.session_state.session_id,
        USER_ID,
        "assistant",
        "Design generated: requirements, tech stack, architecture, and diagram are ready."
    )
    try:
        save_generated_blueprint_to_db(
            problem_statement=prompt,
            design_result=final_state,
            user_id=USER_ID,
            profile_id=PROFILE_ID,
        )
    except Exception as e:
        st.warning(f"Design generated, but saving it to your blueprint history failed: {e}")

# 3. Dynamic & Theme-Aware Styling
st.markdown("""
<style>
/* Global Font Tuning (Except main H1 title) */
html, body, [class*="css"], .stMarkdown p, li, span, label {
    font-size: 0.92rem !important;
}

/* Exempt the hero heading from the global reset */
.hero-title, .hero-title * {
    font-size: initial !important;
}

h2 { font-size: 1.4rem !important; font-weight: 600 !important; margin-top: 1rem !important; }
h3 { font-size: 1.1rem !important; font-weight: 600 !important; }

/* Top Header, Toolbar, Decoration Cleanups */
header[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu {
    background: transparent;
}
[data-testid="stDecoration"] {
    display:none;
}

/* Dynamic App Background & Subtle Radial Grid */
.stApp, [data-testid="stAppViewContainer"] {
    background-color: var(--background-color);
    background-image:
        radial-gradient(circle, rgba(128,128,128,0.08) 1px, transparent 1px),
        radial-gradient(circle at 15% 20%, rgba(124,58,237,0.06), transparent 22%),
        radial-gradient(circle at 82% 18%, rgba(59,130,246,0.05), transparent 25%),
        radial-gradient(circle at 70% 82%, rgba(250,204,21,0.04), transparent 22%);
    background-size: 22px 22px, auto, auto, auto;
    color: var(--text-color);
}

/* Glass & Theme-Aware Sidebar */
[data-testid="stSidebar"] {
    background-color: var(--secondary-background-color);
    border-right: 1px solid rgba(128, 128, 128, 0.15);
}

.block-container { padding-top: 2rem; }
.stTabs {
    background: var(--secondary-background-color);
    border-radius: 12px;
    padding: 10px;
    border: 1px solid rgba(128, 128, 128, 0.15);
}
.streamlit-expanderHeader {
    background: var(--secondary-background-color);
    border-radius: 6px;
}
[data-testid="stChatInput"] {
    background: var(--secondary-background-color);
    border-radius: 8px;
}

/* Theme-Aware Custom UI Components */
.spec-card {
    background: var(--secondary-background-color);
    padding: 16px;
    border-radius: 8px;
    border: 1px solid rgba(128, 128, 128, 0.18);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    margin-bottom: 12px;
    color: var(--text-color);
}
.tech-tag {
    display: inline-block;
    background: var(--secondary-background-color);
    color: var(--text-color);
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 500;
    font-size: 0.82rem !important;
    margin: 4px;
    border: 1px solid rgba(128, 128, 128, 0.25);
}
.critic-box {
    background: rgba(253, 133, 58, 0.08);
    border-left: 4px solid #FD853A;
    padding: 12px;
    border-radius: 0 8px 8px 0;
    margin-bottom: 10px;
    color: var(--text-color);
}

/* --- Hero title --- */
.hero-title {
    display: flex !important;
    align-items: center !important;
    gap: 14px !important;
    margin-bottom: 0.2rem !important;
}
.hero-title-icon {
    width: 56px !important;
    height: 56px !important;
    flex-shrink: 0 !important;
}
.hero-title-text {
    font-size: 3.5rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.06rem !important;
    line-height: 1.2 !important;
    color: var(--text-color) !important;
    font-family: sans-serif !important;
}
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR LAYOUT (Left Side Panel) ---
if "result" not in st.session_state:
    st.session_state.result = _empty_design_result()

if "last_user_prompt" not in st.session_state:
    st.session_state.last_user_prompt = None

if "last_answer" not in st.session_state:
    st.session_state.last_answer = None

if "last_document_query" not in st.session_state:
    st.session_state.last_document_query = None

if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

if "upload_widget_key" not in st.session_state:
    st.session_state.upload_widget_key = 0

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid4())

attachment_lookup_error = None
try:
    attached_documents = fetch_attached_documents(
        USER_ID,
        PROFILE_ID,
    )
except Exception as e:
    attached_documents = []
    attachment_lookup_error = e

attached_file_names = {
    str(doc.get("file_name") or doc.get("source") or doc.get("title") or "").strip()
    for doc in attached_documents
    if str(doc.get("file_name") or doc.get("source") or doc.get("title") or "").strip()
}

with st.sidebar:
    # st.markdown("### ⚙️ Workspace Config")
    # scale_option = st.selectbox("Target Architecture Scale", ["10K Users", "100K Users", "1M Users", "10M+ Users"])
    # enable_rag = st.checkbox("Enable RAG Grounding (Supabase)", value=True)

    # st.divider()

    st.markdown("### 📎 Upload Files")
    if "upload_message" in st.session_state:
        st.success(st.session_state.pop("upload_message"))
    if attachment_lookup_error is not None:
        st.warning(
            "Saved attachments could not be loaded right now, so auto-ingestion is paused."
        )

    uploaded_files = st.file_uploader(
        "Attach documents once for grounding",
        type=["pdf", "txt", "md", "docx"],
        accept_multiple_files=True,
        key=f"upload_files_{st.session_state.upload_widget_key}",
        help="New files are saved immediately. If a file is already in Supabase for this account, it will be treated as already attached.",
    )

    if uploaded_files:
        st.session_state.uploaded_files = uploaded_files

    pending_files = []
    if st.session_state.uploaded_files:
        pending_files = [
            file
            for file in st.session_state.uploaded_files
            if file.name not in attached_file_names
        ]

        if pending_files and attachment_lookup_error is None:
            with st.spinner("Uploading and chunking new files..."):
                try:
                    ingest_uploaded_files(
                        pending_files,
                        user_id=USER_ID,
                        profile_id=PROFILE_ID,
                        session_id=st.session_state.session_id,
                    )
                    st.session_state.upload_message = (
                        f"Saved {len(pending_files)} new file(s) to Supabase."
                    )
                    st.session_state.uploaded_files = []
                    st.session_state.upload_widget_key += 1
                    st.rerun()
                except Exception as e:
                    st.error(f"File ingestion failed: {e}")
        elif pending_files and attachment_lookup_error is not None:
            st.info("Upload lookup is unavailable, so new files were not auto-ingested.")

        if st.session_state.uploaded_files:
            st.caption(f"{len(st.session_state.uploaded_files)} file(s) selected")
            for file in st.session_state.uploaded_files:
                if attachment_lookup_error is not None:
                    status = "status unknown"
                else:
                    status = "already attached" if file.name in attached_file_names else "new"
                st.markdown(f"- `{file.name}` ({status})")
            if st.button("Clear selection"):
                st.session_state.uploaded_files = []
                st.session_state.upload_widget_key += 1
                st.rerun()
        else:
            st.caption("No files selected right now.")

    st.markdown("#### Saved attachments")
    if attachment_lookup_error is not None:
        st.caption("Attachment history is temporarily unavailable.")
    elif attached_documents:
        for doc in attached_documents:
            file_name = doc.get("file_name") or doc.get("source") or doc.get("title") or "Untitled"
            st.markdown(f"- `{file_name}`")
    else:
        st.caption("No saved files found for this account yet.")

    st.divider()

    st.markdown("### 🕒 Recent Blueprints")
    try:
        recent_blueprints = fetch_recent_blueprints(
            user_id=USER_ID,
            profile_id=PROFILE_ID,
            limit=5,
        )
    except Exception as e:
        recent_blueprints = []

    if recent_blueprints:
        for bp in recent_blueprints:
            st.caption(f"💬 {bp['title']}")
    else:
        st.caption("No saved blueprints found in Supabase database.")

# --- MAIN CONTENT LAYOUT (Center & Right Panel) ---
st.markdown("""
<div class="hero-title">
    <img class="hero-title-icon" src="https://cdn-icons-png.flaticon.com/512/2103/2103633.png">
    <span class="hero-title-text">BluePrint-AI Workspace</span>
</div>
""", unsafe_allow_html=True)
st.caption("Multi-agent collaborative framework for system architecture blueprints.")

if st.session_state.uploaded_files:
    with st.container(border=True):
        st.markdown("### 📎 Attached Files")
        st.write("These files are attached to the current account and are available for grounding.")
        for file in st.session_state.uploaded_files:
            st.write(f"- {file.name}")

# Split the workspace into Main View (Left) and Quick Stats/Critique Panel (Right)
col_workspace, col_stats = st.columns([3, 1], gap="medium")

with col_workspace:
    latest_chat_sessions = fetch_chat_sessions(USER_ID, limit=1)
    if latest_chat_sessions:
        latest_session_id = str(latest_chat_sessions[0].get("id") or "")
        if latest_session_id:
            current_messages = fetch_chat_messages(st.session_state.session_id)
            if not current_messages:
                st.session_state.session_id = latest_session_id

    active_session_id = st.session_state.session_id
    chat_history = fetch_chat_messages(active_session_id)

    if chat_history:
        for msg in chat_history:
            with st.chat_message(msg.get("role", "user")):
                st.write(msg.get("message", ""))

    design_panel = st.container()

    chat_placeholder = "Ask a question or add 'generate design' when you want a blueprint."
    user_input = st.chat_input(chat_placeholder)

    if user_input:
        previous_prompt = st.session_state.last_user_prompt
        st.session_state.last_user_prompt = user_input
        if _is_document_request(user_input):
            st.session_state.last_document_query = user_input
        else:
            st.session_state.last_document_query = None
        save_chat_message(active_session_id, USER_ID, "user", user_input)

        with st.spinner("Processing your request..."):
            answer_text = _answer_user_message(user_input)
            st.session_state.last_answer = answer_text
            save_chat_message(
                active_session_id,
                USER_ID,
                "assistant",
                answer_text or "I do not have a direct answer for that request."
            )

        generation_prompt = _resolve_generation_prompt(user_input, fallback_prompt=previous_prompt)
        if generation_prompt:
            with st.spinner("Generating design..."):
                _run_design_generation(generation_prompt)
            st.rerun()
    res = st.session_state.result

    # Display workspace output tabs if engine has executed successfully
    with design_panel:
        if res.get("requirements") or res.get("architecture"):
            tab_doc, tab_diagram, tab_rag = st.tabs([
                "📄 Generated Specification",
                "📊 System Flowchart",
                "📚 Grounded Context"
            ])

            with tab_doc:
                # ── Requirements ────────────────────────────────────────────
                st.markdown("## 🎯 System Requirements")
                if isinstance(res.get("requirements"), dict):
                    req = res["requirements"]
                    cols = st.columns(2)
                    with cols[0]:
                        st.markdown("**Functional**")
                        for r in req.get("functional_requirements", []):
                            st.markdown(f"- {r}")
                        st.markdown(f"**Scale:** `{req.get('scale', '—')}`")
                    with cols[1]:
                        st.markdown("**Non-Functional**")
                        for r in req.get("non_functional_requirements", []):
                            st.markdown(f"- {r}")
                        if req.get("constraints"):
                            st.markdown("**Constraints**")
                            for c in req["constraints"]:
                                st.markdown(f"- {c}")
                else:
                    st.write(res.get("requirements"))

                # ── Tech Stack ───────────────────────────────────────────────
                st.markdown("## 💻 Chosen Technology Stack")
                if isinstance(res.get("techstack"), dict):
                    stack = res["techstack"].get("stack", [])
                    if stack:
                        header_cols = st.columns([2, 2, 4])
                        header_cols[0].markdown("**Component**")
                        header_cols[1].markdown("**Selected**")
                        header_cols[2].markdown("**Why**")
                        st.divider()
                        for item in stack:
                            row = st.columns([2, 2, 4])
                            row[0].markdown(f"`{item.get('component', '')}`")
                            row[1].markdown(f"**{item.get('choice', '')}**")
                            row[2].markdown(item.get('justification', ''))
                else:
                    st.write(res.get("techstack"))

                # ── Architecture ─────────────────────────────────────────────
                st.markdown("## 🏛️ Architectural Blueprint")
                if isinstance(res.get("architecture"), dict):
                    arch = res["architecture"]

                    if arch.get("design_description"):
                        st.markdown(f"> {arch['design_description']}")

                    st.markdown("### Components")
                    for comp in arch.get("components", []):
                        with st.container(border=True):
                            st.markdown(f"**{comp.get('name', '')}**")
                            st.caption(comp.get('responsibility', ''))
                            deps = comp.get("connects_to") or comp.get("depends_on") or []
                            if deps:
                                st.markdown("*Depends on:* " + " · ".join([f"`{d}`" for d in deps]))

                    if arch.get("tradeoffs"):
                        with st.expander("⚖️ Tradeoffs"):
                            for t in arch["tradeoffs"]:
                                st.markdown(f"- {t}")
                else:
                    st.write(res.get("architecture"))

                # ── Critic Verdict ───────────────────────────────────────────
                if res.get("critic_verdict"):
                    verdict = res["critic_verdict"]
                    is_approved = verdict.get("verdict") == "APPROVE"
                    st.markdown("## 🔍 Agentic Critic Verdict")
                    if is_approved:
                        st.success("✅ **Status: APPROVED**")
                    else:
                        st.error("🔴 **Status: REVISE**")
                        issues = verdict.get("issues", [])
                        if issues:
                            st.markdown("**Issues Found:**")
                            for issue in issues:
                                st.markdown(f"- {issue}")

                # ── Revision History ─────────────────────────────────────────
                if res.get("critic_history"):
                    with st.expander(f"⏳ Revision History ({len(res['critic_history'])} iterations)"):
                        for i, review in enumerate(res["critic_history"], start=1):
                            verdict_val = review.get("verdict", "")
                            icon = "✅" if verdict_val == "APPROVE" else "🔴"
                            st.markdown(f"**{icon} Iteration {i} — {verdict_val}**")
                            for issue in review.get("issues", []):
                                st.markdown(f"  - {issue}")
                            if i < len(res["critic_history"]):
                                st.divider()
                # ======================================================
                # Download Report
                # ======================================================
                st.divider()
                st.subheader("📥 Export Report")
                try:
                    res["problem_statement"] = (
                    res.get("problem_statement")
                    or st.session_state.get("last_query", "")
                    )
                    pdf_buffer = create_pdf_report(res)
                    st.download_button(
                        label="📄 Download PDF Report",
                        data=pdf_buffer,
                        file_name="BluePrint_AI_Report.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as e:
                    print(e)
                    st.warning(
                        "⚠ Unable to generate the report right now. Please try again."
                    )

            with tab_diagram:
                st.markdown("### Structural Diagram View")
                if res.get("diagram") and "mermaid_diagram" in res["diagram"]:
                    diagram = res["diagram"]["mermaid_diagram"]
                    print(repr(diagram))

                    with st.container(border=True):
                        render_mermaid_chart(diagram, height=450)
                else:
                    st.info("No active diagram matrix generated for this workflow task yet.")
                st.caption("💡 Tip: This visual blueprint updates dynamically based on consensus architectural constraints.")

            with tab_rag:
                document_query = st.session_state.last_document_query
                if document_query:
                    st.markdown("### 📚 Retrieved Documents")
                    with st.spinner("📚 Fetching matching documents from Supabase..."):
                        fetched_sources = build_document_rag_context(
                            user_query=document_query,
                            user_id=USER_ID,
                            profile_id=PROFILE_ID,
                            session_id=st.session_state.session_id,
                        )

                    if fetched_sources and fetched_sources != "No relevant retrieved documents.":
                        st.success("🎯 Matching documents found:")
                        st.markdown(fetched_sources)
                    else:
                        st.info("No matching documents found for that request.")
                else:
                    st.info("Document search results appear here only when you ask to read or search files.")

# --- RIGHT PANEL STATUS COUNTERS ---
with col_stats:
    latest_prompt = (st.session_state.last_user_prompt or "").strip()
    if st.button(
        "Generate design",
        key="generate_design_button",
        use_container_width=True,
        disabled=not bool(latest_prompt),
    ):
        if latest_prompt:
            with st.spinner("Generating design..."):
                _run_design_generation(latest_prompt)
            st.rerun()          # 👈 add this
        else:
            st.warning("Ask a question first so I have a prompt to generate from.")

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <style>
        .auth-card {{
            display: flex;
            align-items: center;
            gap: 0.8rem;
            width: 100%;
            padding: 0.9rem 1rem;
            border-radius: 16px;
            border: 1px solid rgba(128, 128, 128, 0.22);
            background: linear-gradient(135deg, rgba(17, 24, 39, 0.03), rgba(17, 24, 39, 0.06));
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.05);
            margin-bottom: 0.9rem;
            box-sizing: border-box;
        }}
        .auth-card__icon {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 2.5rem;
            height: 2.5rem;
            border-radius: 12px;
            background: rgba(34, 197, 94, 0.12);
            color: #16a34a;
            font-size: 1.2rem;
            flex: 0 0 auto;
        }}
        .auth-card__body {{
            min-width: 0;
            flex: 1 1 auto;
        }}
        .auth-card__label {{
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: rgba(128, 128, 128, 0.9);
            margin-bottom: 0.12rem;
        }}
        .auth-card__email {{
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-color);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .auth-card__subtle {{
            font-size: 0.8rem;
            color: rgba(128, 128, 128, 0.95);
            margin-top: 0.15rem;
        }}
        @media (max-width: 640px) {{
            .auth-card {{
                padding: 0.8rem 0.85rem;
                border-radius: 14px;
                gap: 0.7rem;
            }}
            .auth-card__email {{
                white-space: normal;
                word-break: break-word;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="auth-card">
            <div class="auth-card__icon">👤</div>
            <div class="auth-card__body">
                <div class="auth-card__label">Account</div>
                <div class="auth-card__email">{getattr(user, "email", "unknown")}</div>
                <div class="auth-card__subtle">Signed in</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Logout", key="logout_right_panel"):
        sign_out()
        clear_auth_session()
        st.rerun()

    st.markdown("### 📊 Status Check")
    res = st.session_state.result

    indicators = [
        ("requirements", "Requirements"),
        ("techstack", "Tech Stack"),
        ("architecture", "Architecture"),
        ("critic_verdict", "Critic Review"),
        ("diagram", "Mermaid Diagram")
    ]

    for key, label in indicators:
        if res.get(key):
            st.success(f"🟢 {label}")
        else:
            st.markdown(f"<span style='color:#98A2B3;'>⚪ {label}</span>", unsafe_allow_html=True)
