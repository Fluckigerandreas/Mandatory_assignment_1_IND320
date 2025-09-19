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
This app allows you to explore weather patterns, track historical data, and make insightful visualizations.  

Navigate through the pages to:
- **Overview**: See key statistics and trends
- **Temperature Analysis**: Explore daily and monthly temperature trends
- **Precipitation Insights**: Analyze rainfall and snowfall patterns
- **Forecasting**: Predict future weather trends
- **Data Explorer**: Dive into raw weather datasets
""")

# Optional image or GIF for aesthetic front page
st.image("https://images.unsplash.com/photo-1503264116251-35a269479413?auto=format&fit=crop&w=1200&q=80",
         use_column_width=True)

st.markdown("---")
st.info("Use the sidebar to navigate between different pages of the dashboard.")

# Sidebar navigation hint
st.sidebar.title("Navigation")
st.sidebar.info("""
Click on the pages below to explore weather data:
- Overview
- Temperature Analysis
- Precipitation Insights
- Forecasting
- Data Explorer
""")

