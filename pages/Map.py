import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_plotly_events import plotly_events

st.set_page_config(layout="wide")
st.title("Norwegian Price Areas – Interactive Map")

# -----------------------
# Load GeoJSON
# -----------------------
geojson_path = "/workspaces/blank-app/file.geojson"
with open(geojson_path, "r") as f:
    geojson_data = json.load(f)

# Extract Price Area names for locations
df = pd.DataFrame([feat["properties"] for feat in geojson_data["features"]])
df["dummy"] = 1  # placeholder column for choropleth

# -----------------------
# Streamlit UI
# -----------------------
st.sidebar.header("Map Options")
# Future: select production/consumption group
# Future: select time interval

# -----------------------
# Build Plotly choropleth (outlines only)
# -----------------------
fig = px.choropleth(
    df,
    geojson=geojson_data,
    locations="ElSpotOmr",
    featureidkey="properties.ElSpotOmr",
    color="dummy",
    color_continuous_scale="Viridis"
)
# Show only outlines
fig.update_traces(marker_opacity=0.0, marker_line_width=2, marker_line_color="black")
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
fig.update_layout(clickmode="event+select")

# -----------------------
# Handle clicks
# -----------------------
if "clicked_coords" not in st.session_state:
    st.session_state.clicked_coords = []

clicked_points = plotly_events(fig, click_event=True, hover_event=False)

for point in clicked_points:
    lat = point["lat"]
    lon = point["lon"]
    st.session_state.clicked_coords.append((lat, lon))

# -----------------------
# Highlight clicked points
# -----------------------
for lat, lon in st.session_state.clicked_coords:
    fig.add_trace(
        go.Scattergeo(
            lon=[lon],
            lat=[lat],
            mode="markers",
            marker=dict(size=10, color="red"),
            name="Clicked point"
        )
    )

# -----------------------
# Display the map
# -----------------------
st.plotly_chart(fig, use_container_width=True)

# -----------------------
# Show clicked coordinates
# -----------------------
if st.session_state.clicked_coords:
    st.subheader("Clicked Coordinates")
    st.write(st.session_state.clicked_coords)
