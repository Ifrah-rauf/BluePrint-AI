# 1. Load the environment variables FIRST
from dotenv import load_dotenv
load_dotenv()

import streamlit as st

# --- STREAMLIT PAGE CONFIG (Must be the very first Streamlit command) ---
st.set_page_config(page_title="BluePrint-AI Workplace", layout="wide", initial_sidebar_state="expanded")

# 2. Import regular libraries
from tools.diagram_renderer import render_mermaid_chart
from rag.query import search_relevant_docs
from graph import generate_design
from state import DesignState

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
with st.sidebar:
    st.markdown("### ⚙️ Workspace Config")
    scale_option = st.selectbox("Target Architecture Scale", ["10K Users", "100K Users", "1M Users", "10M+ Users"])
    enable_rag = st.checkbox("Enable RAG Grounding (Supabase)", value=True)

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

# Split the workspace into Main View (Left) and Quick Stats/Critique Panel (Right)
col_workspace, col_stats = st.columns([3, 1], gap="medium")

# Initialize design state
if "result" not in st.session_state:
    st.session_state.result = {
        "problem_statement": "",
        "requirements": None,
        "techstack": None,
        "architecture": None,
        "diagram": None,
        "critic_verdict": None,
        "critic_history": [],
        "revision_count": 0,
    }

with col_workspace:
    user_input = st.chat_input("Describe the architecture target criteria...")

    if user_input:
        with st.spinner("🤖 Multi-agent consensus pipeline running..."):
            st.session_state.result = generate_design(user_input)

    res = st.session_state.result

    # Display workspace output tabs if engine has executed successfully
    if res.get("requirements") or res.get("architecture"):
        tab_doc, tab_diagram, tab_rag = st.tabs([
            "📄 Generated Specification",
            "📊 System Flowchart",
            "📚 Grounded Context"
        ])

        with tab_doc:
            # Requirements Section
            st.markdown("## 🎯 System Requirements")
            if isinstance(res["requirements"], dict):
                for req_type, req_list in res["requirements"].items():
                    st.markdown(f"**{req_type.title()}**")
                    if isinstance(req_list, list):
                        for r in req_list: st.markdown(f"- {r}")
                    else:
                        st.write(req_list)
            else:
                st.write(res["requirements"])

            # Tech Stack Section
            st.markdown("## 💻 Chosen Technology Stack")
            if isinstance(res["techstack"], dict):
                html_tags = "".join([f"<span class='tech-tag'>{k}: {v}</span>" for k, v in res["techstack"].items()])
                st.markdown(f"<div>{html_tags}</div>", unsafe_allow_html=True)
            elif isinstance(res["techstack"], list):
                html_tags = "".join([f"<span class='tech-tag'>{item}</span>" for item in res["techstack"]])
                st.markdown(f"<div>{html_tags}</div>", unsafe_allow_html=True)
            else:
                st.write(res["techstack"])

            # Architecture Blueprint Section
            st.markdown("## 🏛️ Architectural Blueprint")
            if isinstance(res["architecture"], dict):
                for layer, desc in res["architecture"].items():
                    st.markdown(f"""
                    <div class="spec-card">
                        <strong>🛠️ Layer: {layer.title()}</strong><br>
                        <span style="color: #475467;">{desc}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.write(res["architecture"])

            # Critic Engine Feedback
            if res.get("critic_verdict"):
                st.markdown("## 🔍 Agentic Critic Verdict")
                st.markdown(f"""
                <div class="critic-box">
                    <strong>Review Summary:</strong><br>{res['critic_verdict']}
                </div>
                """, unsafe_allow_html=True)

            if res.get("critic_history"):
                with st.expander("⏳ Revision Changelog History"):
                    for i, review in enumerate(res["critic_history"], start=1):
                        st.markdown(f"**Iteration Revision {i}**")
                        st.write(review)

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
                    fetched_sources = search_relevant_docs(user_input, limit=3)

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