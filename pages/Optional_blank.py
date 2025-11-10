import streamlit as st

st.set_page_config(page_title="NMBU Campus Ås", layout="centered")

st.title("NMBU — Campus Ås")
st.write("Here's a single picture of NMBU (Campus Ås).")

# Direct image URL (replace if you have a different image)
default_url = "https://www.nmbu.no/sites/default/files/2021-08/campus_aas_0.jpg"

# Show the image using Streamlit's built-in image loader
st.image(default_url, caption="NMBU — Campus Ås", use_column_width=True)

st.markdown("---")
st.write("To run: `streamlit run streamlit_nmbu_campus_Ås.py`")