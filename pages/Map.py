import re
import streamlit as st
import folium
from streamlit_folium import st_folium
import json
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from datetime import timedelta
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
    """
    Normalize many representations to 'NO1'...'NO5'.
    Accepts: 'N01', 'N1', 'NO1', '01', '1', 1, 'n01', 'n1', 'NO 1', 'N-01', etc.
    Returns e.g. 'NO1' or None if cannot parse.
    """
    if code is None:
        return None
    if isinstance(code, int):
        n = int(code)
        return f"NO{n}"
    s = str(code).strip().upper()
    # remove non-alphanumeric
    s = re.sub(r"[^A-Z0-9]", "", s)
    # examples: N01, N1, NO1, 01, 1
    m = re.match(r"^N0?([1-9])$", s)            # N01, N1 -> capture 1
    if m:
        return f"NO{m.group(1)}"
    m2 = re.match(r"^NO0?([1-9])$", s)          # NO01, NO1
    if m2:
        return f"NO{m2.group(1)}"
    m3 = re.match(r"^0?([1-9])$", s)            # 01, 1
    if m3:
        return f"NO{m3.group(1)}"
    return None

def extract_geojson_area(feature):
    # Try a few known property names commonly found in the NVE export
    props = feature.get("properties", {})
    candidates = ["ElSpotOmr", "Elspot_omr", "ELSPOT_OMR", "ElSpotOmråde", "ELSPOT_OMRADE"]
    raw = None
    for k in candidates:
        if k in props:
            raw = props[k]
            break
    if raw is None:
        # as fallback, attempt to search any property that looks like Nxx/NOx
        for v in props.values():
            if isinstance(v, (str, int)):
                if normalize_to_NO(v) is not None:
                    raw = v
                    break
    return normalize_to_NO(raw)

# Build a lookup from geojson feature index -> normalized area code
geo_feature_area = {}
for i, feat in enumerate(geojson_data.get("features", [])):
    norm = extract_geojson_area(feat)
    geo_feature_area[i] = norm

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
    # Normalize pricearea column if present
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
    df["starttime"] = pd.to_datetime(df["starttime"])
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

# Handle empty dataframe or missing group column gracefully
if df.empty or group_col not in df.columns:
    st.warning("No data available (empty dataframe or missing group column). Check DB and secrets.")
    st.stop()

groups = sorted(df[group_col].dropna().unique())
if not groups:
    st.warning("No groups found in the data.")
    st.stop()

selected_group = st.selectbox("Select group:", groups)
days = st.number_input("Time interval (days):", min_value=1, max_value=365, value=7)

# ==============================================================================
# Compute mean per area (and normalize keys)
# ==============================================================================
def compute_area_means():
    df_group = df[df[group_col] == selected_group].copy()
    if df_group.empty:
        return {}
    end_time = df_group.index.max()
    start_time = end_time - timedelta(days=days)
    df_interval = df_group[(df_group.index >= start_time) & (df_group.index <= end_time)]
    if df_interval.empty:
        return {}
    # pricearea should already be normalized by loader; ensure again and drop nulls
    df_interval["pricearea"] = df_interval["pricearea"].apply(normalize_to_NO)
    df_interval = df_interval[df_interval["pricearea"].notna()]
    means = df_interval.groupby("pricearea")["quantitykwh"].mean().to_dict()
    return means

st.session_state.area_means = compute_area_means()
area_means = st.session_state.area_means

if not area_means:
    st.warning("No data available for this selection.")
    st.stop()

# Debug: show mapping between geojson areas and normalized codes (optional)
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
    caption=f"Mean quantity kWh for {selected_group} ({days} days)"
)

# ==============================================================================
# Build folium map
# ==============================================================================
m = folium.Map(location=[63.0, 10.5], zoom_start=5.4, tiles="OpenStreetMap")

def style_function(feature):
    # normalize geojson area to NOx
    area = extract_geojson_area(feature)
    # fallback fill
    fill = "#dddddd"
    if area in area_means:
        fill = colormap(area_means[area])
    # selected highlight
    if st.session_state.selected_area == area:
        return {
            "fillColor": fill,
            "color": "red",
            "weight": 3,
            "fillOpacity": 0.65,
        }
    return {
        "fillColor": fill,
        "color": "#3333cc",
        "weight": 1,
        "fillOpacity": 0.55,
    }

# Add GeoJson with tooltip showing the original property and the normalized code
def tooltip_content(feature):
    props = feature.get("properties", {})
    # show a few property candidates for debugging
    txt = []
    for k in ["ElSpotOmr", "Elspot_omr", "ELSPOT_OMR"]:
        if k in props:
            txt.append(f"{k}: {props[k]}")
    norm = extract_geojson_area(feature)
    txt.append(f"Normalized: {norm}")
    return "<br/>".join(txt)

gj = folium.GeoJson(
    geojson_data,
    style_function=style_function,
    tooltip=folium.GeoJsonTooltip(fields=[], aliases=[], labels=False),
    highlight_function=lambda feat: {"weight": 2, "color": "black"}
)
# Attach custom tooltip per-feature (so we can include normalized code)
for i, feat in enumerate(geojson_data.get("features", [])):
    folium.GeoJson(
        feat,
        style_function=style_function,
        tooltip=folium.Tooltip(tooltip_content(feat), sticky=True)
    ).add_to(m)

# Add colormap (legend)
colormap.add_to(m)

# Marker for clicked point
if st.session_state.clicked_point:
    folium.Marker(
        st.session_state.clicked_point,
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)

# ==============================================================================
# Click handler (st_folium)
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

