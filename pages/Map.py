import streamlit as st
import pandas as pd
import json
from datetime import timedelta
import plotly.express as px
import plotly.graph_objects as go
from streamlit_plotly_events import plotly_events

# -----------------------
# Load GeoJSON
# -----------------------
with open("/workspaces/blank-app/file.geojson", "r") as f:
    geojson_data = json.load(f)

# Extract properties for the data table
df = pd.DataFrame([feat["properties"] for feat in geojson_data["features"]])
df["date"] = pd.to_datetime(df["date"])
df["value"] = pd.to_numeric(df["value"])

# -----------------------
# Streamlit UI
# -----------------------
st.title("Norwegian Price Areas – Interactive Map")

group_selected = st.selectbox("Select energy group:", df["group"].unique())
days = st.number_input("Time interval (days):", min_value=1, value=7, step=1)

# -----------------------
# Filter data by group and interval
# -----------------------
end_date = df["date"].max()
start_date = end_date - timedelta(days=days)

df_filtered = df[
    (df["group"] == group_selected) &
    (df["date"].between(start_date, end_date))
]

df_mean = df_filtered.groupby("price_area")["value"].mean().reset_index()

# -----------------------
# Build choropleth
# -----------------------
fig = px.choropleth(
    df_mean,
    geojson=geojson_data,
    locations="price_area",
    featureidkey="properties.price_area",
    color="value",
    color_continuous_scale="Viridis",
    range_color=(df_mean["value"].min(), df_mean["value"].max()),
)
fig.update_geos(fitbounds="locations", visible=False)
fig.update_traces(marker_opacity=0.55)

# -----------------------
# Handle clicks
# -----------------------
if "clicked_coords" not in st.session_state:
    st.session_state.clicked_coords = []

click_info = st.empty()
selected_area_text = st.empty()

def plot_click_marker(click_data):
    if click_data:
        lon = click_data["points"][0]["lon"]
        lat = click_data["points"][0]["lat"]
        st.session_state.clicked_coords.append((lat, lon))
        click_info.write(f"Clicked coordinates: Lat {lat:.4f}, Lon {lon:.4f}")

        if "location" in click_data["points"][0]:
            selected_area = click_data["points"][0]["location"]
            selected_area_text.write(f"Selected Price Area: {selected_area}")

            fig.add_trace(
                go.Choropleth(
                    geojson=geojson_data,
                    locations=[selected_area],
                    z=[1],
                    colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
                    marker_line_width=5,
                    marker_line_color="red",
                    featureidkey="properties.price_area",
                    showscale=False,
                    name="Selected Area"
                )
            )

# -----------------------
# Display map with Plotly events
# -----------------------
fig.update_layout(clickmode="event+select")
plotly_chart = st.plotly_chart(fig, use_container_width=True)
clicked_points = plotly_events(fig, click_event=True, hover_event=False)

if clicked_points:
    for point in clicked_points:
        plot_click_marker({"points": [point]})

# Show all clicked points
if st.session_state.clicked_coords:
    st.write("All clicked points:")
    st.write(st.session_state.clicked_coords)
