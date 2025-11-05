import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt


def page_new_A():
    st.title("STL & Spectrogram Analysis")

    tabs = st.tabs(["STL Decomposition", "Spectrogram"])
    
    # --- STL Decomposition Tab ---
    with tabs[0]:
        st.header("STL Decomposition")
        period = st.number_input("STL Period (hours)", value=24*7)
        stl_res = stl_decompose_series(full_elhub_df["production"], period=period)
        st.write("Trend, seasonal, and residual components are plotted above.")
    
    # --- Spectrogram Tab ---
    with tabs[1]:
        st.header("Spectrogram")
        nperseg = st.number_input("Window size (hours)", value=24*7)
        noverlap = st.number_input("Overlap (hours)", value=nperseg//2)
        f, t, Sxx = plot_spectrogram(full_elhub_df["production"], fs=1.0, nperseg=nperseg, noverlap=noverlap)
        st.write("Spectrogram (dB scale) plotted above.")