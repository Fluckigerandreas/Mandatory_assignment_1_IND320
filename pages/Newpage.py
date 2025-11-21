import streamlit as st
import pandas as pd
from pymongo import MongoClient
import certifi

@st.cache_data(show_spinner="Loading data from MongoDB...")
def load_data():
    uri = st.secrets["mongo"]["uri"]
    ca = certifi.where()
    client = MongoClient(uri, tls=True, tlsCAFile=ca)
    db = client['Elhub']
    collection = db['Data']

    data = list(collection.find())
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df["starttime"] = pd.to_datetime(df["starttime"])
    df = df.drop_duplicates(subset=["pricearea", "productiongroup", "starttime"], keep="first").reset_index(drop=True)
    return df

# Load data
df = load_data()

if df.empty:
    st.warning("No data found in MongoDB.")
else:
    # Extract year
    df["year"] = df["starttime"].dt.year

    st.subheader("Unique Years per Category")

    # Choose category
    category = st.selectbox("Select category", options=["pricearea", "productiongroup"])

    # Group by category and list unique years
    unique_years = df.groupby(category)["year"].unique().reset_index()
    unique_years["year"] = unique_years["year"].apply(lambda x: sorted(list(x)))  # Sort years

    st.dataframe(unique_years)
