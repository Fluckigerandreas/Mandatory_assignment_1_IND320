# pages/Map.py
import streamlit as st
import pandas as pd
import json
from datetime import timedelta
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient
import certifi
from streamlit_plotly_events import plotly_events
from shapely.geometry import shape, Point

st.set_page_config(layout="wide", page_title="Price Areas Map")

# -----------------------
# Helper: normalize area name
# -----------------------
def normalize_area_name(s):
    if s is None:
        return s
    # strip, remove extra spaces, uppercase, remove internal spaces like "NO 2" -> "NO2"
    return "".join(str(s).upper().split())

# -----------------------
# Sidebar - GeoJSON source
# -----------------------
st.sidebar.header("GeoJSON source")
geojson_local_path = st.sidebar.text_input("Local geojson path", value="/workspaces/blank-app/file.geojson")
geojson_url = st.sidebar.text_input("Or GeoJSON URL (optional)", value="")

# -----------------------
# Load GeoJSON
# -----------------------
@st.cache_data(show_spinner="Loading GeoJSON...")
def load_geojson(local_path, url):
    if url:
        # try download
        import requests
        r = requests.get(url)
        r.raise_for_status()
        geo = r.json()
    else:
        with open(local_path, "r", encoding="utf-8") as f:
            geo = json.load(f)

    # Normalize property key names if needed. We expect property "ElSpotOmr" but adapt if different
    # We'll search for a key that contains 'ElSpot' or 'ElSpotOmr' etc.
    # Normalize the values as well (NO 2 -> NO2)
    for feat in geo.get("features", []):
        props = feat.setdefault("properties", {})

        # find candidate key for price area:
        price_keys = [k for k in props.keys() if "ELSPOT" in k.upper() or "EL_SPOT" in k.upper() or "ELSPOTOMR" in k.upper() or "OMR" in k.upper()]
        if price_keys:
            # keep first candidate, but standardize to 'ElSpotOmr'
            val = props[price_keys[0]]
            props["ElSpotOmr"] = normalize_area_name(val)
        else:
            # if nothing found, leave as-is; user must ensure property present
            props["ElSpotOmr"] = normalize_area_name(props.get("ElSpotOmr") or props.get("pricearea") or props.get("price_area"))
    return geo

try:
    geojson_data = load_geojson(geojson_local_path, geojson_url)
except Exception as e:
    st.error(f"Could not load GeoJSON: {e}")
    st.stop()

# Build list of price areas from GeoJSON
price_areas_geo = []
for feat in geojson_data.get("features", []):
    pa = feat.get("properties", {}).get("ElSpotOmr")
    if pa:
        price_areas_geo.append(pa)
price_areas_geo = list(dict.fromkeys(price_areas_geo))  # unique preserve order

if not price_areas_geo:
    st.error("No price area names found in GeoJSON properties. Ensure the GeoJSON has an 'ElSpotOmr' property (or similar).")
    st.stop()

# -----------------------
# Sidebar - choose production / consumption
# -----------------------
st.sidebar.header("Data source")
data_type = st.sidebar.radio("Select data type:", ["Production", "Consumption"])

# -----------------------
# Load MongoDB data (cached)
# -----------------------
@st.cache_data(show_spinner="Loading data from MongoDB...")
def load_mongo_data(data_type):
    # NOTE: you must have st.secrets["mongo"]["uri"] set with access to your DB
    uri = st.secrets["mongo"]["uri"]
    ca = certifi.where()
    client = MongoClient(uri, tls=True, tlsCAFile=ca)

    if data_type == "Production":
        db = client['Elhub']
        collection = db['Data']
    else:
        db = client['Consumption_Elhub']
        collection = db['Data']

    rows = list(collection.find())
    if not rows:
        return pd.DataFrame()

    df_local = pd.DataFrame(rows)

    # ensure fields exist; if names differ adjust here
    # Expected fields: pricearea, productiongroup, quantitykwh, starttime
    # Some documents may use other keys; user may adjust mapping
    expected = ["pricearea", "productiongroup", "quantitykwh", "starttime"]
    # Normalize column names to lower-case for safety
    df_local.columns = [c.lower() for c in df_local.columns]

    # If there are alternate column names, try to adapt
    if "pricearea" not in df_local.columns:
        # try alternatives
        for alt in ["elspotomr", "price_area", "priceArea", "pricearea_name"]:
            if alt in df_local.columns:
                df_local = df_local.rename(columns={alt: "pricearea"})
                break

    if "productiongroup" not in df_local.columns:
        for alt in ["group", "production_group", "prodgroup"]:
            if alt in df_local.columns:
                df_local = df_local.rename(columns={alt: "productiongroup"})
                break

    if "quantitykwh" not in df_local.columns and "quantity" in df_local.columns:
        df_local = df_local.rename(columns={"quantity": "quantitykwh"})

    if "starttime" not in df_local.columns:
        for alt in ["time", "timestamp", "start_time"]:
            if alt in df_local.columns:
                df_local = df_local.rename(columns={alt: "starttime"})
                break

    # Make sure required columns exist now
    if "pricearea" not in df_local.columns or "productiongroup" not in df_local.columns or "quantitykwh" not in df_local.columns or "starttime" not in df_local.columns:
        # still missing something — return df so user can inspect
        return df_local

    # Normalize pricearea strings to same format as GeoJSON (NO2 etc)
    df_local["pricearea"] = df_local["pricearea"].astype(str).apply(normalize_area_name)

    # parse datetime
    df_local["starttime"] = pd.to_datetime(df_local["starttime"], errors="coerce")
    # numeric
    df_local["quantitykwh"] = pd.to_numeric(df_local["quantitykwh"], errors="coerce").fillna(0.0)

    # Aggregate duplicates
    df_local = df_local.groupby(["pricearea", "productiongroup", "starttime"], as_index=False).agg({"quantitykwh": "sum"})
    return df_local

df = load_mongo_data(data_type)

# If data frame lacks required columns, show to user for debugging
required_cols = {"pricearea", "productiongroup", "quantitykwh", "starttime"}
if not required_cols.issubset(set(df.columns)):
    st.warning("Loaded MongoDB data is missing some expected columns. Showing first rows for inspection.")
    st.write("Columns found:", df.columns.tolist())
    st.dataframe(df.head(50))
    st.stop()

# -----------------------
# Sidebar filters: production group and interval
# -----------------------
st.sidebar.header("Filters")
group_selected = st.sidebar.selectbox("Select production/consumption group:", sorted(df["productiongroup"].unique()))
days = st.sidebar.number_input("Time interval (days):", min_value=1, value=7, step=1)

# -----------------------
# Compute mean per price area for selected interval & group
# -----------------------
end_date = df["starttime"].max()
start_date = end_date - timedelta(days=days)
df_filtered = df[(df["productiongroup"] == group_selected) & (df["starttime"].between(start_date, end_date))]

# Debug info
with st.sidebar.expander("Debug info"):
    st.write("Data Type:", data_type)
    st.write("Group:", group_selected)
    st.write("Date range in DB:", df["starttime"].min(), "→", df["starttime"].max())
    st.write("Using interval:", start_date.date(), "→", end_date.date())
    st.write("Filtered rows:", len(df_filtered))

df_mean = df_filtered.groupby("pricearea")["quantitykwh"].mean().reset_index().rename(columns={"quantitykwh": "mean_kwh"})

# Ensure every geo price area has a value (0 if missing)
df_mean = df_mean.set_index("pricearea").reindex(price_areas_geo, fill_value=0).reset_index()

# -----------------------
# Build choropleth outline + transparent fill
# -----------------------
fig = px.choropleth(
    df_mean,
    geojson=geojson_data,
    locations="pricearea",
    featureidkey="properties.ElSpotOmr",
    color="mean_kwh",
    color_continuous_scale="Viridis",
    labels={"mean_kwh": "mean kWh"},
)

# transparent fill and visible outlines
fig.update_traces(marker_opacity=0.5, marker_line_width=1, marker_line_color="black")
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
fig.update_layout(coloraxis_colorbar=dict(title="mean kWh"))
fig.update_layout(clickmode="event+select")

# -----------------------
# Click handling: store coords, find containing Price Area, highlight it
# -----------------------
if "clicked_coords" not in st.session_state:
    st.session_state.clicked_coords = []
if "selected_price_area" not in st.session_state:
    st.session_state.selected_price_area = None

# Capture clicks using streamlit-plotly-events
clicked_points = plotly_events(fig, click_event=True, hover_event=False, key="map_events")

# For each click: get lat/lon, append to session, find containing polygon
if clicked_points:
    for pt in clicked_points:
        lat = pt.get("lat")
        lon = pt.get("lon")
        # store coords
        st.session_state.clicked_coords.append((lat, lon))

        # Determine containing Price Area: prefer 'location' returned by Plotly (the location id),
        # otherwise do point-in-polygon using shapely.
        selected_area = pt.get("location")  # might be None
        if not selected_area:
            # point-in-polygon test
            p = Point(lon, lat)  # shapely Point uses (x=lon, y=lat)
            found = None
            for feat in geojson_data.get("features", []):
                geom = feat.get("geometry")
                props = feat.get("properties", {})
                poly = shape(geom)
                if poly.contains(p) or poly.touches(p):
                    found = props.get("ElSpotOmr")
                    break
            selected_area = found

        if selected_area:
            # normalize
            selected_area = normalize_area_name(selected_area)
            st.session_state.selected_price_area = selected_area

# Add markers for clicked coords
for (lat, lon) in st.session_state.clicked_coords:
    fig.add_trace(go.Scattergeo(
        lon=[lon], lat=[lat],
        mode="markers",
        marker=dict(size=8, color="red"),
        name="Clicked point",
        showlegend=False
    ))

# Highlight selected price area polygon with thicker red outline and transparent fill
if st.session_state.selected_price_area:
    sel = st.session_state.selected_price_area
    # Add a second choropleth trace with only the selected area and a strong outline
    fig.add_trace(go.Choropleth(
        geojson=geojson_data,
        locations=[sel],
        z=[1],
        featureidkey="properties.ElSpotOmr",
        colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],  # fully transparent fill
        marker_line_color="red",
        marker_line_width=4,
        showscale=False,
        name=f"Selected {sel}"
    ))

# -----------------------
# Display map and side info
# -----------------------
col1, col2 = st.columns([3,1])
with col1:
    st.plotly_chart(fig, use_container_width=True, clamp=True)

with col2:
    st.header("Selection")
    st.write("Data type:", data_type)
    st.write("Group:", group_selected)
    st.write("Interval (days):", days)
    st.write("Computed from:", start_date.date(), "→", end_date.date())
    st.write("Available Price Areas (from GeoJSON):", price_areas_geo)
    if st.session_state.selected_price_area:
        st.markdown(f"**Selected Price Area:** `{st.session_state.selected_price_area}`")
    if st.session_state.clicked_coords:
        st.write("Clicked coordinates (most recent first):")
        # show reversed so newest first
        for c in reversed(st.session_state.clicked_coords[-10:]):
            st.write(f"Lat {c[0]:.6f}, Lon {c[1]:.6f}")

# Optional: show underlying dataframe for debugging/inspection
with st.expander("Show data used for choropleth (df_mean)"):
    st.dataframe(df_mean)
