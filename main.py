import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="Pegelstationen", layout="wide")

API_URL_STATIONS = st.secrets["API_URL_STATIONS"]
API_URL_TSDATA = st.secrets["API_URL_TSDATA"]

st.title("Pegelstationen")


@st.cache_data(ttl=300)
def load_stations() -> pd.DataFrame:
  response = requests.get(API_URL_STATIONS, timeout=10)
  response.raise_for_status()
  df = pd.DataFrame(response.json())
  df["longitude"] = df["location"].str["longitude"]
  df["latitude"] = df["location"].str["latitude"]
  return df


@st.cache_data(ttl=60)
def get_station_data(station_id: str) -> pd.DataFrame:
  response = requests.get(
      API_URL_TSDATA, params={"station_id": station_id}, timeout=10
  )
  response.raise_for_status()
  payload = response.json()

  if not payload.get("data"):
    return pd.DataFrame()

  metriken = pd.DataFrame.from_dict(payload["metriken"], orient="index")
  messdaten = pd.DataFrame(payload["data"])
  messdaten["timestamp"] = pd.to_datetime(messdaten["timestamp"])
  messdaten = messdaten.drop(columns="station_id", errors="ignore")

  messdaten = messdaten.melt(
      id_vars="timestamp", var_name="metrik_id", value_name="value"
  )
  messdaten["metrik_name"] = messdaten["metrik_id"].map(metriken["metrik_name"])
  messdaten["metrik_einheit"] = messdaten["metrik_id"].map(
      metriken["metrik_einheit"]
  )
  return messdaten


try:
  stations = load_stations()
except requests.RequestException as e:
  st.error(f"Fehler beim Laden der Stationen: {e}")
  st.stop()

station_list = stations["station_id"].tolist()

# Startwert im Session State setzen
if "selected_station" not in st.session_state:
  st.session_state.selected_station = station_list[0]

col_map, col_data = st.columns([1, 1.5])

with col_map:
  stations["status"] = stations["station_id"].apply(
      lambda x: (
          "Ausgewählt"
          if x == st.session_state.selected_station
          else "Verfügbar"
      )
  )

  # Mittelpunkt aller Stationen für den Startausschnitt berechnen
  center_lat = stations["latitude"].mean()
  center_lon = stations["longitude"].mean()

  fig = px.scatter_map(
      stations,
      lat="latitude",
      lon="longitude",
      color="status",
      color_discrete_map={"Ausgewählt": "#FF4B4B", "Verfügbar": "#1F77B4"},
      hover_name="station_id",
      custom_data=["station_id"],
      center={"lat": center_lat, "lon": center_lon},
      zoom=7,
  )
  fig.update_traces(marker=dict(size=12))
  fig.update_layout(showlegend=False, margin={"r": 0, "t": 0, "l": 0, "b": 0})

  event = st.plotly_chart(
      fig,
      use_container_width=True,
      on_select="rerun",
      selection_mode="points",
      key="station_map",
  )

  if event and event.selection and event.selection.points:
    clicked_station = event.selection.points[0]["customdata"][0]
    if clicked_station != st.session_state.selected_station:
      st.session_state.selected_station = clicked_station
      st.rerun()

with col_data:
  station_id = st.selectbox(
      "Station auswählen (oder auf Karte klicken)",
      options=station_list,
      key="selected_station",
  )

  try:
    messdaten = get_station_data(station_id)
  except requests.RequestException as e:
    st.error(f"Fehler beim Laden der Messdaten: {e}")
    st.stop()

  if messdaten.empty:
    st.warning("Für diese Station liegen aktuell keine Messdaten vor.")
  else:
    alle_metriken = messdaten["metrik_name"].dropna().unique()

    # Alle Metriken nacheinander darstellen
    for metrik in alle_metriken:
      messdaten_single = (
          messdaten[messdaten["metrik_name"] == metrik]
          .dropna(subset=["value"])
          .sort_values("timestamp")
      )

      if messdaten_single.empty:
        continue

      einheit = messdaten_single["metrik_einheit"].iloc[0]
      aktuell = messdaten_single.iloc[-1]

      st.subheader(f"{metrik} ({einheit})")
      st.metric(
          label=(
              f"Aktueller Wert ({aktuell['timestamp'].strftime('%d.%m.%Y %H:%M')})"
          ),
          value=f"{aktuell['value']:.2f} {einheit}",
      )

      st.line_chart(
          data=messdaten_single,
          x="timestamp",
          y="value",
          y_label=f"{metrik} ({einheit})",
          x_label="Zeitpunkt",
      )
      st.divider()
