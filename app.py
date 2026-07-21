# 1. Load the environment variables FIRST
from dotenv import load_dotenv
load_dotenv()

import streamlit as st

# 2. Import regular libraries
from tools.diagram_renderer import render_mermaid_chart
from rag.query import fetch_attached_documents, search_relevant_docs
from rag.ingest import ingest_uploaded_files
from auth.auth import sign_in, sign_up, get_profile
from auth.session import (
    set_auth_user,
    get_auth_user,
    get_profile as session_profile,
    clear_auth_session,
    is_authenticated,
)
from graph import generate_design
from state import DesignState
from agents.intent_agent import preflight_run, is_affirmative, is_negative
from uuid import uuid4

# --- STREAMLIT PAGE CONFIG (Must be the very first Streamlit command) ---
st.set_page_config(page_title="BluePrint-AI Workplace", layout="wide", initial_sidebar_state="expanded")

if not is_authenticated():

    st.title("🔐 BluePrint-AI Login")

    tab1, tab2 = st.tabs(
        ["Login", "Create Account"]
    )

    with tab1:
        email = st.text_input(
            "Email",
            key="login_email"
        )

        password = st.text_input(
            "Password",
            type="password",
            key="login_password"
        )

        if st.button("Login"):

            try:
                response = sign_in(
                    email,
                    password
                )

                user = response.user

                profile_response = get_profile(
                    user.id
                )

                set_auth_user(
                    user,
                    profile_response.data
                )

                st.success(
                    "Login successful"
                )

                st.rerun()

            except Exception as e:
                st.error(str(e))


    with tab2:

        email = st.text_input(
            "Email",
            key="signup_email"
        )

        password = st.text_input(
            "Password",
            type="password",
            key="signup_password"
        )

        full_name = st.text_input(
            "Full Name"
        )

        organization = st.text_input(
            "Organization"
        )


        if st.button("Create Account"):

            try:

                sign_up(
                    email,
                    password,
                    full_name,
                    organization
                )

                st.success(
                    "Account created. Check email if confirmation is enabled."
                )

            except Exception as e:
                st.error(str(e))


    st.stop()
    
user = get_auth_user()
profile = session_profile()

if user is None or profile is None:
    st.error("Authentication session expired.")
    clear_auth_session()
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


def _looks_like_document_lookup(user_input: str) -> bool:
    text = user_input.lower()
    lookup_actions = (
        "look up",
        "lookup",
        "search",
        "find",
        "retrieve",
        "show",
        "summarize",
        "summarise",
        "list",
        "read",
        "inspect",
    )
    lookup_targets = (
        "document",
        "documents",
        "file",
        "files",
        "attachment",
        "attachments",
        "upload",
        "uploads",
        "pdf",
        "notes",
        "note",
        "chunk",
        "chunks",
        "context",
    )
    design_signals = (
        "architecture",
        "architectural",
        "system design",
        "design blueprint",
        "tech stack",
        "scalable",
        "service",
        "services",
        "database",
        "api",
        "gateway",
    )

    action_hits = sum(1 for term in lookup_actions if term in text)
    target_hits = sum(1 for term in lookup_targets if term in text)
    design_hits = sum(1 for term in design_signals if term in text)

    return action_hits > 0 and target_hits > 0 and design_hits == 0

# 3. Premium Styling & Fine-tuned Font Sizes
st.markdown("""
<style>
/* Global Font Tuning (Except main H1 title) */
html, body, [class*="css"], .stMarkdown p, li, span, label {
    font-size: 0.92rem !important;
}

/* Exempt the hero heading (and everything inside it) from the reset above.
   This is what was silently overriding your 3.5rem heading: Streamlit can
   re-wrap the trailing text node next to your <img> in its own <p>/<span>,
   which matches the catch-all rule directly (not by inheritance), so the
   div's inline font-size no longer applied to it. */
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

/* Whole Application Background & Dot Grid */
.stApp, [data-testid="stAppViewContainer"] {
    background-color: #FCFCFD;
    background-image:
        radial-gradient(circle, rgba(0,0,0,0.04) 1px, transparent 1px),
        radial-gradient(circle at 15% 20%, rgba(124,58,237,0.06), transparent 22%),
        radial-gradient(circle at 82% 18%, rgba(59,130,246,0.05), transparent 25%),
        radial-gradient(circle at 70% 82%, rgba(250,204,21,0.04), transparent 22%);
    background-size: 22px 22px, auto, auto, auto;
}

/* Glass Sidebar */
[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.45);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border-right: 1px solid rgba(0,0,0,.05);
}

.block-container { padding-top: 2rem; }
.stTabs { background: rgba(255,255,255,.4); border-radius: 12px; padding: 10px; }
.streamlit-expanderHeader { background: rgba(255,255,255,.5); }
[data-testid="stChatInput"] { background: rgba(255,255,255,.7); backdrop-filter: blur(15px); }

/* Premium Custom UI Components */
.spec-card {
    background: #ffffff;
    padding: 16px;
    border-radius: 8px;
    border: 1px solid #E4E7EC;
    box-shadow: 0 1px 3px rgba(16, 24, 40, 0.05);
    margin-bottom: 12px;
}
.tech-tag {
    display: inline-block;
    background: #F2F4F7;
    color: #344054;
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 500;
    font-size: 0.82rem !important;
    margin: 4px;
    border: 1px solid #D0D5DD;
}
.critic-box {
    background: #FFF9F5;
    border-left: 4px solid #FD853A;
    padding: 12px;
    border-radius: 0 8px 8px 0;
    margin-bottom: 10px;
}

/* --- Hero title (dedicated, robust rule instead of inline styling) --- */
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
    color: #101828 !important;
    font-family: sans-serif !important;
}
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR LAYOUT (Left Side Panel) ---
if "result" not in st.session_state:
    st.session_state.result = _empty_design_result()

if "lookup_result" not in st.session_state:
    st.session_state.lookup_result = None

if "generate" not in st.session_state:
    st.session_state.generate = False

if "pending_generate_prompt" not in st.session_state:
    st.session_state.pending_generate_prompt = None

if "preflight_result" not in st.session_state:
    st.session_state.preflight_result = None

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
    st.markdown("### ⚙️ Workspace Config")
    scale_option = st.selectbox("Target Architecture Scale", ["10K Users", "100K Users", "1M Users", "10M+ Users"])
    enable_rag = st.checkbox("Enable RAG Grounding (Supabase)", value=True)
    chat_mode = st.selectbox("Chat Mode", ["Auto", "Design Blueprint", "Document Lookup"], index=0)
    st.caption(f"Generate mode: {'on' if st.session_state.generate else 'off'}")

    st.divider()

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
    
    if st.button("Logout"):
        from auth.auth import sign_out

        sign_out()
        clear_auth_session()
        st.rerun()

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
                        session_id=st.session_state.session_id
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
    else:
        st.caption("No files attached yet.")

    st.markdown("#### Already attached")
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
    st.caption("💬 Design a scalable URL shortener")
    st.caption("💬 Notification engine for 10M users")

# --- MAIN CONTENT LAYOUT (Center & Right Panel) ---
# Heading now uses a dedicated class instead of inline style + !important,
# so it can't be silently re-targeted/overridden by the global font reset.
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
    if st.session_state.pending_generate_prompt:
        chat_placeholder = "Reply yes to generate the design, or no to stay in understanding mode..."
    else:
        chat_placeholder = "Describe an architecture or ask to look up attached docs..."

    user_input = st.chat_input(chat_placeholder)
if user_input:
    st.session_state.last_query = user_input

    if user_input:
        st.session_state.lookup_result = None

        if st.session_state.pending_generate_prompt and is_affirmative(user_input):
            st.session_state.generate = True
            with st.spinner("🤖 Multi-agent consensus pipeline running..."):
                st.session_state.result = generate_design(
                    st.session_state.pending_generate_prompt,
                    user_id=STATIC_USER_ID,  # static uid
                    profile_id=STATIC_PROFILE_ID,
                    session_id=st.session_state.session_id,
                )
            st.session_state.generate = False
            st.session_state.pending_generate_prompt = None
            st.session_state.preflight_result = None
        elif st.session_state.pending_generate_prompt and is_negative(user_input):
            st.session_state.pending_generate_prompt = None
            st.session_state.preflight_result = {
                "intent": "aborted",
                "understanding": "Okay, I won’t generate the design yet.",
                "generate": False,
                "question": "Tell me what you want changed or what you want me to do next.",
            }
            st.session_state.result = _empty_design_result()
        elif chat_mode == "Document Lookup" or (
            chat_mode == "Auto" and _looks_like_document_lookup(user_input)
        ):
            with st.spinner("🔎 Searching attached documents..."):
                lookup_sources = search_relevant_docs(
                    user_input,
                    limit=5,
                    user_id=STATIC_USER_ID,  # static uid
                    profile_id=STATIC_PROFILE_ID,
                )
            st.session_state.lookup_result = {
                "query": user_input,
                "sources": lookup_sources,
            }
            st.session_state.result = _empty_design_result()
        else:
            if chat_mode == "Document Lookup":
                with st.spinner("🔎 Searching attached documents..."):
                    lookup_sources = search_relevant_docs(
                        user_input,
                        limit=5,
                        user_id=STATIC_USER_ID,  # static uid
                        profile_id=STATIC_PROFILE_ID,
                    )
                st.session_state.lookup_result = {
                    "query": user_input,
                    "sources": lookup_sources,
                }
                st.session_state.result = _empty_design_result()
            else:
                with st.spinner("🧠 Understanding your request..."):
                    preflight = preflight_run(user_input)
                st.session_state.preflight_result = preflight
                st.session_state.pending_generate_prompt = user_input
                st.session_state.generate = bool(preflight.get("generate", False))
                st.session_state.result = _empty_design_result()

    res = st.session_state.result

    if st.session_state.preflight_result:
        preflight = st.session_state.preflight_result
        with st.container(border=True):
            st.markdown("### 🧠 Request Understanding")
            st.write(preflight.get("understanding") or "I understand the request.")
            question = preflight.get("question") or "Do you want me to generate the design now? (yes/no)"
            st.info(question)
            if st.session_state.pending_generate_prompt:
                st.caption("Reply `yes` to generate, or `no` to keep refining the request.")

    if st.session_state.lookup_result:
        lookup_result = st.session_state.lookup_result
        with st.container(border=True):
            st.markdown("### 🔎 Document Lookup")
            st.caption(f"Query: {lookup_result['query']}")
            sources = lookup_result.get("sources") or []
            if sources:
                st.success(f"Found {len(sources)} matching document(s).")
                for idx, doc in enumerate(sources, start=1):
                    with st.expander(
                        f"📄 [{idx}] {doc.get('title') or 'Untitled'} "
                        f"(Similarity: {doc.get('similarity', 0.0):.4f})"
                    ):
                        st.caption(
                            f"Source: {doc.get('source') or 'unknown'} | "
                            f"Collection: {doc.get('collection') or 'unknown'}"
                        )
                        st.write(doc.get("content") or "")
            else:
                st.warning("No matching documents were found for that lookup.")

    # Display workspace output tabs if engine has executed successfully
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

        with tab_diagram:
            st.markdown("### Structural Diagram View")
            if res.get("diagram") and "mermaid_diagram" in res["diagram"]:
                diagram = res["diagram"]["mermaid_diagram"]
                print(repr(diagram))

                with st.container(border=True):
                    render_mermaid_chart(diagram, height=450)
            # diagram = """
            # graph TD
            # A[Frontend] --> B[API Gateway]
            # B --> C[Backend]
            # C --> D[Database]
            # """
            # with st.container(border=True):
            #     render_mermaid_chart(diagram,height=450)
            else:
                st.info("No active diagram matrix generated for this workflow task yet.")
            st.caption("💡 Tip: This visual blueprint updates dynamically based on consensus architectural constraints.")

    with tab_rag:
        st.markdown("### Database Context Matches (Supabase pgvector)")
        if enable_rag and user_input:
            with st.spinner("📚 Fetching semantic grounding vectors from Supabase..."):
                fetched_sources = search_relevant_docs(
                    user_input,
                    limit=3,
                    user_id=USER_ID,
                    profile_id=PROFILE_ID,
                )

                if fetched_sources:
                    st.success(f"🎯 Retrieved {len(fetched_sources)} highly similar blueprint records!")
                    for idx, doc in enumerate(fetched_sources, start=1):
                        with st.expander(f"📄 [{idx}] {doc['title']} (Similarity: {doc['similarity']:.4f})"):
                            st.caption(f"📍 Source: {doc['source']} | Collection: {doc['collection']}")
                            st.write(doc['content'])
                else:
                    st.warning("⚠️ No matching vector representations found above the threshold limit.")
            else:
                st.info("💡 RAG Grounding is currently disabled or awaiting prompt generation parameters.")

# --- RIGHT PANEL STATUS COUNTERS ---
with col_stats:
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
