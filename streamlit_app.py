# app.py (Front Page)
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Weather & Energy Insights Dashboard",
    page_icon="🌤️"
)

st.markdown("""
# 🌤️ Weather & Energy Insights Dashboard

Welcome! This interactive Streamlit app lets you explore **weather data** and **energy production data** through three pages:

1. **First Month Overview** 📈  
   View imported weather data and explore trends for the first month of the year. Interactive line charts show hourly patterns for each variable.

2. **Weather Data Visualization** 📊  
   Visualize weather variables over any month range. Select individual variables or view all at once, with clear, interactive Altair line charts.

3. **Energy Production Dashboard** ⚡  
   Analyze electricity production by price area and production group. Select price areas, production groups, and months to explore both pie charts (annual totals) and line plots (monthly hourly data). Data is loaded from **MongoDB** and visualized dynamically.

Use the sidebar and interactive controls on each page to filter and customize your visualizations.
""")

# Added a nice picture (Chose a nice nightsky)
st.image(
    "https://images.unsplash.com/photo-1503264116251-35a269479413?auto=format&fit=crop&w=1200&q=80",
    use_container_width=True
)

st.markdown("---")
st.info("Use the sidebar to navigate between different pages of the dashboard :)")

