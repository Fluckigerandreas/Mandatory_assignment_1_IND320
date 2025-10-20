import streamlit as st
import pandas as pd
import plotly.express as px

# --- Load your dataset ---
# Replace with your actual data loading
df = pd.read_csv("production_data.csv", parse_dates=["startTime"])

st.set_page_config(page_title="Page Four: Energy Analysis", layout="wide")
st.title("Energy Production Overview")

# --- Split page into two columns ---
col1, col2 = st.columns(2)

# --- LEFT COLUMN: Pie chart by price area ---
with col1:
    st.subheader("Total Production by Price Area")
    price_areas = df['priceArea'].unique()
    selected_area = st.radio("Select a Price Area:", price_areas)

    # Filter and aggregate
    pie_data = df[df['priceArea'] == selected_area].groupby('productionGroup')['quantityKwh'].sum().reset_index()

    # Plot pie chart using Plotly
    fig1 = px.pie(pie_data, names='productionGroup', values='quantityKwh',
                  title=f"Total Production in {selected_area}")
    st.plotly_chart(fig1, use_container_width=True)

# --- RIGHT COLUMN: Line plot by production group(s) and month ---
with col2:
    st.subheader("Monthly Production Trends")
    
    # Production group selection
    production_groups = df['productionGroup'].unique()
    selected_groups = st.multiselect("Select Production Groups:", production_groups, default=production_groups)
    
    # Month selection
    months = df['startTime'].dt.month.unique()
    selected_month = st.selectbox("Select Month:", sorted(months))
    
    # Filter data
    df_filtered = df[
        (df['priceArea'] == selected_area) &
        (df['productionGroup'].isin(selected_groups)) &
        (df['startTime'].dt.month == selected_month)
    ]
    
    # Aggregate per day
    df_filtered['day'] = df_filtered['startTime'].dt.day
    line_data = df_filtered.groupby(['day', 'productionGroup'])['quantityKwh'].sum().reset_index()

    # Plot line chart using Plotly
    fig2 = px.line(line_data, x='day', y='quantityKwh', color='productionGroup',
                   markers=True,
                   title=f"Daily Production in {selected_area} - Month {selected_month}")
    st.plotly_chart(fig2, use_container_width=True)

# --- Expander with data source ---
with st.expander("Data Source"):
    st.write("""
    The production data shown on this page is sourced from [your data source name], 
    which provides hourly energy production per price area and production group.
    Data is aggregated here by production group and day for visualization purposes.
    """)

