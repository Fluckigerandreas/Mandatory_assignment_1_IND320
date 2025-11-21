import streamlit as st
import folium
from streamlit_folium import st_folium
import json
from shapely.geometry import shape, Point
from datetime import timedelta
from pymongo import MongoClient
import certifi
import pandas as pd

st.title("Norway Price Areas Map – Elhub Data (NO1–NO5)")

# ------------------------------------------------------------------------------
# Load GeoJSON
# ------------------------------------------------------------------------------
geojson_path = "file.geojson"  # replace with your path
with open(geojson_path, "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

# ------------------------------------------------------------------------------
# Session state
# ------------------------------------------------------------------------------
if "clicked_point" not in st.session_state:
    st.session_state.clicked_point = None

if "selected_area" not in st.session_state:
    st.session_state.selected_area = None

if "area_means" not in st.session_state:
    st.session_state.area_means = {}

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
# User selections
# ------------------------------------------------------------------------------
data_type = st.radio("Select data type:", ["Production", "Consumption"], horizontal=True)
df = prod_df if data_type == "Production" else cons_df
group_col = "productiongroup" if data_type == "Production" else "consumptiongroup"

groups = sorted(df[group_col].unique())
selected_group = st.selectbox("Select group:", groups)

days = st.number_input("Time interval (days):", min_value=1, max_value=90, value=7)

# ------------------------------------------------------------------------------
# Compute mean per area and store in session state
# ------------------------------------------------------------------------------
def compute_area_means():
    df_group = df[df[group_col] == selected_group]
    if df_group.empty:
        return {}
    end_time = df_group.index.max()
    start_time = end_time - timedelta(days=days)
    df_interval = df_group[(df_group.index >= start_time) & (df_group.index <= end_time)]
    return df_interval.groupby("pricearea")["quantitykwh"].mean().to_dict()

st.session_state.area_means = compute_area_means()
area_means = st.session_state.area_means

if not area_means:
    st.warning("No data available for this selection.")
    st.stop()

# ------------------------------------------------------------------------------
# Color function based on area means
# ------------------------------------------------------------------------------
vals = list(area_means.values())
if vals:
    vmin, vmax = min(vals), max(vals)
else:
    vmin, vmax = 0, 1

def get_color(value):
    if vmin == vmax:
        return "#ffff00"  # yellow if all values are equal
    norm = (value - vmin) / (vmax - vmin)
    r = int(255 * (1 - norm))
    g = int(255 * norm)
    return f"#{r:02x}{g:02x}00"

# ------------------------------------------------------------------------------
# Build Folium map
# ------------------------------------------------------------------------------
m = folium.Map(location=[63.0, 10.5], zoom_start=5.5)

def style_function(feature):
    area = feature["properties"]["ElSpotOmr"]
    if area in area_means:
        fill = get_color(area_means[area])
    else:
        fill = "#cccccc"  # light grey for areas without data
    if st.session_state.selected_area == area:
        return {"fillColor": fill, "color": "red", "weight": 3, "fillOpacity": 0.6}
    return {"fillColor": fill, "color": "blue", "weight": 1, "fillOpacity": 0.6}

folium.GeoJson(
    geojson_data,
    style_function=style_function,
    tooltip=folium.GeoJsonTooltip(fields=["ElSpotOmr"], aliases=["Price area:"])
).add_to(m)

# Add marker for clicked point
if st.session_state.clicked_point:
    folium.Marker(
        st.session_state.clicked_point,
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)

# ------------------------------------------------------------------------------
# Click handler
# ------------------------------------------------------------------------------
map_data = st_folium(m, width=900, height=600)

if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]
    st.session_state.clicked_point = (lat, lon)

    point = Point(lon, lat)
    clicked_area = None
    for feature in geojson_data["features"]:
        polygon = shape(feature["geometry"])
        if polygon.contains(point):
            clicked_area = feature["properties"]["ElSpotOmr"]
            break
    st.session_state.selected_area = clicked_area
    st.rerun()

# ------------------------------------------------------------------------------
# Display information
# ------------------------------------------------------------------------------
st.write("### Mean values per area:")
st.json(area_means)

if st.session_state.selected_area:
    st.success(f"Selected area: **{st.session_state.selected_area}**")
st.write(f"Clicked coordinates: {st.session_state.clicked_point}")
