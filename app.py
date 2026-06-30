# Streamlit entry point
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from pipeline import generate_design

user_input = st.chat_input("Describe what you want to design")
if user_input:
    result = generate_design(user_input)  # same function as above
    st.write(result)