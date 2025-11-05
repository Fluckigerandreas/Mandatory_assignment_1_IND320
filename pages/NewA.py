import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.seasonal import STL
from scipy import signal
from pymongo.mongo_client import MongoClient
import certifi

# ======================================================
#   CACHED DATA LOADING FROM MONGODB
# ======================================================
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

    # Remove duplicates (fix NO1 duplicate issue)
    df = df.drop_duplicates(subset=["pricearea", "productiongroup", "starttime"], keep="first").reset_index(drop=True)
    return df

# ======================================================
#   STL DECOMPOSITION
# ======================================================
def stl_decompose_series(series, period=24*7, title="STL Decomposition"):
    series = series.sort_index()
    if series.index.tz is not None:
        series = series.tz_convert("UTC")
    else:
        series.index = series.index.tz_localize("UTC")
    series = series.asfreq("h")
    series = series.interpolate(method="time")
    stl = STL(series, period=period, robust=True)
    result = stl.fit()
    fig = result.plot()
    fig.set_size_inches(14, 10)
    fig.suptitle(f"{title}\n{series.name}", fontsize=12)
    plt.tight_layout()
    st.pyplot(fig)
    return result

# ======================================================
#   SPECTROGRAM
# ======================================================
def plot_spectrogram(series, fs=1.0, nperseg=24*7, noverlap=None):
    s = series.dropna().astype(float)
    noverlap = noverlap or nperseg // 2
    f, t, Sxx = signal.spectrogram(s.values, fs=fs, window="hann", nperseg=nperseg, noverlap=noverlap)
    fig, ax = plt.subplots(figsize=(10, 5))
    pcm = ax.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-12), shading="gouraud")
    ax.set_title("Spectrogram (dB scale)")
    ax.set_xlabel("Window index")
    ax.set_ylabel("Frequency [cycles/hour]")
    plt.colorbar(pcm, ax=ax, label="dB")
    plt.tight_layout()
    st.pyplot(fig)
    return f, t, Sxx

# ======================================================
#   STREAMLIT APP
# ======================================================
st.title("STL & Spectrogram Analysis - Elhub Production")

# Load data (cached)
df = load_data()
if df.empty:
    st.warning("No data found in MongoDB.")
else:
    # Select pricearea if needed
    price_areas = df["pricearea"].unique().tolist()
    selected_area = st.selectbox("Select Price Area", price_areas)
    df_area = df[df["pricearea"] == selected_area].copy()
    df_area.set_index("starttime", inplace=True)
    series = df_area["production"]

    # Tabs
    tabs = st.tabs(["STL Decomposition", "Spectrogram"])

    # --- STL Tab ---
    with tabs[0]:
        st.header(f"STL Decomposition - {selected_area}")
        period = st.number_input("STL Period (hours)", value=24*7)
        stl_res = stl_decompose_series(series, period=period)

    # --- Spectrogram Tab ---
    with tabs[1]:
        st.header(f"Spectrogram - {selected_area}")
        nperseg = st.number_input("Window size (hours)", value=24*7)
        noverlap = st.number_input("Overlap (hours)", value=nperseg//2)
        f, t, Sxx = plot_spectrogram(series, nperseg=nperseg, noverlap=noverlap)
