import streamlit as st
import folium
from streamlit_folium import st_folium
import json
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from datetime import timedelta
from pymongo import MongoClient
import certifi
import pandas as pd

st.title("Norway Price Areas Map – Elhub Data (NO1–NO5)")

# --------------------------------------------------------------------------
# Load GeoJSON
# --------------------------------------------------------------------------
geojson_path = "file.geojson"
with open(geojson_path, "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

# Ensure consistent property name
def extract_area_name(feature):
    return feature["properties"].get("ElSpotOmr")


# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
if "clicked_point" not in st.session_state:
    st.session_state.clicked_point = None
if "selected_area" not in st.session_state:
    st.session_state.selected_area = None
if "area_means" not in st.session_state:
    st.session_state.area_means = {}

# --------------------------------------------------------------------------
# Mongo Loaders
# --------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading production data...")
def load_production():
    client = MongoClient(st.secrets["mongo"]["uri"], tls=True, tlsCAFile=certifi.where())
    db = client["Elhub"]
    df = pd.DataFrame(list(db["Data"].find()))
    if df.empty:
        return df
    df["starttime"] = pd.to_datetime(df["starttime"])
    df = df.groupby(["pricearea", "productiongroup", "starttime"], as_index=False).agg({"quantitykwh": "sum"})
    df.set_index("starttime", inplace=True)
    return df

@st.cache_data(show_spinner="Loading consumption data...")
def load_consumption():
    client = MongoClient(st.secrets["mongo"]["uri"], tls=True, tlsCAFile=certifi.where())
    db = client["Consumption_Elhub"]
    df = pd.DataFrame(list(db["Data"].find()))
    if df.empty:
        return df
    df["starttime"] = pd.to_datetime(df["starttime"])
    df = df.groupby(["pricearea", "consumptiongroup", "starttime"], as_index=False).agg({"quantitykwh": "sum"})
    df.set_index("starttime", inplace=True)
    return df

prod_df = load_production()
cons_df = load_consumption()

# --------------------------------------------------------------------------
# User selection
# --------------------------------------------------------------------------
data_type = st.radio("Select data type:", ["Production", "Consumption"], horizontal=True)
df = prod_df if data_type == "Production" else cons_df
group_col = "productiongroup" if data_type == "Production" else "consumptiongroup"

groups = sorted(df[group_col].unique())
selected_group = st.selectbox("Choose group:", groups)
days = st.number_input("Time interval (days):", min_value=1, max_value=90, value=7)

# --------------------------------------------------------------------------
# Compute area means
# --------------------------------------------------------------------------
def compute_area_means():
    df_group = df[df[group_col] == selected_group]
    if df_group.empty:
        return {}
    end = df_group.index.max()
    start = end - timedelta(days=days)
    interval = df_group[(df_group.index >= start) & (df_group.index <= end)]
    return interval.groupby("pricearea")["quantitykwh"].mean().to_dict()

area_means = compute_area_means()
st.session_state.area_means = area_means

if not area_means:
    st.warning("No data available for this filter.")
    st.stop()

# --------------------------------------------------------------------------
# Color scale
# --------------------------------------------------------------------------
vals = list(area_means.values())
vmin, vmax = min(vals), max(vals)

def get_color(value):
    if vmin == vmax:
        return "#ffff00"
    t = (value - vmin) / (vmax - vmin)
    r = int(255 * (1 - t))
    g = int(255 * t)
    return f"#{r:02x}{g:02x}00"

# --------------------------------------------------------------------------
# Folium map
# --------------------------------------------------------------------------
m = folium.Map(location=[63, 10], zoom_start=5.3)

def style_function(feature):
    area_name = extract_area_name(feature)
    color = get_color(area_means.get(area_name, vmin))

    if st.session_state.selected_area == area_name:
        return {"fillColor": color, "color": "red", "weight": 3, "fillOpacity": 0.55}

    return {"fillColor": color, "color": "blue", "weight": 1, "fillOpacity": 0.55}

folium.GeoJson(
    geojson_data,
    name="Price Areas",
    style_function=style_function,
    tooltip=folium.GeoJsonTooltip(fields=["ElSpotOmr"], aliases=["Area:"])
).add_to(m)

# Marker
if st.session_state.clicked_point:
    folium.Marker(st.session_state.clicked_point, icon=folium.Icon(color="red")).add_to(m)

# --------------------------------------------------------------------------
# Click handling
# --------------------------------------------------------------------------
map_data = st_folium(m, width=1000, height=650)

if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]
    st.session_state.clicked_point = (lat, lon)

    point = Point(lon, lat)

    clicked_area = None
    for feature in geojson_data["features"]:
        geom = shape(feature["geometry"])
        if isinstance(geom, (Polygon, MultiPolygon)) and geom.contains(point):
            clicked_area = extract_area_name(feature)
            break

    st.session_state.selected_area = clicked_area
    st.rerun()

# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
st.subheader("Mean values per area:")
st.json(area_means)

if st.session_state.selected_area:
    st.success(f"Selected Price Area: {st.session_state.selected_area}")

st.write(f"Clicked point: {st.session_state.clicked_point}")
