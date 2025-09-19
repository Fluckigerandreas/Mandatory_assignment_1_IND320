import streamlit as st
import pandas as pd

# Load CSV
data = pd.read_csv("/workspaces/blank-app/open-meteo-subset.csv")

# Display data in the Streamlit app
st.title("Weather Data")
st.subheader("Imported Data Table")
st.dataframe(data)  # interactive table