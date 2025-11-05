import streamlit as st

st.title("⚡ Energy & Weather Dashboard")
st.markdown("""
Welcome! This dashboard provides interactive analysis of energy production and weather data.  
Navigate through the pages using the sidebar:

1. **Energy Production Overview**  
   Explore hourly electricity production by price area and production group.  
   - Pie chart: Total production per price area.  
   - Line chart: Hourly production trends by group and month.  

2. **STL & Spectrogram Analysis (NewA)**  
   Analyze time series patterns in energy production:  
   - **STL Decomposition**: Trend, seasonal, and residual components.  
   - **Spectrogram**: Frequency content over time.  

3. **ERA5 Weather: First Month Overview**  
   Inspect the first month (January) of historical weather data for selected cities:  
   - Hourly temperature, precipitation, and wind.  
   - Interactive line charts per variable.  

4. **Weather Data Visualization (Page3)**  
   Flexible plotting of ERA5 weather data:  
   - Select variables and months.  
   - Plot multiple variables or a single variable over time.  

5. **Outlier & Anomaly Analysis (NewB)**  
   Detect unusual weather events for selected cities and years:  
   - **Temperature**: Outliers via DCT + SPC.  
   - **Precipitation**: Anomalies via Local Outlier Factor (LOF).  

6. **Optional Page**  
   Additional analyses or experiments can be added here.
""")

# Added a nice picture (Chose a nice nightsky)
st.image(
    "https://images.unsplash.com/photo-1503264116251-35a269479413?auto=format&fit=crop&w=1200&q=80",
    use_container_width=True
)

st.markdown("---")
st.info("Use the sidebar to navigate between different pages of the dashboard :)")

