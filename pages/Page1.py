import streamlit as st
import pandas as pd

# Load data
data = pd.read_csv("/workspaces/blank-app/open-meteo-subset.csv")

st.title("Weather Data Dashboard")
st.subheader("Imported Data Table")
st.dataframe(data)

# --- Row-wise line charts for the first month ---
st.subheader("First Month Trends by Variable")

# Convert 'time' to datetime
data['time'] = pd.to_datetime(data['time'])

# Filter first month (January 2020)
first_month = data[data['time'].dt.month == 1]

# Drop the time column for plotting numeric variables
numeric_data = first_month.drop(columns=['time'])

# Display each variable as a small line chart
for col in numeric_data.columns:
    st.markdown(f"**{col}**")
    st.line_chart(numeric_data[col], use_container_width=True)
