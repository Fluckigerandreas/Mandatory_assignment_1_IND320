# ======================================================
# NewB_single_file.py — Streamlit page
# ======================================================
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.fftpack import dct, idct
from sklearn.neighbors import LocalOutlierFactor
from scipy import signal
import requests_cache
from retry_requests import retry
import openmeteo_requests

# ======================================================
# PRICE AREAS (CITIES)
# ======================================================
price_areas = [
    {"price_area": "NO1", "city": "Oslo", "latitude": 59.9139, "longitude": 10.7522},
    {"price_area": "NO2", "city": "Kristiansand", "latitude": 58.1467, "longitude": 7.9956},
    {"price_area": "NO3", "city": "Trondheim", "latitude": 63.4305, "longitude": 10.3951},
    {"price_area": "NO4", "city": "Tromsø", "latitude": 69.6492, "longitude": 18.9553},
    {"price_area": "NO5", "city": "Bergen", "latitude": 60.3913, "longitude": 5.3221},
]
cities_df = pd.DataFrame(price_areas)

# ======================================================
# ERA5 WEATHER DATA DOWNLOAD
# ======================================================
@st.cache_data(show_spinner="Downloading weather data...")
def download_era5_openmeteo(lat, lon, year, timezone="Europe/Oslo"):
    """Download ERA5 hourly weather data from Open-Meteo."""
    cache_session = requests_cache.CachedSession(".cache", expire_after=-1)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    client = openmeteo_requests.Client(session=retry_session)

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

    response = client.weather_api(url, params=params)[0]
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

# ======================================================
# DCT + SPC TEMPERATURE OUTLIERS
# ======================================================
def detect_temperature_outliers_dct(df, temp_col="temperature_2m", cutoff_hours=24*30*6, n_std=3.5):
    s = df[temp_col].dropna().sort_index()
    x = s.values.astype(float)
    n = len(x)

    # DCT smoothing
    K = max(1, int(n / max(1, cutoff_hours)))
    X = dct(x, norm="ortho")
    low = np.zeros_like(X)
    low[:K] = X[:K]
    low_rec = idct(low, norm="ortho")

    # SPC-based limits
    satv = x - low_rec
    sigma_hat = 1.4826 * np.median(np.abs(satv - np.median(satv)))
    med_temp = np.median(x)
    lower, upper = med_temp - n_std * sigma_hat, med_temp + n_std * sigma_hat
    mask = (x < lower) | (x > upper)

    outliers = pd.DataFrame({"temperature": x[mask]}, index=s.index[mask])

    # Plot
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(s.index, x, lw=0.7, label="Temperature (°C)")
    ax.scatter(outliers.index, outliers["temperature"], color="red", s=12, label=f"Outliers ({len(outliers)})")
    ax.axhline(lower, color="orange", ls="--")
    ax.axhline(upper, color="orange", ls="--")
    ax.set_title("Temperature Outliers (DCT + SPC)")
    ax.legend()
    plt.tight_layout()
    st.pyplot(fig)

    return outliers

# ======================================================
# LOF PRECIPITATION ANOMALIES
# ======================================================
def detect_precipitation_lof(df, precip_col="precipitation", proportion=0.01):
    p = df[precip_col].fillna(0).sort_index()
    X = p.values.reshape(-1, 1)
    lof = LocalOutlierFactor(n_neighbors=min(len(p) - 1, 20), contamination=proportion)
    y_pred = lof.fit_predict(X)
    outliers = pd.DataFrame({"precipitation": p.values[y_pred == -1]}, index=p.index[y_pred == -1])

    # Plot
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(p.index, p.values, lw=0.7, label="Precipitation (mm)")
    ax.scatter(outliers.index, outliers["precipitation"], color="red", s=10, label=f"LOF anomalies ({len(outliers)})")
    ax.set_title("Precipitation Anomalies (LOF)")
    ax.legend()
    plt.tight_layout()
    st.pyplot(fig)

    return outliers

# ======================================================
# STREAMLIT PAGE
# ======================================================
st.title("New B: Outlier & Anomaly Analysis")

city_name = st.selectbox("Select city", [c["city"] for c in price_areas])
city_info = next(c for c in price_areas if c["city"] == city_name)
year = st.number_input("Select year", min_value=2000, max_value=2025, value=2019)

weather_df = download_era5_openmeteo(city_info["latitude"], city_info["longitude"], year)
st.write(f"✅ Loaded weather data for {city_name} ({len(weather_df)} rows)")

# Tabs
tab1, tab2 = st.tabs(["Temperature Outliers (SPC)", "Precipitation Anomalies (LOF)"])

with tab1:
    st.header("Temperature Outliers (DCT + SPC)")
    n_std = st.number_input("Number of standard deviations", min_value=0.1, value=3.5, step=0.1)
    cutoff_hours = st.number_input("Cutoff hours for DCT smoothing", min_value=1, value=24*30*6, step=1)
    temp_outliers = detect_temperature_outliers_dct(weather_df, cutoff_hours=cutoff_hours, n_std=n_std)
    st.write(f"Total outliers detected: {len(temp_outliers)}")
    st.dataframe(temp_outliers.head(20))

with tab2:
    st.header("Precipitation Anomalies (LOF)")
    proportion = st.slider("Proportion of anomalies", min_value=0.001, max_value=0.1, value=0.01, step=0.001)
    precip_outliers = detect_precipitation_lof(weather_df, proportion=proportion)
    st.write(f"Total anomalies detected: {len(precip_outliers)}")
    st.dataframe(precip_outliers.head(20))
