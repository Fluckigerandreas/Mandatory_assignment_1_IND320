# ======================================================
#   new_A.py - STL & Spectrogram for Elhub Production
# ======================================================
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.seasonal import STL
from scipy import signal
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import certifi

from mysecrets import USERNAME, PASSWORD  # MongoDB credentials

# ======================================================
#   MONGODB CONNECTION
# ======================================================
def connect_mongo():
    ca = certifi.where()
    uri = (
        f"mongodb+srv://{USERNAME}:{PASSWORD}"
        "@cluster0.chffuae.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    )
    client = MongoClient(uri, server_api=ServerApi("1"), tls=True, tlsCAFile=ca)
    client.admin.command("ping")
    st.success("✅ Connected to MongoDB")
    return client

# ======================================================
#   LOAD ELHUB PRODUCTION DATA
# ======================================================
def load_all_elhub_production(client, db_name="example", collection_name="data"):
    db = client[db_name]
    coll = db[collection_name]
    df = pd.DataFrame(list(coll.find()))
    if df.empty:
        raise ValueError(f"No documents found in {db_name}.{collection_name}")
    datetime_col = next((c for c in df.columns if "start" in c.lower()), None)
    quantity_col = next((c for c in df.columns if "quantity" in c.lower()), None)
    if not datetime_col or not quantity_col:
        raise ValueError("Missing datetime or quantity column")
    df[datetime_col] = pd.to_datetime(df[datetime_col])
    df.set_index(datetime_col, inplace=True)
    df = df.groupby(df.index).agg({quantity_col: "sum"})
    df.rename(columns={quantity_col: "production"}, inplace=True)
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

# Connect and load data
client = connect_mongo()
full_elhub_df = load_all_elhub_production(client)

# Tabs
tabs = st.tabs(["STL Decomposition", "Spectrogram"])

# --- STL Decomposition Tab ---
with tabs[0]:
    st.header("STL Decomposition of Elhub Production")
    period = st.number_input("STL Period (hours)", value=24*7)
    stl_res = stl_decompose_series(full_elhub_df["production"], period=period)

# --- Spectrogram Tab ---
with tabs[1]:
    st.header("Spectrogram of Elhub Production")
    nperseg = st.number_input("Window size (hours)", value=24*7)
    noverlap = st.number_input("Overlap (hours)", value=nperseg//2)
    f, t, Sxx = plot_spectrogram(full_elhub_df["production"], nperseg=nperseg, noverlap=noverlap)
