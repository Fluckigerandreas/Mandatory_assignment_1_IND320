# app.py (Front Page)
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Weather Insights Dashboard",
    page_icon="🌤️",
    layout="wide"
)

# Front-page content
st.title("🌦️ Weather Insights Dashboard")
st.subheader("Explore, Analyze, and Visualize Weather Data")

st.markdown("""
Welcome to the Weather Insights Dashboard!  
This Streamlit-app allows you to explore weather patterns, track historical data (from 2020), and make insightful visualizations.  
""")

# Optional image or GIF for aesthetic front page (Chose a nice nightsky)
st.image(
    "https://images.unsplash.com/photo-1503264116251-35a269479413?auto=format&fit=crop&w=1200&q=80",
    use_container_width=True
)

st.markdown("---")
st.info("Use the sidebar to navigate between different pages of the dashboard :)")

