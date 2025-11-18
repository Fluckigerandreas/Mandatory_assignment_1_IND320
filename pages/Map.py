import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
from pymongo import MongoClient
import certifi
from streamlit_plotly_events import plotly_events

st.set_page_config(layout="wide")
st.title("Norwegian Price Areas – Interactive Map")

# -----------------------
# Load GeoJSON
# -----------------------
with open("/workspaces/blank-app/file.geojson", "r") as f:
    geojson_data = json.load(f)

# -----------------------
# Sidebar: choose data type
# -----------------------
data_type = st.sidebar.radio("Select data type:", ["Production", "Consumption"])

# -----------------------
# Load MongoDB data
# -----------------------
@st.cache_data(show_spinner="Loading data from MongoDB...")
def load_data(data_type):
    uri = st.secrets["mongo"]["uri"]
    ca = certifi.where()
    client = MongoClient(uri, tls=True, tlsCAFile=ca)

    if data_type == "Production":
        db = client['Elhub']
        collection = db['Data']
    else:
        db = client['Consumption_Elhub']
        collection = db['Data']

    data = list(collection.find())
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df["starttime"] = pd.to_datetime(df["starttime"])
    # Aggregate duplicates
    df = df.groupby(["pricearea", "productiongroup", "starttime"], as_index=False).agg({"quantitykwh": "sum"})
    return df

df = load_data(data_type)

if df.empty:
    st.warning(f"No data found for {data_type}!")
    st.stop()

# -----------------------
# Sidebar: group selection & time interval
# -----------------------
group_selected = st.sidebar.selectbox("Select group:", df["productiongroup"].unique())
days = st.sidebar.number_input("Time interval (days):", min_value=1, value=7, step=1)

# Filter by group and date interval
end_date = df["starttime"].max()
start_date = end_date - timedelta(days=days)

df_filtered = df[
    (df["productiongroup"] == group_selected) &
    (df["starttime"].between(start_date, end_date))
]

# Compute mean per price area
df_mean = df_filtered.groupby("pricearea")["quantitykwh"].mean().reset_index()

# Align with GeoJSON
price_areas = [feat["properties"]["ElSpotOmr"] for feat in geojson_data["features"]]
df_mean = df_mean.set_index("pricearea").reindex(price_areas, fill_value=0).reset_index()

# -----------------------
# Build choropleth map
# -----------------------
fig = px.choropleth(
    df_mean,
    geojson=geojson_data,
    locations="pricearea",
    featureidkey="properties.ElSpotOmr",
    color="quantitykwh",
    color_continuous_scale="Viridis",
    range_color=(df_mean["quantitykwh"].min(), df_mean["quantitykwh"].max()),
)

fig.update_traces(marker_opacity=0.55, marker_line_width=2, marker_line_color="black")
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, clickmode="event+select")

# -----------------------
# Handle clicks
# -----------------------
if "clicked_coords" not in st.session_state:
    st.session_state.clicked_coords = []

clicked_points = plotly_events(fig, click_event=True, hover_event=False)
for point in clicked_points:
    st.session_state.clicked_coords.append((point["lat"], point["lon"]))

# Highlight clicked points
for lat, lon in st.session_state.clicked_coords:
    fig.add_trace(go.Scattergeo(
        lon=[lon], lat=[lat], mode="markers",
        marker=dict(size=10, color="red"), name="Clicked point"
    ))

# -----------------------
# Display map
# -----------------------
st.plotly_chart(fig, use_container_width=True)

# Show clicked coordinates
if st.session_state.clicked_coords:
    st.subheader("Clicked Coordinates")
    st.write(st.session_state.clicked_coords)
