import streamlit as st
import pandas as pd

st.set_page_config(page_title="First Month Weather Data")

st.title("📊 First Month Weather Data")

# --- Load Data ---
@st.cache_data
def load_data():
    df = pd.read_csv("/workspaces/blank-app/open-meteo-subset.csv")
    df['time'] = pd.to_datetime(df['time'])
    return df

df = load_data()

# --- Filter First Month ---
first_month = df[df['time'].dt.month == 1].copy()

st.subheader("Raw Imported Data")
st.dataframe(df)

# --- Display First Month with Row-wise Line Charts ---
st.subheader("First Month with Row-wise LineChartColumn")

st.data_editor(
    first_month,
    column_config={
        "temperature_2m (°C)": st.column_config.LineChartColumn(
            "Temperature (°C)", width="medium", y_min=-10, y_max=10
        ),
        "precipitation (mm)": st.column_config.LineChartColumn(
            "Precipitation (mm)", width="medium"
        ),
        "wind_speed_10m (m/s)": st.column_config.LineChartColumn(
            "Wind Speed (m/s)", width="medium"
        ),
        "wind_gusts_10m (m/s)": st.column_config.LineChartColumn(
            "Wind Gusts (m/s)", width="medium"
        ),
        "wind_direction_10m (°)": st.column_config.LineChartColumn(
            "Wind Direction (°)", width="medium"
        ),
    },
    hide_index=True,
    use_container_width=True
)