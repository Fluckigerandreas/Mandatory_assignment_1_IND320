import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# --- Functions from Snow_drift.py ---
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
        season_start = pd.Timestamp(year=s, month=7, day=1)
        season_end = pd.Timestamp(year=s+1, month=6, day=30, hour=23, minute=59, second=59)
        df_season = df[(df['time'] >= season_start) & (df['time'] <= season_end)]
        if df_season.empty:
            continue
        df_season['Swe_hourly'] = df_season.apply(
            lambda row: row['precipitation (mm)'] if row['temperature_2m (°C)'] < 1 else 0, axis=1)
        total_Swe = df_season['Swe_hourly'].sum()
        wind_speeds = df_season["wind_speed_10m (m/s)"].tolist()
        result = compute_snow_transport(T, F, theta, total_Swe, wind_speeds)
        result["season"] = f"{s}-{s+1}"
        results_list.append(result)
    return pd.DataFrame(results_list)

def compute_average_sector(df):
    sectors_list = []
    for s, group in df.groupby('season'):
        group = group.copy()
        group['Swe_hourly'] = group.apply(
            lambda row: row['precipitation (mm)'] if row['temperature_2m (°C)'] < 1 else 0, axis=1)
        ws = group["wind_speed_10m (m/s)"].tolist()
        wdir = group["wind_direction_10m (°)"].tolist()
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

# --- Streamlit UI ---
st.title("Snow Drift Calculator & Wind Rose Visualization")

uploaded_file = st.file_uploader("Upload Open-Meteo CSV", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file, skiprows=3)
    df['time'] = pd.to_datetime(df['time'])
    df['season'] = df['time'].apply(lambda dt: dt.year if dt.month >= 7 else dt.year - 1)

    # Check coordinates selection (dummy here: require lat/lon columns)
    if "latitude" not in df.columns or "longitude" not in df.columns:
        st.error("Coordinate selection missing in the data. Cannot proceed.")
    else:
        st.success("Coordinates found.")

        min_year, max_year = int(df['season'].min()), int(df['season'].max())
        year_range = st.slider("Select Year Range", min_year, max_year, (min_year, max_year))

        df_selected = df[(df['season'] >= year_range[0]) & (df['season'] <= year_range[1])]

        T = 3000
        F = 30000
        theta = 0.5

        yearly_df = compute_yearly_results(df_selected, T, F, theta)

        if yearly_df.empty:
            st.warning("No data available for the selected year range.")
        else:
            st.subheader("Yearly Snow Drift (Qt in tonnes/m)")
            yearly_df['Qt (tonnes/m)'] = yearly_df['Qt'] / 1000.0
            st.dataframe(yearly_df[['season', 'Qt (tonnes/m)', 'Control']])

            # Plot Qt as bar chart
            fig_bar = go.Figure([go.Bar(
                x=yearly_df['season'],
                y=yearly_df['Qt (tonnes/m)'],
                text=yearly_df['Control'],
                marker_color='skyblue'
            )])
            fig_bar.update_layout(title="Yearly Snow Drift", yaxis_title="Qt (tonnes/m)")
            st.plotly_chart(fig_bar)

            # Wind rose
            avg_sectors = compute_average_sector(df_selected)
            overall_avg = yearly_df['Qt'].mean()
            st.subheader("Wind Rose of Snow Transport")
            plot_wind_rose(avg_sectors, overall_avg)

else:
    st.info("Please upload a CSV file to start.")