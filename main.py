import pandas as pd
import requests
import streamlit as st

st.title("🌊 Pegelstationen")

@st.cache_data(ttl=300)
def load_stations():
  response = requests.get("https://pegel.thw-forchheim.de/get_stations", timeout=10)
  response.raise_for_status()
  return response.json()

raw_data = load_stations()
st.write(raw_data)
