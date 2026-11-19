import pandas as pd
import requests
import streamlit as st
import plotly.express as px

API_URL = st.secrets["API_URL"]
st.title("🌊 Pegelstationen")

@st.cache_data(ttl=60)
def load_stations():
  response = requests.get(API_URL, timeout=10)
  response.raise_for_status()
  return response.json()

stations = pd.DataFrame(load_stations())
stations["longitude"] = stations["location"].apply(lambda x: x["longitude"])
stations["latitude"] = stations["location"].apply(lambda x: x["latitude"])

fig = px.scatter_map(stations, lat="latitude", lon="longitude",color="station_id")
st.plotly_chart(fig)
