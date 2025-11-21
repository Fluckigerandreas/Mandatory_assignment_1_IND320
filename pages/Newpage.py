import streamlit as st
import pandas as pd
from pymongo import MongoClient
import certifi
import plotly.express as px

# -------------------------------
# LOAD PRODUCTION DATA
# -------------------------------
@st.cache_data(show_spinner="Loading production data...")
def load_production_years():
    client = MongoClient(st.secrets["mongo"]["uri"], tls=True, tlsCAFile=certifi.where())
    db = client["Elhub"]
    df = pd.DataFrame(list(db["Data"].find()))
    
    if df.empty:
        return pd.DataFrame()  # empty fallback

    # Convert starttime to datetime safely
    df["starttime"] = pd.to_datetime(df["starttime"], errors="coerce", utc=True)
    df = df.dropna(subset=["starttime"])

    # Extract year
    df["year"] = df["starttime"].dt.year

    return df[["pricearea", "productiongroup", "year"]]

# -------------------------------
# STREAMLIT APP
# -------------------------------
st.title("Production Years from Elhub")

prod_df = load_production_years()

if prod_df.empty:
    st.warning("No production data found in MongoDB.")
else:
    # Let user choose category
    category = st.selectbox("Select category", options=["pricearea", "productiongroup"])

    # Show unique years per category
    unique_years = prod_df.groupby(category)["year"].unique().reset_index()
    unique_years["year"] = unique_years["year"].apply(lambda x: sorted(list(x)))

    st.subheader(f"Unique Years for each {category.capitalize()}")
    st.dataframe(unique_years)
