import streamlit as st
from pathlib import Path
from PIL import Image

image_path = Path(__file__).parent.parent / "a9my9i.jpg"
img = Image.open(image_path)

st.image(img, caption="Overview of how project 2 has gone", use_container_width=True)