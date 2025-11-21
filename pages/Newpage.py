import streamlit as st
import pandas as pd
from pymongo import MongoClient
import certifi
import plotly.express as px

# -------------------------------
# CACHE DATA LOADING
# -------------------------------
@st.cache_data(show_spinner="Loading data from MongoDB...")
def load_data():
    """Load data from MongoDB with caching."""
    uri = st.secrets["mongo"]["uri"]
    ca = certifi.where()
    client = MongoClient(uri, tls=True, tlsCAFile=ca)
    db = client['Elhub']
    collection = db['Data']

    data = list(collection.find())
    if not data:
        return pd.DataFrame()  # Empty DataFrame fallback

    df = pd.DataFrame(data)

    # Force conversion to datetime
    df["starttime"] = pd.to_datetime(df["starttime"], errors="coerce")
    df = df.dropna(subset=["starttime"])

    # Remove duplicates
    df = df.drop_duplicates(subset=["pricearea", "productiongroup", "starttime"], keep="first").reset_index(drop=True)
    return df

# -------------------------------
# STREAMLIT APP
# -------------------------------
st.title("Check MongoDB Data by Year")

df = load_data()

if df.empty:
    st.warning("No data found in MongoDB.")
else:
    # Extract year
    df["year"] = df["starttime"].dt.year

    # Choose category to inspect
    category = st.selectbox("Select category", options=["pricearea", "productiongroup"])

    # Group by category and list unique years
    unique_years = df.groupby(category)["year"].unique().reset_index()
    unique_years["year"] = unique_years["year"].apply(lambda x: sorted(list(x)))

    st.subheader(f"Unique Years for Each {category.capitalize()}")
    st.dataframe(unique_years)

    # Optional: plot years per category
    st.subheader(f"Years Distribution per {category.capitalize()}")
    # Explode the list of years so we can plot
    exploded_df = unique_years.explode("year")
    fig = px.bar(
        exploded_df,
        x=category,
        y="year",
        text="year",
        title=f"Years available for each {category}",
        labels={"year": "Year", category: category.capitalize()},
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)
