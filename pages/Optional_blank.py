import streamlit as st

st.set_page_config(page_title="NMBU Campus Ås", layout="centered")

st.title("NMBU — Campus Ås")
st.write("Here's a single picture of NMBU (Campus Ås).")

# Direct image URL from Wikimedia Commons (CC BY-SA 4.0)
image_url = "https://upload.wikimedia.org/wikipedia/commons/8/82/Veterin%C3%A6rh%C3%B8gskolen%2C_NMBU_i_%C3%85s.jpg"

st.image(image_url, caption="Veterinærbygningen — NMBU, Ås (CC BY-SA 4.0)", use_column_width=True)

