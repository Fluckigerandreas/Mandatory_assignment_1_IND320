# NewA.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.seasonal import STL
from scipy import signal
from pymongo.mongo_client import MongoClient
import certifi

st.set_page_config(page_title="Production Analysis: STL & Spectrogram", layout="wide")

# -------------------------------
@st.cache_data(show_spinner="Loading data from MongoDB...")
def load_data():
    """Load data from MongoDB with caching."""
    uri = st.secrets["mongo"]["uri"]
    ca = certifi.where()
    client = MongoClient(uri, tls=True, tlsCAFile=ca)
    db = client['example']
    collection = db['data']

    data = list(collection.find())
    if not data:
        return pd.DataFrame()  # Empty DataFrame fallback

    df = pd.DataFrame(data)
    df["starttime"] = pd.to_datetime(df["starttime"])

    # Remove duplicates (keep first)
    df = df.drop_duplicates(subset=["pricearea", "productiongroup", "starttime"], keep="first").reset_index(drop=True)

    return df

# -------------------------------
def stl_decompose_series(series, period=24*7, title="STL Decomposition"):
    """Perform STL decomposition and plot."""
    series = series.sort_index()
    series = series[~series.index.duplicated(keep='first')]  # remove duplicate timestamps

    # Handle timezone & DST
    if series.index.tz is not None:
        series = series.tz_convert("UTC")
    else:
        series.index = series.index.tz_localize("UTC")

    # Regularize to hourly frequency
    series = series.asfreq("h")
    series = series.interpolate(method="time")

    stl = STL(series, period=period, robust=True)
    result = stl.fit()

    # Plot
    fig = result.plot()
    fig.set_size_inches(14, 10)
    fig.suptitle(f"{title}\n{series.name}", fontsize=12)
    plt.tight_layout()
    st.pyplot(fig)

    return result

# -------------------------------
def plot_spectrogram(series, fs=1.0, nperseg=24*7, noverlap=None):
    """Plot the spectrogram of a series."""
    series = series[~series.index.duplicated(keep='first')]  # remove duplicate timestamps
    s = series.dropna().astype(float)
    noverlap = noverlap or nperseg // 2

    f, t, Sxx = signal.spectrogram(
        s.values, fs=fs, window="hann", nperseg=nperseg, noverlap=noverlap
    )

    fig, ax = plt.subplots(figsize=(14, 5))
    pcm = ax.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-12), shading="gouraud")
    ax.set_title("Spectrogram (dB scale)")
    ax.set_xlabel("Window index")
    ax.set_ylabel("Frequency [cycles/hour]")
    plt.colorbar(pcm, ax=ax, label="dB")
    plt.tight_layout()
    st.pyplot(fig)

    return f, t, Sxx

# -------------------------------
# Main Streamlit App
# -------------------------------
st.title("Production Analysis: STL & Spectrogram")

# Load data
df = load_data()
if df.empty:
    st.warning("No production data found in MongoDB.")
    st.stop()

# Price area selector
price_areas = df["pricearea"].unique()
selected_area = st.selectbox("Select price area:", price_areas)

# Filter data
df_area = df[df["pricearea"] == selected_area].copy()

# Determine series column
if "quantitykwh" in df_area.columns:
    series = df_area.set_index("starttime")["quantitykwh"]
else:
    st.error("No 'quantitykwh' column found in the data.")
    st.stop()

# Tabs
tab1, tab2 = st.tabs(["STL Decomposition", "Spectrogram"])

with tab1:
    st.header("STL Decomposition")
    period = st.number_input("Seasonal period (hours):", min_value=1, value=24*7)
    stl_res = stl_decompose_series(series, period=period)

with tab2:
    st.header("Spectrogram")
    fs = st.number_input("Sampling frequency (1/hour default):", min_value=0.1, value=1.0)
    nperseg = st.number_input("Window length (hours):", min_value=1, value=24*7)
    plot_spectrogram(series, fs=fs, nperseg=nperseg)
