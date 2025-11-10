import streamlit as st
from PIL import Image
import requests
from io import BytesIO

st.set_page_config(page_title="NMBU Campus Ås", layout="centered")

st.title("NMBU — Campus Ås")
st.write("A simple Streamlit page that displays a picture of NMBU at Ås. You can either upload your own image or use the default one.")

# Option 1: let the user upload an image
uploaded_file = st.file_uploader("Upload an image of NMBU (optional)", type=["png", "jpg", "jpeg"]) 
if uploaded_file is not None:
    img = Image.open(uploaded_file)
    st.image(img, use_column_width=True)
else:
    # Option 2: try to load a default image from the web
    default_url = "https://www.nmbu.no/sites/default/files/2021-08/campus_aas_0.jpg"
    st.write("No upload detected — attempting to load the default campus image from NMBU.")
    try:
        resp = requests.get(default_url, timeout=10)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content))
        st.image(img, use_column_width=True)
    except Exception as e:
        st.error("Couldn't load the default image from the web.\nYou can either upload an image using the uploader above or replace `default_url` in the code with a valid image URL.")
        st.write("(error: {} )".format(e))

st.caption("Photo: NMBU / source website (replace with a local image or different URL if needed)")

# Footer with a tiny instruction
st.markdown("---")
st.write("To run: `streamlit run streamlit_nmbu_campus_Ås.py`")