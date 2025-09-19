import streamlit as st
import pandas as pd 

data = pd.read_csv("/workspaces/blank-app/open-meteo-subset.csv")
print(data)