import streamlit as st
import pandas as pd
from pymongo import MongoClient
import certifi
import plotly.express as px

uri = st.secrets["mongo"]["uri"]
ca = certifi.where()
client = MongoClient(uri, tls=True, tlsCAFile=ca)

df = client['example']
collection = df['data']

# ---------------------------------------------
# 2. Load data from MongoDB into a DataFrame
# ---------------------------------------------
data = list(collection.find())
if len(data) == 0:
    st.error("No data found in MongoDB.")
    st.stop()

df = pd.DataFrame(data)

# Convert date columns to datetime
df["starttime"] = pd.to_datetime(df["starttime"])

# ---------------------------------------------
# 3. Streamlit layout: two columns
# ---------------------------------------------
st.title("Energy Production Dashboard")

col1, col2 = st.columns(2)

# --- Left column: Price area selection + pie chart ---
with col1:
    st.header("Total Production Pie Chart")
    price_area = st.radio("Select a price area:", df["pricearea"].unique())
    
    df_area = df[df["pricearea"] == price_area]
    total_by_group = df_area.groupby("productiongroup")["quantitykwh"].sum().reset_index()

    fig_pie = px.pie(
        total_by_group,
        names="productiongroup",
        values="quantitykwh",
        title=f"Total Production in {price_area} (Year)"
    )
    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig_pie, use_container_width=True)

# --- Right column: Production group(s) + month + line chart ---
with col2:
    st.header("Monthly Production Line Plot")
    
    # Multiple selection for production groups
    prod_groups = st.multiselect(
        "Select production group(s):",
        df["productiongroup"].unique(),
        default=df["productiongroup"].unique()
    )
    
    # Month selection
    month = st.selectbox(
        "Select a month:",
        list(range(1, 13)),
        format_func=lambda x: pd.to_datetime(f"2021-{x}-01").strftime("%B")
    )
    
    # Filter data
    df_filtered = df_area[
        (df_area["productiongroup"].isin(prod_groups)) &
        (df_area["starttime"].dt.month == month)
    ]
    
    if df_filtered.empty:
        st.warning("No data for this selection.")
    else:
        fig_line = px.line(
            df_filtered,
            x="starttime",
            y="quantitykwh",
            color="productiongroup",
            markers=True,
            title=f"Hourly Production in {price_area} ({pd.to_datetime(f'2021-{month}-01').strftime('%B')})"
        )
        st.plotly_chart(fig_line, use_container_width=True)

# ---------------------------------------------
# 4. Expander for data source
# ---------------------------------------------
with st.expander("Data Source"):
    st.write("""
    The data displayed in this dashboard is sourced from the ELHUB API, 
    containing hourly electricity production per price area and production group. 
    Data has been loaded into MongoDB and visualized interactively here.
    """)
