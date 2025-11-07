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
from scipy.signal import butter, filtfilt
import plotly.graph_objects as go

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
# TEMPERATURE OUTLIERS (Highpass–Lowpass Filter + Trend SPC)
# ======================================================
def detect_temperature_outliers_filter(df, temp_col="temperature_2m", cutoff_hours=400,
                                       sample_rate_hours=1, n_std=2.0):
    s = df[temp_col].dropna().sort_index()
    x = s.values.astype(float)

    # --- Define cutoff frequency (normalized) ---
    nyquist = 0.5 / sample_rate_hours
    cutoff_freq = 1 / cutoff_hours  # convert period (hours) → frequency (1/hour)
    normal_cutoff = cutoff_freq / nyquist

    # --- Low-pass Butterworth filter to estimate the trend ---
    b, a = butter(N=4, Wn=normal_cutoff, btype="low", analog=False)
    trend = filtfilt(b, a, x)

    # --- High-pass (detrended) residuals ---
    residual = x - trend

    # --- Local SPC boundaries around the trend ---
    sigma_hat = 1.4826 * np.median(np.abs(residual - np.median(residual)))  # robust std estimate
    upper = trend + n_std * sigma_hat
    lower = trend - n_std * sigma_hat

    # --- Detect outliers ---
    mask = (x > upper) | (x < lower)
    outliers = pd.DataFrame({"temperature": x[mask]}, index=s.index[mask])

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(s.index, x, lw=0.8, label="Temperature (°C)", alpha=0.8)
    ax.plot(s.index, trend, color="black", lw=1.2, label="Low-pass trend")
    ax.fill_between(s.index, lower, upper, color="orange", alpha=0.2,
                    label=f"SPC limits (±{n_std:.1f}σ)")
    ax.scatter(outliers.index, outliers["temperature"], color="red", s=12, zorder=5,
               label=f"Outliers ({len(outliers)})")

    ax.set_title("Temperature Outliers (Highpass–Lowpass + Trend-following SPC)")
    ax.legend()
    plt.tight_layout()
    st.pyplot(fig)

    return outliers

# ======================================================
# LOF PRECIPITATION ANOMALIES
# ======================================================
def detect_precipitation_lof(df, precip_col="precipitation", proportion=0.01):
    """
    Detect extreme precipitation anomalies using LOF on non-zero values.
    """
    p = df[precip_col].fillna(0).sort_index()

    # --- Only consider non-zero precipitation values ---
    nonzero_mask = p.values > 0
    X_nonzero = np.log1p(p.values[nonzero_mask]).reshape(-1, 1)  # log-transform

    if len(X_nonzero) == 0:
        st.warning("No non-zero precipitation values to analyze.")
        return pd.DataFrame(columns=[precip_col])

    # --- Fit LOF ---
    lof = LocalOutlierFactor(n_neighbors=20)
    lof.fit(X_nonzero)

    scores = -lof.negative_outlier_factor_
    threshold = np.quantile(scores, 1 - proportion)
    outlier_mask = scores > threshold

    # Map anomalies back to original index
    outliers = pd.DataFrame(
        {precip_col: p.values[nonzero_mask][outlier_mask]},
        index=p.index[nonzero_mask][outlier_mask]
    )

    # --- Interactive Plotly chart ---
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=p.index, y=p.values,
        mode="lines",
        name="Precipitation (mm)",
        line=dict(width=1.2, color="blue"),
        hovertemplate="%{x}<br>Precip: %{y:.2f} mm<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=outliers.index, y=outliers[precip_col],
        mode="markers",
        name=f"LOF anomalies ({len(outliers)})",
        marker=dict(color="red", size=6, line=dict(width=1, color="darkred")),
        hovertemplate="Outlier<br>%{x}<br>Precip: %{y:.2f} mm<extra></extra>"
    ))
    fig.update_layout(
        title=f"Extreme Precipitation Anomalies (LOF, proportion={proportion:.3f})",
        xaxis_title="Time",
        yaxis_title="Precipitation (mm)",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.5)"),
        height=450,
    )

    st.plotly_chart(fig, use_container_width=True)
    return outliers

# ======================================================
# STREAMLIT PAGE
# ======================================================
st.title("New B: Outlier & Anomaly Analysis")

city_name = st.selectbox("Select city", [c["city"] for c in price_areas])
city_info = next(c for c in price_areas if c["city"] == city_name)
year = st.number_input("Select year", min_value=2000, max_value=2025, value=2021)

weather_df = download_era5_openmeteo(city_info["latitude"], city_info["longitude"], year)
st.write(f"✅ Loaded weather data for {city_name} ({len(weather_df)} rows)")

# Tabs
tab1, tab2 = st.tabs(["Temperature Outliers (SPC)", "Precipitation Anomalies (LOF)"])

with tab1:
    st.header("Temperature Outliers (DCT + SPC)")
    n_std = st.number_input("Number of standard deviations", min_value=0.1, value=2.0, step=0.1)
    cutoff_hours = st.number_input("Cutoff hours for DCT smoothing", min_value=1, value=400, step=1)
    temp_outliers = detect_temperature_outliers_filter(weather_df, cutoff_hours=cutoff_hours, n_std=n_std)
    st.write(f"Total outliers detected: {len(temp_outliers)}")
    st.dataframe(temp_outliers.head(20))

with tab2:
    st.header("Precipitation Anomalies (LOF)")
    proportion = st.slider(
        "Proportion of anomalies",
        min_value=0.001, max_value=0.1, value=0.01, step=0.005
    )
    precip_outliers = detect_precipitation_lof(weather_df, proportion=proportion)
    st.write(f"**Total anomalies detected:** {len(precip_outliers)}")
    st.dataframe(precip_outliers.head(20))
