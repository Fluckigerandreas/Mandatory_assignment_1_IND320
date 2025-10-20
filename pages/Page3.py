import streamlit as st
import pandas as pd
from pymongo import MongoClient
import certifi
import plotly.express as px

# --- MongoDB connection ---
uri = st.secrets["mongo"]["uri"]
ca = certifi.where()
client = MongoClient(uri, tls=True, tlsCAFile=ca)

db = client['example']
collection = db['data']

# --- Load data ---
data = list(collection.find())
if not data:
    st.error("No data found in MongoDB.")
    st.stop()

df = pd.DataFrame(data)
df["starttime"] = pd.to_datetime(df["starttime"])

# --- Streamlit layout ---
st.title("Energy Production Dashboard")
col1, col2 = st.columns(2)

# --- LEFT COLUMN: Price area selection + pie chart ---
with col1:
    st.header("Total Production Pie Chart")
    st.subheader("Select Price Areas:")

    selected_areas = []

    # Multiple radio buttons simulation
    for area in df["pricearea"].unique():
        choice = st.radio(f"{area}:", ["Exclude", "Include"], index=0, key=f"radio_{area}")
        if choice == "Include":
            selected_areas.append(area)

    if not selected_areas:
        st.warning("Please select at least one price area.")
        st.stop()

    # Filter and aggregate
    df_area = df[df["pricearea"].isin(selected_areas)]
    total_by_group = df_area.groupby(["pricearea", "productiongroup"])["quantitykwh"].sum().reset_index()

    # Pie chart
    fig_pie = px.pie(
        total_by_group,
        names="productiongroup",
        values="quantitykwh",
        color="pricearea" if len(selected_areas) > 1 else None,
        title=f"Total Production in Selected Price Area(s)"
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig_pie, use_container_width=True)

# --- RIGHT COLUMN: Production group(s) + month + line chart ---
with col2:
    st.header("Monthly Production Line Plot")
    
    # Multi-select for production groups
    prod_groups = st.multiselect(
        "Select production group(s):",
        df["productiongroup"].unique(),
        default=df["productiongroup"].unique()
    )
    
    # Month selection
    month = st.selectbox(
        "Select a month:",
        list(range(1, 13)),
        format_func=lambda x: pd.to_datetime(f"2021-{x}-01").strftime("%B")
    )
    
    # Filter data
    df_filtered = df_area[
        (df_area["productiongroup"].isin(prod_groups)) &
        (df_area["starttime"].dt.month == month)
    ]
    
    if df_filtered.empty:
        st.warning("No data for this selection.")
    else:
        fig_line = px.line(
            df_filtered,
            x="starttime",
            y="quantitykwh",
            color="productiongroup",
            markers=True,
            title=f"Hourly Production ({pd.to_datetime(f'2021-{month}-01').strftime('%B')})"
        )
        st.plotly_chart(fig_line, use_container_width=True)

# --- Expander for data source ---
with st.expander("Data Source"):
    st.write("""
    The data displayed in this dashboard is sourced from the ELHUB API, 
    containing hourly electricity production per price area and production group. 
    Data has been loaded into MongoDB and visualized interactively here.
    """)
