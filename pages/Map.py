# pages/Map.py
import streamlit as st
from pathlib import Path
import json
from shapely.geometry import shape, Point
import folium
from streamlit_folium import st_folium
from datetime import timedelta
import pandas as pd
from pymongo import MongoClient
import certifi

st.set_page_config(layout="wide", page_title="Norway Price Areas Map (NO1–NO5)")
st.title("Norway Price Areas Map (NO1–NO5)")

# ------------------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------------------
geojson_path = "/workspaces/blank-app/file.geojson"

# ------------------------------------------------------------------------------
# Utility: normalize area name (e.g. "NO 2" -> "NO2")
# ------------------------------------------------------------------------------
def normalize_area_name(s):
    if s is None:
        return None
    return "".join(str(s).upper().split())

# ------------------------------------------------------------------------------
# Load GeoJSON (cached)
# ------------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading GeoJSON...")
def load_geojson(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        geo = json.load(f)
    # Normalize and store a canonical property 'ElSpotOmr' with NO1,NO2...
    for feat in geo.get("features", []):
        props = feat.setdefault("properties", {})
        # try existing common keys, else keep what's present
        candidate = None
        for k in props.keys():
            if "ELSPOT" in k.upper() or "EL_SPOT" in k.upper() or "ELSPOTOMR" in k.upper() or "OMR" in k.upper():
                candidate = props[k]
                break
        if candidate is None:
            # fallback to existing ElSpotOmr or pricearea keys if present
            candidate = props.get("ElSpotOmr") or props.get("pricearea") or props.get("price_area")
        props["ElSpotOmr"] = normalize_area_name(candidate) if candidate is not None else None
    return geo

try:
    geojson = load_geojson(geojson_path)
except Exception as e:
    st.error(f"Could not load GeoJSON at {geojson_path}: {e}")
    st.stop()

# Build list of price areas from geojson
price_areas_geo = [feat["properties"]["ElSpotOmr"] for feat in geojson.get("features", []) if feat["properties"].get("ElSpotOmr")]
price_areas_geo = list(dict.fromkeys(price_areas_geo))  # unique, preserve order

# ------------------------------------------------------------------------------
# Session state
# ------------------------------------------------------------------------------
if "clicked_point" not in st.session_state:
    st.session_state.clicked_point = None
if "selected_area" not in st.session_state:
    st.session_state.selected_area = None
if "area_means" not in st.session_state:
    st.session_state.area_means = None

# ------------------------------------------------------------------------------
# Sidebar controls: data type, group, days
# ------------------------------------------------------------------------------
st.sidebar.header("Controls")
data_type = st.sidebar.radio("Select data type:", ["Production", "Consumption"])

# ------------------------------------------------------------------------------
# Load MongoDB data (cached)
# ------------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading MongoDB data...")
def load_mongo_data(data_type: str):
    # requires st.secrets["mongo"]["uri"] to be set
    uri = st.secrets["mongo"]["uri"]
    ca = certifi.where()
    client = MongoClient(uri, tls=True, tlsCAFile=ca)
    if data_type == "Production":
        db = client["Elhub"]
        collection = db["Data"]
    else:
        db = client["Consumption_Elhub"]
        collection = db["Data"]

    raw = list(collection.find())
    if not raw:
        return pd.DataFrame()

    df = pd.DataFrame(raw)
    # normalize column names to lowercase
    df.columns = [c.lower() for c in df.columns]

    # try to map alternate names to expected names
    if "pricearea" not in df.columns:
        for alt in ["elspotomr", "price_area", "pricearea", "pricearea_name"]:
            if alt in df.columns:
                df = df.rename(columns={alt: "pricearea"})
                break

    if "productiongroup" not in df.columns:
        for alt in ["group", "production_group", "prodgroup"]:
            if alt in df.columns:
                df = df.rename(columns={alt: "productiongroup"})
                break

    if "quantitykwh" not in df.columns and "quantity" in df.columns:
        df = df.rename(columns={"quantity": "quantitykwh"})

    if "starttime" not in df.columns:
        for alt in ["time", "timestamp", "start_time"]:
            if alt in df.columns:
                df = df.rename(columns={alt: "starttime"})
                break

    # If still missing required columns, return df for inspection
    required = {"pricearea", "productiongroup", "quantitykwh", "starttime"}
    if not required.issubset(set(df.columns)):
        return df

    # normalize pricearea values to NO1 format
    df["pricearea"] = df["pricearea"].astype(str).apply(normalize_area_name)
    df["starttime"] = pd.to_datetime(df["starttime"], errors="coerce")
    df["quantitykwh"] = pd.to_numeric(df["quantitykwh"], errors="coerce").fillna(0.0)

    # Aggregate duplicates
    df = df.groupby(["pricearea", "productiongroup", "starttime"], as_index=False).agg({"quantitykwh": "sum"})
    return df

df = load_mongo_data(data_type)

# If required columns missing, show and stop (so user can inspect structure)
required_cols = {"pricearea", "productiongroup", "quantitykwh", "starttime"}
if not required_cols.issubset(set(df.columns)):
    st.sidebar.warning("MongoDB data doesn't contain the expected columns. Inspect loaded table below.")
    st.sidebar.write("Columns found:", df.columns.tolist())
    st.write("Loaded sample rows from MongoDB:")
    st.dataframe(df.head(100))
    st.stop()

# Sidebar: group & days
group_selected = st.sidebar.selectbox("Select production/consumption group:", sorted(df["productiongroup"].unique()))
days = st.sidebar.slider("Time interval (days):", min_value=1, max_value=90, value=7)

# ------------------------------------------------------------------------------
# Compute mean per area for selected group and interval (cached)
# ------------------------------------------------------------------------------
@st.cache_data(show_spinner="Computing means per area...")
def compute_area_means(variable, days, df):
    means = {}
    for area in df["pricearea"].unique():
        df_area = df[df["pricearea"] == area]
        end_time = df_area.index.max()
        start_time = end_time - timedelta(days=days)
        df_period = df_area[(df_area.index >= start_time) & (df_area.index <= end_time)]
        means[area] = float(df_period[variable].mean())
    return means

st.session_state.area_means = compute_area_means(df, group_selected, days, price_areas_geo)
means = st.session_state.area_means

# ------------------------------------------------------------------------------
# Simple color mapping (green->red) using min/max of means
# ------------------------------------------------------------------------------
vals = list(means.values()) if means else [0.0]
vmin, vmax = min(vals), max(vals)
# avoid zero-range
if vmax - vmin < 1e-9:
    vmax = vmin + 1.0

def get_color(value):
    # normalize 0..1
    norm = (value - vmin) / (vmax - vmin)
    # gradient from green (low) to yellow to red (high)
    # simple linear ramp: green -> yellow -> red via RGB interpolation
    if norm <= 0.5:
        # green -> yellow: (0,255,0) to (255,255,0)
        ratio = norm / 0.5
        r = int(255 * ratio)
        g = 255
    else:
        # yellow -> red: (255,255,0) to (255,0,0)
        ratio = (norm - 0.5) / 0.5
        r = 255
        g = int(255 * (1 - ratio))
    b = 0
    return f"#{r:02x}{g:02x}{b:02x}"

# ------------------------------------------------------------------------------
# Build Folium map with GeoJSON overlay
# ------------------------------------------------------------------------------
m = folium.Map(location=[63.0, 10.5], zoom_start=5.4, tiles="CartoDB positron")

def style_function(feature):
    area = feature["properties"].get("ElSpotOmr")
    fill = get_color(means.get(area, 0.0))
    if st.session_state.selected_area and normalize_area_name(st.session_state.selected_area) == normalize_area_name(area):
        return {
            "fillColor": fill,
            "color": "red",
            "weight": 3,
            "fillOpacity": 0.6
        }
    return {
        "fillColor": fill,
        "color": "black",
        "weight": 1,
        "fillOpacity": 0.4
    }

folium.GeoJson(
    geojson,
    style_function=style_function,
    tooltip=folium.GeoJsonTooltip(fields=["ElSpotOmr"], aliases=["Price area:"])
).add_to(m)

# add clicked point marker if present
if st.session_state.clicked_point:
    folium.Marker(
        location=st.session_state.clicked_point,
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)

# ------------------------------------------------------------------------------
# Render map and capture clicks
# ------------------------------------------------------------------------------
map_data = st_folium(m, width=900, height=650)

if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]
    st.session_state.clicked_point = (lat, lon)

    # determine which price area contains the point
    p = Point(lon, lat)
    clicked_area = None
    for feat in geojson.get("features", []):
        poly = shape(feat["geometry"])
        if poly.contains(p) or poly.touches(p):
            clicked_area = feat["properties"].get("ElSpotOmr")
            break
    st.session_state.selected_area = clicked_area
    # rerun to update map highlight and marker
    st.experimental_rerun()

# ------------------------------------------------------------------------------
# Side info: show computed means and selections
# ------------------------------------------------------------------------------
col1, col2 = st.columns([3, 1])
with col2:
    st.subheader("Selection")
    st.write("Data type:", data_type)
    st.write("Group:", group_selected)
    st.write("Interval (days):", days)
    st.write("Data range (DB):", df["starttime"].min(), "→", df["starttime"].max())
    st.write("Selected Price Area:", st.session_state.selected_area)
    if st.session_state.clicked_point:
        st.write("Clicked coords:", st.session_state.clicked_point)

with st.expander("Show mean values per area (for debugging)"):
    df_means = pd.DataFrame([{"pricearea": k, "mean_kwh": v} for k, v in means.items()])
    st.dataframe(df_means)

# ------------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------------
