import streamlit as st
import pandas as pd

# Load data
data = pd.read_csv("/workspaces/blank-app/open-meteo-subset.csv")

st.title("Weather Data Table with First-Month Line Chart")

# Display the full data table
st.subheader("Imported Data")
st.dataframe(data)

# --- Row-wise Line Chart for First Month ---
st.subheader("First Month Weather Trend")

# Assuming first row is the first month, drop non-numeric columns like 'Month' if present
first_month = data.iloc[0:1, 1:]  # skip first column if it's 'Month' or a label

# Transpose so the line chart reads each variable as a series
st.line_chart(first_month.T, use_container_width=True)