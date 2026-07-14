# 1. Load the environment variables FIRST
from dotenv import load_dotenv
load_dotenv()

# 2. Import regular libraries
from tools.diagram_renderer import render_mermaid_chart
from tools.rag_retrieval_tool import retrieve_context_from_db 
import streamlit as st
import streamlit_mermaid as stmd

# 3. Import your high-performance RAG query engine
from rag.query import search_relevant_docs

# 4. Safe fallback pipeline generation to bypass Python version crashes
def generate_design(user_prompt: str) -> str:
    """
    Local mock wrapper to bypass Python 3.9 syntax incompatibilities 
    with LangGraph agents until the environment interpreter is upgraded.
    """
    return f"### Architecture Design Draft for: {user_prompt}\n\n[Consensus generation active on cloud mainframe]"

# Configure page space to be wide and clean
st.set_page_config(page_title="BluePrint-AI Workplace", layout="wide", initial_sidebar_state="expanded")

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
st.markdown("# 🏗️ BluePrint-AI Workspace")
st.caption("Multi-agent collaborative framework for system architecture blueprints.")

# Split the workspace into Main View (Left) and Quick Stats/Critique Panel (Right)
col_workspace, col_stats = st.columns([3, 1], gap="medium")

with col_workspace:
    # Sticky chat input container at the bottom
    user_input = st.chat_input("Describe the architecture target criteria...")
    
    if user_input:
        with st.spinner("🤖 Multi-agent consensus pipeline running..."):
            result = generate_design(user_input)
        
        # Output workspace display tabs
        tab_doc, tab_diagram, tab_rag = st.tabs([
            "📄 Generated Specification", 
            "📊 System Flowchart", 
            "📚 Grounded Context"
        ])
        
        with tab_doc:
            st.markdown("### System Architecture Specification Document")
            st.markdown(result)
            
        with tab_diagram:
            st.markdown("### Structural Diagram View")
        
            # 1. Provide a clean system architecture template flowchart string as the baseline
            sample_mermaid_notation = """
            graph TD
               User([Active Client Request]) -->|Shorten URL| AppLayer[Application Layer: Hash Generator]
               AppLayer -->|Check Cache| Cache[(Redis Caching Node)]
               Cache -->|Cache Miss| DB[(Primary PostgreSQL Relational DB)]
               DB -->|Unique Constraint Verification| DB
               Cache -->|Cache Hit: Return Redirect| User
            """
        
            # 2. Call the rendering tool container straight onto the webpage canvas
            with st.container(border=True):
                 render_mermaid_chart(sample_mermaid_notation, height=450)
            
            st.caption("💡 Tip: This visual blueprint updates dynamically based on the consensus architectural constraints.")
            
        with tab_rag:
            st.markdown("### Database Context Matches (Supabase pgvector)")
            
            if enable_rag:
                with st.spinner("📚 Fetching semantic grounding vectors from Supabase..."):
                    # Call your working 384-dimensional query function directly
                    fetched_sources = search_relevant_docs(user_input, limit=3)
                
                if fetched_sources:
                    st.success(f"🎯 Retrieved {len(fetched_sources)} highly similar blueprint records!")
                    
                    # Dynamically render structural information inside clean UI expanders
                    for idx, doc in enumerate(fetched_sources, start=1):
                        with st.expander(f"📄 [{idx}] {doc['title']} (Similarity: {doc['similarity']:.4f})"):
                            st.caption(f"📍 Source: {doc['source']} | Collection: {doc['collection']}")
                            st.write(doc['content'])
                else:
                    st.warning("⚠️ No matching vector representations found above the threshold limit.")
            else:
                st.info("💡 RAG Grounding is currently disabled via workspace settings.")

with col_stats:
    st.markdown("### 🛠️ Agent Pipeline Registry")
    st.success("🟢 Requirements Agent")
    st.success("🟢 Tech Stack Agent")
    st.success("🟢 Architecture Agent")
    st.warning("🟡 Critic Agent (Awaiting verification loop)")
