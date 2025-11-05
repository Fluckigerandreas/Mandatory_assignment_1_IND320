import streamlit as st
import pandas as pd
from datetime import datetime
import requests_cache
import openmeteo_requests
from retry_requests import retry

# --- City definitions ---
price_areas = [
    {"price_area": "NO1", "city": "Oslo", "latitude": 59.9139, "longitude": 10.7522},
    {"price_area": "NO2", "city": "Kristiansand", "latitude": 58.1467, "longitude": 7.9956},
    {"price_area": "NO3", "city": "Trondheim", "latitude": 63.4305, "longitude": 10.3951},
    {"price_area": "NO4", "city": "Tromsø", "latitude": 69.6492, "longitude": 18.9553},
    {"price_area": "NO5", "city": "Bergen", "latitude": 60.3913, "longitude": 5.3221},
]
cities_df = pd.DataFrame(price_areas)

# --- API function ---
def download_era5_openmeteo(lat, lon, year=2021, timezone="Europe/Oslo"):
    """Download ERA5 hourly data from Open-Meteo."""
    cache_session = requests_cache.CachedSession(".cache", expire_after=-1)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "hourly": [
            "temperature_2m",
            "precipitation",
            "wind_speed_10m",
            "wind_gusts_10m",
            "wind_direction_10m",
        ],
        "models": "era5",
        "timezone": timezone,
    }

    response = openmeteo.weather_api(url, params=params)[0]
    hourly = response.Hourly()

    df = pd.DataFrame(
        {
            "time": pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left",
            ),
            "temperature_2m": hourly.Variables(0).ValuesAsNumpy(),
            "precipitation": hourly.Variables(1).ValuesAsNumpy(),
            "wind_speed_10m": hourly.Variables(2).ValuesAsNumpy(),
            "wind_gusts_10m": hourly.Variables(3).ValuesAsNumpy(),
            "wind_direction_10m": hourly.Variables(4).ValuesAsNumpy(),
        }
    )
    df["time"] = df["time"].dt.tz_convert(timezone)
    df.set_index("time", inplace=True)
    return df

# --- Streamlit UI ---
st.set_page_config(page_title="First Month Overview", page_icon="📈")
st.title("Imported Data Overview")

# --- City selection ---
city_option = st.selectbox("Select city:", cities_df["city"])
selected_city = cities_df[cities_df["city"] == city_option].iloc[0]

# --- Load data from API (year fixed to 2021) ---
@st.cache_data
def load_data_api(city_info):
    df = download_era5_openmeteo(
        lat=city_info["latitude"],
        lon=city_info["longitude"],
        year=2021,
        timezone="Europe/Oslo"
    )
    df.reset_index(inplace=True)
    return df

df = load_data_api(selected_city)
st.dataframe(df)

st.title("📊 First Month Weather Overview")

# --- Filter first month (January) ---
first_month = df[df['time'].dt.month == 1].copy()

# --- Prepare data: one row per variable ---
variables = first_month.columns[1:]  # skip 'time'
chart_data = pd.DataFrame({
    "Variable": variables,
    "Values": [first_month[var].tolist() for var in variables]
})

# --- Display as table with LineChartColumn ---
st.data_editor(
    chart_data,
    column_config={
        "Values": st.column_config.LineChartColumn(
            "First Month Trend",
            width="large"
        )
    },
    hide_index=True,
    use_container_width=True
)
