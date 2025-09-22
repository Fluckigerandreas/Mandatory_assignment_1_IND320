import streamlit as st
import pandas as pd

st.set_page_config(page_title="First Month Overview", page_icon="📈")

st.title("📊 First Month Weather Overview")

# --- Load data ---
@st.cache_data
def load_data():
    df = pd.read_csv("/workspaces/blank-app/open-meteo-subset.csv")
    df['time'] = pd.to_datetime(df['time'])
    return df

df = load_data()

# --- Filter first month (January) ---
first_month = df[df['time'].dt.month == 1].copy()

# --- Prepare data: one row per variable ---
variables = first_month.columns[1:]  # skip 'time'
chart_data = pd.DataFrame({
    "Variable": variables,
    "Values": [first_month[var].tolist() for var in variables]
})

# --- Display as table with LineChartColumn ---
st.data_editor(
    chart_data,
    column_config={
        "Values": st.column_config.LineChartColumn(
            "First Month Trend",
            width="large",
            y_min=min(first_month[variables].min()),
            y_max=max(first_month[variables].max())
        )
    },
    hide_index=True,
    use_container_width=True
)
