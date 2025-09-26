# 3_Weather_Plot.py
import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(page_title="Weather Data Plot", page_icon="📈")

st.title("📊 Weather Data Visualization")

# --- Load Data ---
@st.cache_data
def load_data():
    df = pd.read_csv("open-meteo-subset.csv")
    df['time'] = pd.to_datetime(df['time'])
    df['month'] = df['time'].dt.to_period("M")  # extract year-month
    return df

df = load_data()

# --- User Controls ---
st.sidebar.header("Controls")

# Select column (or all)
columns = ["All"] + list(df.columns[1:-1])  # skip time + month helper
selected_column = st.selectbox("Select variable:", columns)

# Slider for month range
unique_months = df['month'].unique().astype(str).tolist()
month_range = st.select_slider(
    "Select months:",
    options=unique_months,
    value=(unique_months[0], unique_months[0])  # default: first month
)

# Filter data by month range
start, end = pd.Period(month_range[0]), pd.Period(month_range[1])
filtered_df = df[(df['month'] >= start) & (df['month'] <= end)]

# --- Plotting ---
st.subheader("Weather Data Plot")

if selected_column == "All":
    chart_data = filtered_df.melt(
        id_vars=["time"], 
        value_vars=df.columns[1:-1], 
        var_name="Variable", 
        value_name="Value"
    )
    chart = (
        alt.Chart(chart_data)
        .mark_line()
        .encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y("Value:Q", title="Value"),
            color="Variable:N",
            tooltip=["time:T", "Variable:N", "Value:Q"]
        )
        .properties(width=800, height=400, title="All Weather Variables")
    )
else:
    chart = (
        alt.Chart(filtered_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y(f"{selected_column}:Q", title=selected_column),
            tooltip=["time:T", f"{selected_column}:Q"]
        )
        .properties(width=800, height=400, title=f"{selected_column} over Time")
    )

st.altair_chart(chart, use_container_width=True)
