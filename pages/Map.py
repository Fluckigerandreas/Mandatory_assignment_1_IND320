import streamlit as st
import folium
from streamlit_folium import st_folium
import json
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from pymongo import MongoClient
from datetime import timedelta
import certifi
import pandas as pd

st.title("Norway Price Areas Map – Elhub Data (NO1–NO5)")

# ==============================================================================
# Load GeoJSON
# ==============================================================================
geojson_path = "file.geojson"  # Replace with your file location
with open(geojson_path, "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

# Normalize GeoJSON area ("N01") → Mongo area ("NO1")
def normalize_area_name(name):
    if isinstance(name, str) and name.startswith("N0") and len(name) == 3:
        return "NO" + name[-1]
    return name

def extract_area_name(feature):
    raw = feature["properties"].get("ElSpotOmr")
    return normalize_area_name(raw)

# ==============================================================================
# Session state
# ==============================================================================
if "clicked_point" not in st.session_state:
    st.session_state.clicked_point = None

if "selected_area" not in st.session_state:
    st.session_state.selected_area = None

if "area_means" not in st.session_state:
    st.session_state.area_means = {}

# ==============================================================================
# MongoDB Loaders
# ==============================================================================
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

# ==============================================================================
# User selections
# ==============================================================================
data_type = st.radio("Select data type:", ["Production", "Consumption"], horizontal=True)
df = prod_df if data_type == "Production" else cons_df
group_col = "productiongroup" if data_type == "Production" else "consumptiongroup"

groups = sorted(df[group_col].unique())
selected_group = st.selectbox("Select group:", groups)

# ==============================================================================
# Compute mean per area (fixed interval 2021 → 2024)
# ==============================================================================
def compute_area_means():
    df_group = df[df[group_col] == selected_group]
    if df_group.empty:
        return {}

    # --- FIXED time interval (your requirement) ---
    start_time = pd.Timestamp("2021-01-01")
    end_time   = pd.Timestamp("2024-12-31")

    df_interval = df_group[(df_group.index >= start_time) & (df_group.index <= end_time)]
    if df_interval.empty:
        return {}

    # Normalize price areas
    df_interval["pricearea"] = df_interval["pricearea"].apply(normalize_area_name)
    df_interval = df_interval[df_interval["pricearea"].notna()]

    return df_interval.groupby("pricearea")["quantitykwh"].mean().to_dict()

st.session_state.area_means = compute_area_means()
area_means = st.session_state.area_means

if not area_means:
    st.warning("No data available for this selection.")
    st.stop()

# ==============================================================================
# Color function
# ==============================================================================
vals = list(area_means.values())
vmin, vmax = min(vals), max(vals)

def get_color(value):
    if vmin == vmax:
        return "#ffff00"  # Yellow when no variation
    norm = (value - vmin) / (vmax - vmin)
    r = int(255 * (1 - norm))
    g = int(255 * norm)
    return f"#{r:02x}{g:02x}00"

# ==============================================================================
# Build Folium map
# ==============================================================================
m = folium.Map(location=[63.0, 10.5], zoom_start=5.4)

def style_function(feature):
    area = extract_area_name(feature)

    if area in area_means:
        fill = get_color(area_means[area])
    else:
        fill = "#cccccc"

    # highlight selected area
    if st.session_state.selected_area == area:
        return {"fillColor": fill, "color": "red", "weight": 3, "fillOpacity": 0.60}

    return {"fillColor": fill, "color": "blue", "weight": 1, "fillOpacity": 0.60}

folium.GeoJson(
    geojson_data,
    style_function=style_function,
    tooltip=folium.GeoJsonTooltip(fields=["ElSpotOmr"], aliases=["Price area:"])
).add_to(m)

# Marker for clicked point
if st.session_state.clicked_point:
    folium.Marker(
        st.session_state.clicked_point,
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)

# ==============================================================================
# Click handler
# ==============================================================================
map_data = st_folium(m, width=950, height=630)

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

# ==============================================================================
# Display info
# ==============================================================================
st.write("### Mean values per area (2021–2024):")
st.json(area_means)

if st.session_state.selected_area:
    st.success(f"Selected area: **{st.session_state.selected_area}**")

st.write(f"Clicked coordinates: {st.session_state.clicked_point}")
