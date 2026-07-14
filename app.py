from graph import generate_design
import streamlit as st

st.set_page_config(
    page_title="AI-powered Software Design Assistant",
    layout="wide"
)

st.title("🤖 AI-powered Software Design Assistant")

user_input = st.chat_input("Describe what you want to design")

if user_input:

    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):

        with st.spinner("Generating system design..."):
            result = generate_design(user_input)
            st.write(result.keys())
            st.json(result)

        st.success("Design generated successfully!")

        # ---------------- Requirements ----------------
        st.subheader("Functional Requirements")
        for req in result["requirements"]["functional_requirements"]:
            st.markdown(f"- {req}")

        # ---------------- Tech Stack ----------------
        st.subheader("Technology Stack")
        for item in result["techstack"]["stack"]:
            st.markdown(
                f"**{item['component']}** → {item['choice']}"
            )

        # ---------------- Architecture ----------------
        with st.expander("🏗️ Architecture", expanded=True):
            st.json(result["architecture"])

        # ---------------- Critic ----------------
        with st.expander("🧐 Critic Verdict", expanded=False):
            st.json(result["critic_verdict"])

        # ---------------- Critic History ----------------
        with st.expander("📝 Critic History", expanded=False):
            st.json(result["critic_history"])

        # ---------------- Diagram ----------------
        with st.expander("📈 Mermaid Diagram", expanded=True):
            st.code(
                result["diagram"]["mermaid_diagram"],
                language="text",
            )

        # ---------------- Complete State ----------------
        with st.expander("🔍 Complete Graph State", expanded=False):
            st.json(result)