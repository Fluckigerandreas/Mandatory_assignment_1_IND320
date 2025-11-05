import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

def page_new_B():
    st.title("Outlier & Anomaly Analysis")

    tabs = st.tabs(["Temperature Outliers (DCT+SPC)", "Precipitation Anomalies (LOF)"])

    # --- Temperature Outliers Tab ---
    with tabs[0]:
        st.header("Temperature Outliers (DCT + SPC)")
        cutoff_hours = st.number_input("Cutoff Hours for DCT Smoothing", value=24*30*6)
        n_std = st.number_input("Number of Std Devs for SPC", value=3.5, step=0.1)
        temp_outliers = detect_temperature_outliers_dct(weather_df, cutoff_hours=cutoff_hours, n_std=n_std)
        st.write(f"Number of outliers detected: {len(temp_outliers)}")
        st.dataframe(temp_outliers)
    
    # --- Precipitation Anomalies Tab ---
    with tabs[1]:
        st.header("Precipitation Anomalies (LOF)")
        proportion = st.number_input("Contamination proportion", value=0.01, step=0.01)
        precip_outliers = detect_precipitation_lof(weather_df, proportion=proportion)
        st.write(f"Number of anomalies detected: {len(precip_outliers)}")
        st.dataframe(precip_outliers)