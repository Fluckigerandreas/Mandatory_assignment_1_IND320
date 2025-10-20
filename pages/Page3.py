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

# --- Define custom colors per production group ---
# Make sure these match the actual names in your data
group_colors = {
    "hydro": "blue",
    "wind": "orange",
    "solar": "yellow",
    "thermal": "green",
    "other": "black"
}

# If your dataset has additional groups, assign default colors
for group in df["productiongroup"].unique():
    if group not in group_colors:
        group_colors[group] = px.colors.qualitative.Pastel1[len(group_colors) % len(px.colors.qualitative.Pastel1)]

# --- Streamlit layout ---
st.title("Energy Production Dashboard")
col1, col2 = st.columns(2)

# --- LEFT COLUMN: Price area selection + pie chart ---
with col1:
    st.header("Total Production Pie Chart")
    st.subheader("Select Price Areas:")

    selected_areas = []

    # Arrange checkboxes horizontally
    price_areas = df["pricearea"].unique()
    n_cols = min(4, len(price_areas))
    rows = (len(price_areas) + n_cols - 1) // n_cols
    for r in range(rows):
        cols = st.columns(n_cols)
        for c, area_idx in enumerate(range(r * n_cols, min((r + 1) * n_cols, len(price_areas)))):
            area = price_areas[area_idx]
            if cols[c].checkbox(area, value=True, key=f"chk_{area}"):
                selected_areas.append(area)

    if not selected_areas:
        st.warning("Please select at least one price area.")
        st.stop()

    df_area = df[df["pricearea"].isin(selected_areas)]
    total_by_group = df_area.groupby(["productiongroup"])["quantitykwh"].sum().reset_index()

    # Pie chart with custom colors
    fig_pie = px.pie(
        total_by_group,
        names="productiongroup",
        values="quantitykwh",
        color="productiongroup",
        color_discrete_map=group_colors,
        title=f"Total Production in Selected Price Area(s)",
        width=600,
        height=600
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig_pie, use_container_width=True)

# --- RIGHT COLUMN: Production group(s) + month + line chart ---
with col2:
    st.header("Monthly Production Line Plot")
    
    # Multi-select for production groups
    prod_groups_selected = st.multiselect(
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
        (df_area["productiongroup"].isin(prod_groups_selected)) &
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
            color_discrete_map=group_colors,
            title=f"Hourly Production ({pd.to_datetime(f'2021-{month}-01').strftime('%B')})",
            width=700,
            height=500
        )
        st.plotly_chart(fig_line, use_container_width=True)

# --- Expander for data source ---
with st.expander("Data Source"):
    st.write("""
    The data displayed in this dashboard is sourced from the ELHUB API, 
    containing hourly electricity production per price area and production group. 
    Data has been loaded into MongoDB and visualized interactively here.
    """)
