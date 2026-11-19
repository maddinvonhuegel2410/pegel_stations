import pandas as pd
import requests
import streamlit as st
import plotly.express as px

API_URL_STATIONS = st.secrets["API_URL_STATIONS"]
API_URL_TSDATA = st.secrets["API_URL_TSDATA"]

st.title("Pegelstationen")

@st.cache_data(ttl=60)
def load_stations():
  response = requests.get(API_URL_STATIONS, timeout=10)
  response.raise_for_status()
  return response.json()

def get_station_data(station_id):
    url = f"{API_URL_TSDATA}?station_id={station_id}"
    response = requests.get(url)
    payload = response.json()

    metriken = pd.DataFrame([payload["metriken"][i] for i in payload["metriken"]])
    metriken = metriken.set_index("metrik_id")
    messdaten = pd.DataFrame(payload["data"])
    messdaten["timestamp"] = pd.to_datetime(messdaten["timestamp"])
    messdaten = messdaten.drop(columns="station_id")

    messdaten = messdaten.melt(id_vars="timestamp", var_name="metrik_id", value_name="value")
    messdaten["metrik_name"] = messdaten["metrik_id"].map(metriken.to_dict()["metrik_name"])
    messdaten["metrik_einheit"] = messdaten["metrik_id"].map(metriken.to_dict()["metrik_einheit"])
    return messdaten

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

messdaten = get_station_data(station_id="MHP_OFOR_1")

st.table(messdaten)
