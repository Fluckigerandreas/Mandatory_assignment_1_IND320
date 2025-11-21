import re
import streamlit as st
import folium
from streamlit_folium import st_folium
import json
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from pymongo import MongoClient
import certifi
import pandas as pd
import branca

st.set_page_config(layout="wide")
st.title("Norway Price Areas Map – Elhub Data (NO1–NO5)")

# ==============================================================================
# Load GeoJSON
# ==============================================================================
geojson_path = "file.geojson"  # <-- replace if needed
with open(geojson_path, "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

# ==============================================================================
# Normalization helpers
# ==============================================================================
def normalize_to_NO(code):
    if code is None:
        return None
    if isinstance(code, int):
        return f"NO{code}"
    s = str(code).strip().upper()
    s = re.sub(r"[^A-Z0-9]", "", s)
    m = re.match(r"^N0?([1-9])$", s)
    if m:
        return f"NO{m.group(1)}"
    m2 = re.match(r"^NO0?([1-9])$", s)
    if m2:
        return f"NO{m2.group(1)}"
    m3 = re.match(r"^0?([1-9])$", s)
    if m3:
        return f"NO{m3.group(1)}"
    return None

def extract_geojson_area(feature):
    props = feature.get("properties", {})
    candidates = ["ElSpotOmr", "Elspot_omr", "ELSPOT_OMR", "ElSpotOmråde", "ELSPOT_OMRADE"]
    raw = None
    for k in candidates:
        if k in props:
            raw = props[k]
            break
    if raw is None:
        for v in props.values():
            if isinstance(v, (str, int)) and normalize_to_NO(v) is not None:
                raw = v
                break
    return normalize_to_NO(raw)

geo_feature_area = {}
for i, feat in enumerate(geojson_data.get("features", [])):
    geo_feature_area[i] = extract_geojson_area(feat)

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
@st.cache_data(show_spinner="Loading production data...")
def load_production():
    client = MongoClient(st.secrets["mongo"]["uri"], tls=True, tlsCAFile=certifi.where())
    db = client["Elhub"]
    df = pd.DataFrame(list(db["Data"].find()))
    if df.empty:
        return df
    # Convert to datetime with UTC
    df["starttime"] = pd.to_datetime(df["starttime"], utc=True)
    if "pricearea" in df.columns:
        df["pricearea"] = df["pricearea"].apply(normalize_to_NO)
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
    df["starttime"] = pd.to_datetime(df["starttime"], utc=True)
    if "pricearea" in df.columns:
        df["pricearea"] = df["pricearea"].apply(normalize_to_NO)
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

if df.empty or group_col not in df.columns:
    st.warning("No data available (empty dataframe or missing group column). Check DB and secrets.")
    st.stop()

groups = sorted(df[group_col].dropna().unique())
if not groups:
    st.warning("No groups found in the data.")
    st.stop()

selected_group = st.selectbox("Select group:", groups)

# Year filter
selected_year = st.selectbox("Select year:", [2021, 2022, 2023, 2024])

# ==============================================================================
# Compute mean per area
# ==============================================================================
def compute_area_means():
    df_group = df[df[group_col] == selected_group].copy()
    if df_group.empty:
        return {}

    # Ensure index is DatetimeIndex
    if not isinstance(df_group.index, pd.DatetimeIndex):
        df_group.index = pd.to_datetime(df_group.index)

    df_group["year"] = df_group.index.year
    df_year = df_group[df_group["year"] == selected_year]
    if df_year.empty:
        return {}

    df_year["pricearea"] = df_year["pricearea"].apply(normalize_to_NO)
    df_year = df_year[df_year["pricearea"].notna()]

    means = df_year.groupby("pricearea")["quantitykwh"].mean().to_dict()
    return means

st.session_state.area_means = compute_area_means()
area_means = st.session_state.area_means

if not area_means:
    st.warning(f"No data available for {selected_group} in {selected_year}.")
    st.stop()

# ==============================================================================
# Debug: show mapping between geojson areas and normalized codes
# ==============================================================================
st.sidebar.write("GeoJSON -> normalized area (sample):")
sample_map = {i: v for i, v in list(geo_feature_area.items())}
st.sidebar.json(sample_map)

# ==============================================================================
# Color scale using branca
# ==============================================================================
vals = list(area_means.values())
vmin, vmax = min(vals), max(vals)
colormap = branca.colormap.LinearColormap(
    colors=["#d73027", "#fee08b", "#1a9850"],  # red -> yellow -> green
    vmin=vmin, vmax=vmax,
    caption=f"Mean quantity kWh for {selected_group} ({selected_year})"
)

# ==============================================================================
# Build folium map
# ==============================================================================
m = folium.Map(location=[63.0, 10.5], zoom_start=5.4, tiles="OpenStreetMap")

def style_function(feature):
    area = extract_geojson_area(feature)
    fill = "#dddddd"
    if area in area_means:
        fill = colormap(area_means[area])
    if st.session_state.selected_area == area:
        return {"fillColor": fill, "color": "red", "weight": 3, "fillOpacity": 0.65}
    return {"fillColor": fill, "color": "#3333cc", "weight": 1, "fillOpacity": 0.55}

def tooltip_content(feature):
    props = feature.get("properties", {})
    txt = []
    for k in ["ElSpotOmr", "Elspot_omr", "ELSPOT_OMR"]:
        if k in props:
            txt.append(f"{k}: {props[k]}")
    norm = extract_geojson_area(feature)
    txt.append(f"Normalized: {norm}")
    return "<br/>".join(txt)

for i, feat in enumerate(geojson_data.get("features", [])):
    folium.GeoJson(
        feat,
        style_function=style_function,
        tooltip=folium.Tooltip(tooltip_content(feat), sticky=True)
    ).add_to(m)

colormap.add_to(m)

if st.session_state.clicked_point:
    folium.Marker(
        st.session_state.clicked_point,
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)

# ==============================================================================
# Click handler
# ==============================================================================
map_data = st_folium(m, width=1000, height=700)

if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]
    st.session_state.clicked_point = (lat, lon)

    point = Point(lon, lat)
    clicked_area = None
    for feat in geojson_data.get("features", []):
        geom = shape(feat["geometry"])
        if isinstance(geom, (Polygon, MultiPolygon)) and geom.contains(point):
            clicked_area = extract_geojson_area(feat)
            break

    st.session_state.selected_area = clicked_area
    st.experimental_rerun()

# ==============================================================================
# Display info
# ==============================================================================
st.write("### Mean values per area (normalized keys):")
st.json(area_means)

if st.session_state.selected_area:
    st.success(f"Selected area: **{st.session_state.selected_area}**")

st.write(f"Clicked coordinates: {st.session_state.clicked_point}")
