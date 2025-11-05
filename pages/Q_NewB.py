# ======================================================
# NewB.py — Streamlit page
# ======================================================
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.fftpack import dct, idct
from sklearn.neighbors import LocalOutlierFactor

# Import your previously defined functions
from NewA import download_era5_openmeteo, price_areas

# ======================================================
# Streamlit UI
# ======================================================
st.title("New B Analysis: Outliers & Anomalies")

# Select city / price area
city_name = st.selectbox("Select city for analysis", [c["city"] for c in price_areas])
city_info = next(c for c in price_areas if c["city"] == city_name)

# Select year
year = st.number_input("Select year", min_value=2000, max_value=2025, value=2019)

# Download weather data (no MongoDB needed)
@st.cache_data(show_spinner="Downloading weather data...")
def load_weather_data(lat, lon, year):
    df = download_era5_openmeteo(lat, lon, year)
    return df

weather_df = load_weather_data(city_info["latitude"], city_info["longitude"], year)
st.write(f"✅ Loaded weather data for {city_name} ({len(weather_df)} rows)")

# Tabs
tab1, tab2 = st.tabs(["Temperature Outliers (SPC)", "Precipitation Anomalies (LOF)"])

# ======================================================
# Tab 1: Temperature Outliers (DCT + SPC)
# ======================================================
with tab1:
    st.header("Temperature Outliers (DCT + SPC)")

    n_std = st.number_input("Number of standard deviations for SPC", min_value=0.1, value=3.5, step=0.1)
    cutoff_hours = st.number_input("Cutoff hours for DCT smoothing", min_value=1, value=24*30*6, step=1)

    # Function to detect temperature outliers
    def detect_temperature_outliers_dct_streamlit(df, temp_col="temperature_2m", cutoff_hours=24*30*6, n_std=3.5):
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

        # Summary statistics
        st.write(f"Total outliers detected: {len(outliers)}")
        st.dataframe(outliers.head(20))
        return outliers

    temp_outliers = detect_temperature_outliers_dct_streamlit(
        weather_df, cutoff_hours=cutoff_hours, n_std=n_std
    )

# ======================================================
# Tab 2: Precipitation Anomalies (LOF)
# ======================================================
with tab2:
    st.header("Precipitation Anomalies (LOF)")

    proportion = st.slider("Proportion of anomalies to detect (LOF)", min_value=0.001, max_value=0.1, value=0.01, step=0.001)

    def detect_precipitation_lof_streamlit(df, precip_col="precipitation", proportion=0.01):
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

        # Summary statistics
        st.write(f"Total anomalies detected: {len(outliers)}")
        st.dataframe(outliers.head(20))
        return outliers

    precip_outliers = detect_precipitation_lof_streamlit(weather_df, proportion=proportion)
