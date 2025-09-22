import streamlit as st

# --- Inject custom CSS for dark mode ---
dark_theme = """
    <style>
        .stApp {
            background-color: #0E1117;
            color: #FAFAFA;
        }
        .stSelectbox label, .stMultiSelect label, .stSlider label {
            color: #FAFAFA !important;
        }
    </style>
"""
st.markdown(dark_theme, unsafe_allow_html=True)