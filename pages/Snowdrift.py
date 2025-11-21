import streamlit as st
import folium
from streamlit_folium import st_folium
import json
from shapely.geometry import shape, Point
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests_cache

# ------------------- Snow drift functions -------------------
def compute_Qupot(hourly_wind_speeds, dt=3600):
    total = sum((u ** 3.8) * dt for u in hourly_wind_speeds) / 233847
    return total

def sector_index(direction):
    return int(((direction + 11.25) % 360) // 22.5)

def compute_sector_transport(hourly_wind_speeds, hourly_wind_dirs, dt=3600):
    sectors = [0.0] * 16
    for u, d in zip(hourly_wind_speeds, hourly_wind_dirs):
        idx = sector_index(d)
        sectors[idx] += ((u ** 3.8) * dt) / 233847
    return sectors

def compute_snow_transport(T, F, theta, Swe, hourly_wind_speeds, dt=3600):
    Qupot = compute_Qupot(hourly_wind_speeds, dt)
    Qspot = 0.5 * T * Swe
    Srwe = theta * Swe
    if Qupot > Qspot:
        Qinf = 0.5 * T * Srwe
        control = "Snowfall controlled"
    else:
        Qinf = Qupot
        control = "Wind controlled"
    Qt = Qinf * (1 - 0.14 ** (F / T))
    return {"Qupot": Qupot, "Qspot": Qspot, "Srwe": Srwe, "Qinf": Qinf, "Qt": Qt, "Control": control}

def compute_yearly_results(df, T, F, theta):
    seasons = sorted(df['season'].unique())
    results_list = []
    for s in seasons:
        # Make timestamps UTC-aware
        season_start = pd.Timestamp(year=s, month=7, day=1, tz='UTC')
        season_end = pd.Timestamp(year=s+1, month=6, day=30, hour=23, minute=59, second=59, tz='UTC')
        
        df_season = df[(df.index >= season_start) & (df.index <= season_end)].copy()
        if df_season.empty:
            continue
        df_season.loc[:, 'Swe_hourly'] = df_season.apply(
            lambda row: row['precipitation'] if row['temperature_2m'] < 1 else 0, axis=1
        )
        total_Swe = df_season['Swe_hourly'].sum()
        wind_speeds = df_season["wind_speed_10m"].tolist()
        result = compute_snow_transport(T, F, theta, total_Swe, wind_speeds)
        result["season"] = f"{s}-{s+1}"
        results_list.append(result)
    return pd.DataFrame(results_list)

def compute_average_sector(df):
    sectors_list = []
    for s, group in df.groupby('season'):
        group = group.copy()
        group.loc[:, 'Swe_hourly'] = group.apply(
            lambda row: row['precipitation'] if row['temperature_2m'] < 1 else 0, axis=1
        )
        ws = group["wind_speed_10m"].tolist()
        wdir = group["wind_direction_10m"].tolist()
        sectors = compute_sector_transport(ws, wdir)
        sectors_list.append(sectors)
    avg_sectors = np.mean(sectors_list, axis=0)
    return avg_sectors

def plot_wind_rose(avg_sector_values, overall_avg):
    directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                  'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    theta = np.linspace(0, 360, 16, endpoint=False)
    r = np.array(avg_sector_values) / 1000.0  # kg/m → tonnes/m
    fig = go.Figure()
    fig.add_trace(go.Barpolar(
        r=r,
        theta=theta,
        width=[22.5]*16,
        marker_color=r,
        marker_line_color="black",
        marker_line_width=1,
        opacity=0.8
    ))
    fig.update_layout(
        title=f"Average Directional Distribution of Snow Transport<br>Overall Average Qt: {overall_avg/1000:.1f} tonnes/m",
        polar=dict(
            radialaxis=dict(title='Qt (tonnes/m)'),
            angularaxis=dict(direction="clockwise", rotation=90, tickmode='array', tickvals=theta, ticktext=directions)
        )
    )
    st.plotly_chart(fig)

# ------------------- Open-Meteo ERA5 downloader -------------------
@st.cache_data(show_spinner="Downloading weather data...")
def download_era5_openmeteo(lat, lon, year, timezone="Europe/Oslo"):
    session = requests_cache.CachedSession(".cache", expire_after=-1)
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "hourly": ["temperature_2m", "precipitation", "wind_speed_10m",
                   "wind_gusts_10m", "wind_direction_10m"],
        "models": "era5",
        "timezone": timezone,
    }
    response = session.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'], utc=True)  # Make index UTC-aware
    df = df.set_index('time')
    df['season'] = df.index.to_series().apply(lambda dt: dt.year if dt.month >= 7 else dt.year - 1)
    return df

# ------------------- Streamlit App -------------------
st.title("Snow Drift Analysis with Map & Open-Meteo Data")

# --- Load GeoJSON ---
geojson_path = "file.geojson"
with open(geojson_path, "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

if "clicked_point" not in st.session_state:
    st.session_state.clicked_point = None
if "selected_area" not in st.session_state:
    st.session_state.selected_area = None

# --- Folium map ---
m = folium.Map(location=[63.0, 10.5], zoom_start=5.2)
def style_function(feature):
    if st.session_state.selected_area == feature["properties"]["ElSpotOmr"]:
        return {"fillColor":"red","color":"red","weight":3,"fillOpacity":0.6}
    else:
        return {"fillColor":"blue","color":"blue","weight":1,"fillOpacity":0.3}

folium.GeoJson(
    geojson_data,
    style_function=style_function,
    tooltip=folium.GeoJsonTooltip(fields=["ElSpotOmr"], aliases=["Area:"])
).add_to(m)

if st.session_state.clicked_point:
    folium.Marker(st.session_state.clicked_point, icon=folium.Icon(color="red")).add_to(m)

map_data = st_folium(m, width=900, height=500)

# --- Handle clicks ---
if map_data and map_data.get("last_clicked"):
    st.session_state.clicked_point = (map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"])
    p = Point(st.session_state.clicked_point[1], st.session_state.clicked_point[0])
    clicked_area = None
    for feature in geojson_data["features"]:
        polygon = shape(feature["geometry"])
        if polygon.contains(p):
            clicked_area = feature["properties"]["ElSpotOmr"]
            break
    st.session_state.selected_area = clicked_area
    # No need for experimental_rerun

# --- Snow drift calculation ---
if st.session_state.selected_area and st.session_state.clicked_point:
    st.success(f"Selected area: **{st.session_state.selected_area}**")
    lat, lon = st.session_state.clicked_point

    start_year = st.number_input("Start Year", min_value=1950, max_value=pd.Timestamp.now().year, value=2020)
    end_year = st.number_input("End Year", min_value=start_year, max_value=pd.Timestamp.now().year, value=2022)

    T = 3000
    F = 30000
    theta = 0.5

    all_years_df = []
    for year in range(start_year, end_year + 1):
        df_year = download_era5_openmeteo(lat, lon, year)
        all_years_df.append(df_year)
    df_all = pd.concat(all_years_df)

    yearly_df = compute_yearly_results(df_all, T, F, theta)
    if yearly_df.empty:
        st.warning("No snow drift data available for the selected range.")
    else:
        yearly_df['Qt (tonnes/m)'] = yearly_df['Qt'] / 1000
        st.subheader("Yearly Snow Drift (Qt)")
        st.dataframe(yearly_df[['season', 'Qt (tonnes/m)', 'Control']])

        # Qt bar chart
        fig_bar = go.Figure([go.Bar(x=yearly_df['season'], y=yearly_df['Qt (tonnes/m)'], marker_color='skyblue')])
        fig_bar.update_layout(title="Yearly Snow Drift", yaxis_title="Qt (tonnes/m)")
        st.plotly_chart(fig_bar)

        # Wind rose
        avg_sectors = compute_average_sector(df_all)
        overall_avg = yearly_df['Qt'].mean()
        st.subheader("Wind Rose of Snow Transport")
        plot_wind_rose(avg_sectors, overall_avg)
else:
    st.info("Click on the map to select a location.")

