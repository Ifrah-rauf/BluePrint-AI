from graph import generate_design
import streamlit as st

st.title("AI-powered Software Design Assistant")

user_input = st.chat_input("Describe what you want to design")

if user_input:
    result = generate_design(user_input)
    st.write(result)

    st.image(result.get_graph().draw_mermaid_png())