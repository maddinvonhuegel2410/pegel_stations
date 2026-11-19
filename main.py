import pandas as pd
import requests
import streamlit as st
import plotly.express as px

API_URL_STATIONS = st.secrets["API_URL_STATIONS"]
API_URL_TSDATA = st.secrets["API_URL_TSDATA"]

st.title("🌊 Pegelstationen")

@st.cache_data(ttl=60)
def load_stations():
  response = requests.get(API_URL_STATIONS, timeout=10)
  response.raise_for_status()
  return response.json()

stations = pd.DataFrame(load_stations())
stations["longitude"] = stations["location"].apply(lambda x: x["longitude"])
stations["latitude"] = stations["location"].apply(lambda x: x["latitude"])

fig = px.scatter_map(stations, lat="latitude", lon="longitude",color="station_id")
st.plotly_chart(fig)

station_id = st.selectbox(
    "Station auswählen",
    list(stations["station_id"]),
    index=0
)
