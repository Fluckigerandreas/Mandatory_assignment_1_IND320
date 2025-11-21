import streamlit as st
import folium
from streamlit_folium import st_folium
import json
from shapely.geometry import shape, Point
import pandas as pd
import numpy as np
from datetime import timedelta
from pymongo import MongoClient
import certifi

# ------------------------------------------------------------------------------
# Page title
# ------------------------------------------------------------------------------
st.title("Energy Map – Norway Price Areas (NO1–NO5)")

# ------------------------------------------------------------------------------
# Load GeoJSON for price areas
# ------------------------------------------------------------------------------
geojson_path = "file.geojson"
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

# ------------------------------------------------------------------------------
# Create map
# ------------------------------------------------------------------------------
m = folium.Map(location=[63.0, 10.5], zoom_start=5.2)

# Create DataFrame for choropleth
choropleth_df = pd.DataFrame({
    "pricearea": list(area_means.keys()),
    "mean_value": list(area_means.values())
})

# Scale values to millions for legend readability
choropleth_df["mean_value_millions"] = choropleth_df["mean_value"] / 1_000_000

# Compute bins for color thresholds (5 bins)
bins = list(np.linspace(
    choropleth_df["mean_value_millions"].min(),
    choropleth_df["mean_value_millions"].max(),
    6
))

# Add choropleth with explicit bins
folium.Choropleth(
    geo_data=geojson_data,
    name="Mean Values",
    data=choropleth_df,
    columns=["pricearea", "mean_value_millions"],
    key_on="feature.properties.ElSpotOmr",
    fill_color="YlOrRd",
    fill_opacity=0.7,
    line_opacity=0.5,
    legend_name=f"Mean {selected_group} ({data_type}) M kWh",
    threshold_scale=bins,
    reset=True
).add_to(m)

# Overlay GeoJson to allow selection highlighting
def style_function(feature):
    area = feature["properties"]["ElSpotOmr"]
    if area == st.session_state.selected_area:
        return {
            "fillColor": "#0000ff",  # Highlight selected area in blue
            "color": "red",
            "weight": 3,
            "fillOpacity": 0.4
        }
    else:
        return {
            "fillColor": "#00000000",  # Transparent fill so choropleth color shows through
            "color": "black",
            "weight": 1,
            "fillOpacity": 0
        }

folium.GeoJson(
    geojson_data,
    name="Selection",
    style_function=style_function,
    tooltip=folium.GeoJsonTooltip(fields=["ElSpotOmr"], aliases=["Price area:"])
).add_to(m)

# Add marker for clicked point
if st.session_state.clicked_point:
    folium.Marker(
        st.session_state.clicked_point,
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)

map_data = st_folium(m, width=900, height=600)

# ------------------------------------------------------------------------------
# Show clicked coordinates
# ------------------------------------------------------------------------------
if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]
    st.write(f"**Clicked coordinates:** Latitude = {lat:.5f}, Longitude = {lon:.5f}")

# ------------------------------------------------------------------------------
# Handle clicks for area detection and rerun
# ------------------------------------------------------------------------------
if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]
    st.session_state.clicked_point = (lat, lon)

    # Detect area
    p = Point(lon, lat)
    clicked_area = None
    for feature in geojson_data["features"]:
        polygon = shape(feature["geometry"])
        if polygon.contains(p):
            clicked_area = feature["properties"]["ElSpotOmr"]
            break

    st.session_state.selected_area = clicked_area
    st.rerun()

# ------------------------------------------------------------------------------
# Diagnostics
# ------------------------------------------------------------------------------
st.write("### Mean values per area:")
st.json(area_means)

if st.session_state.selected_area:
    st.success(f"Selected area: **{st.session_state.selected_area}**")
