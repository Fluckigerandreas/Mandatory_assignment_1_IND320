import streamlit as st
from pathlib import Path

image_path = Path(__file__).parent / "a9my9i.jpg"
st.image(str(image_path), caption="", use_container_width=True)