import streamlit as st
import pandas as pd
import json
from datetime import timedelta
from pymongo import MongoClient
import certifi
import plotly.express as px
from shapely.geometry import shape, Point

# ------------------------------------------------------------------------------
# Page title
# ------------------------------------------------------------------------------
st.title("Energy Map – Norway Price Areas (NO1–NO5)")

# ------------------------------------------------------------------------------
# Load GeoJSON for price areas
# ------------------------------------------------------------------------------
geojson_path = "file.geojson"  # replace with your file path
with open(geojson_path, "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

# ------------------------------------------------------------------------------
# Session state
# ------------------------------------------------------------------------------
if "clicked_point" not in st.session_state:
    st.session_state.clicked_point = None

if "selected_area" not in st.session_state:
    st.session_state.selected_area = None

# ------------------------------------------------------------------------------
# MongoDB loaders
# ------------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading Production data...")
def load_production():
    uri = st.secrets["mongo"]["uri"]
    ca = certifi.where()
    client = MongoClient(uri, tls=True, tlsCAFile=ca)

    db = client["Elhub"]
    collection = db["Data"]

    data = list(collection.find())
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df["starttime"] = pd.to_datetime(df["starttime"])
    df = df.groupby(["pricearea", "productiongroup", "starttime"], as_index=False).agg({"quantitykwh": "sum"})
    df.set_index("starttime", inplace=True)
    return df

@st.cache_data(show_spinner="Loading Consumption data...")
def load_consumption():
    uri = st.secrets["mongo"]["uri"]
    ca = certifi.where()
    client = MongoClient(uri, tls=True, tlsCAFile=ca)

    db = client["Consumption_Elhub"]
    collection = db["Data"]

    data = list(collection.find())
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df["starttime"] = pd.to_datetime(df["starttime"])
    df = df.groupby(["pricearea", "consumptiongroup", "starttime"], as_index=False).agg({"quantitykwh": "sum"})
    df.set_index("starttime", inplace=True)
    return df

prod_df = load_production()
cons_df = load_consumption()

# ------------------------------------------------------------------------------
# Selectors
# ------------------------------------------------------------------------------
data_type = st.radio("Select data type:", ["Production", "Consumption"], horizontal=True)

if data_type == "Production":
    df = prod_df
    group_col = "productiongroup"
else:
    df = cons_df
    group_col = "consumptiongroup"

groups = sorted(df[group_col].unique())
selected_group = st.selectbox("Select group:", groups)
days = st.number_input("Time interval (days):", min_value=1, max_value=90, value=7)

# ------------------------------------------------------------------------------
# Filter data
# ------------------------------------------------------------------------------
df_group = df[df[group_col] == selected_group]

# Compute time window
end_time = df_group.index.max()
start_time = end_time - timedelta(days=days)
df_interval = df_group[(df_group.index >= start_time) & (df_group.index <= end_time)]

# Compute mean per price area
area_means = df_interval.groupby("pricearea")["quantitykwh"].mean().to_dict()

if not area_means:
    st.warning("No data available for this selection.")
    st.stop()

# Store area_means in session for access in Plotly
st.session_state.area_means = area_means

# ------------------------------------------------------------------------------
# Create Plotly choropleth
# ------------------------------------------------------------------------------
df_plot = pd.DataFrame({
    "pricearea": list(area_means.keys()),
    "mean_value": list(area_means.values())
})

fig = px.choropleth_mapbox(
    df_plot,
    geojson=geojson_data,
    locations="pricearea",
    featureidkey="properties.ElSpotOmr",
    color="mean_value",
    color_continuous_scale=["green", "blue", "yellow"],  # custom scale
    mapbox_style="carto-positron",
    zoom=5.2,
    center={"lat": 63.0, "lon": 10.5},
    opacity=0.7,
    labels={"mean_value": f"Mean {selected_group} ({data_type}) kWh"}
)

fig.update_traces(
    hovertemplate="<b>%{location}</b><br>Mean value: %{z:.2f} kWh<extra></extra>"
)

# ------------------------------------------------------------------------------
# Display Plotly map
# ------------------------------------------------------------------------------
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------------------
# Handle clicks on the map (requires Plotly click event workaround)
# ------------------------------------------------------------------------------
clicked = st.session_state.get("clicked_point", None)
st.write("### Clicked coordinates (use hover info for Plotly clicks):")
if clicked:
    st.write(f"Latitude = {clicked[0]:.5f}, Longitude = {clicked[1]:.5f}")
else:
    st.info("Hover over areas to see values; Plotly does not directly provide click coordinates.")
    
# ------------------------------------------------------------------------------
# Diagnostics
# ------------------------------------------------------------------------------
st.write("### Mean values per area:")
st.json(area_means)
