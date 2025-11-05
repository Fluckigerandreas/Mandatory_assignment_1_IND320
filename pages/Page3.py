# 3_Weather_Plot.py
# 3_Weather_Plot.py
import streamlit as st
import pandas as pd
import altair as alt
import requests

st.set_page_config(page_title="Weather Data Plot", page_icon="📈")
st.title("📊 Weather Data Visualization")

# --- City definitions ---
cities = [
    {"city": "Oslo", "lat": 59.9139, "lon": 10.7522},
    {"city": "Kristiansand", "lat": 58.1467, "lon": 7.9956},
    {"city": "Trondheim", "lat": 63.4305, "lon": 10.3951},
    {"city": "Tromsø", "lat": 69.6492, "lon": 18.9553},
    {"city": "Bergen", "lat": 60.3913, "lon": 5.3221},
]

# --- Function to fetch ERA5 weather data ---
@st.cache_data
def load_data_api(lat, lon, year=2021, timezone="Europe/Oslo"):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "hourly": ["temperature_2m","precipitation","wind_speed_10m","wind_gusts_10m","wind_direction_10m"],
        "models": "era5",
        "timezone": timezone
    }
    r = requests.get(url, params=params)
    data = r.json()["hourly"]
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    df["month"] = df["time"].dt.to_period("M")  # helper column
    return df

# --- Sidebar controls ---
st.sidebar.header("Controls")
city_option = st.sidebar.selectbox("Select city:", [c["city"] for c in cities])
selected_city = next(c for c in cities if c["city"] == city_option)

# --- Load data from API ---
df = load_data_api(selected_city["lat"], selected_city["lon"])

# --- Variable selection ---
columns = ["All"] + list(df.columns[1:-1])  # skip 'time' and 'month'
selected_column = st.sidebar.selectbox("Select variable:", columns)

# --- Month range slider ---
unique_months = df['month'].unique().astype(str).tolist()
month_range = st.sidebar.select_slider(
    "Select months:",
    options=unique_months,
    value=(unique_months[0], unique_months[0])
)
start, end = pd.Period(month_range[0]), pd.Period(month_range[1])
filtered_df = df[(df['month'] >= start) & (df['month'] <= end)]

# --- Plotting ---
st.subheader("Weather Data Plot")

if selected_column == "All":
    chart_data = filtered_df.melt(
        id_vars=["time"], 
        value_vars=df.columns[1:-1], 
        var_name="Variable", 
        value_name="Value"
    )
    chart = (
        alt.Chart(chart_data)
        .mark_line()
        .encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y("Value:Q", title="Value"),
            color="Variable:N",
            tooltip=["time:T", "Variable:N", "Value:Q"]
        )
        .properties(width=800, height=400, title="All Weather Variables")
    )
else:
    chart = (
        alt.Chart(filtered_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y(f"{selected_column}:Q", title=selected_column),
            tooltip=["time:T", f"{selected_column}:Q"]
        )
        .properties(width=800, height=400, title=f"{selected_column} over Time")
    )

st.altair_chart(chart, width='stretch')  # updated per Streamlit deprecation
