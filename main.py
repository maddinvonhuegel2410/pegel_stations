import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="Pegelstationen", layout="wide")

API_URL_STATIONS = st.secrets["API_URL_STATIONS"]
API_URL_TSDATA = st.secrets["API_URL_TSDATA"]
API_URL_AUTH = st.secrets["API_URL_AUTH"]

st.title("Pegelstationen")


def authenticate_user(username: str, password: str) -> tuple[bool, str | None]:
    """Sendet die Login-Daten an das AWS API Gateway und gibt (Erfolg, Rolle) zurück."""
    payload = {"username": username, "password": password}
    
    try:
        response = requests.post(API_URL_AUTH, json=payload, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("authenticated", False):
                return True, data.get("role", "viewer")
        return False, None
    except requests.exceptions.RequestException:
        st.error("Verbindung zum Authentifizierungs-Server fehlgeschlagen. Bitte später erneut versuchen.")
        return False, None

def login_screen():
    """Zeigt die Login-Maske an."""
    st.title("Pegelstationen")
    st.write("Bitte melde dich mit deinen Zugangsdaten an.")
    
    with st.form("login_form"):
        username = st.text_input("Benutzername")
        password = st.text_input("Passwort", type="password")
        submit = st.form_submit_button("Einloggen")
        
        if submit:
            if not username or not password:
                st.warning("Bitte Benutzername und Passwort eingeben.")
                return
                
            with st.spinner("Zugangsdaten werden geprüft..."):
                is_auth, role = authenticate_user(username.strip(), password)
                
            if is_auth:
                st.session_state["authenticated"] = True
                st.session_state["username"] = username.strip()
                st.session_state["role"] = role
                st.rerun()
            else:
                st.error("Benutzername oder Passwort ist falsch.")

# --- ZUGRIFFSKONTROLLE ---
if not st.session_state.get("authenticated", False):
    login_screen()
    st.stop()


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


def prepare_csv(df: pd.DataFrame) -> bytes:
  # Tabelle für den Export wieder ins breite Format bringen
  df_export = df.copy()
  df_export["spalte"] = (
      df_export["metrik_name"] + " (" + df_export["metrik_einheit"] + ")"
  )
  pivoted = df_export.pivot(
      index="timestamp", columns="spalte", values="value"
  ).sort_index()
  return pivoted.to_csv(sep=";", decimal=",").encode("utf-8-sig")


try:
  stations = load_stations()
except requests.RequestException as e:
  st.error(f"Fehler beim Laden der Stationen: {e}")
  st.stop()

station_list = stations["station_id"].tolist()

# Startwert im Session State setzen
if "selected_station" not in st.session_state:
  st.session_state.selected_station = station_list

col_map, col_data = st.columns([1, 1.5])

with col_map:
  stations["status"] = stations["station_id"].apply(
      lambda x: (
          "Ausgewählt"
          if x == st.session_state.selected_station
          else "Verfügbar"
      )
  )

  center_lat = stations["latitude"].mean()
  center_lon = stations["longitude"].mean()

  fig_map = px.scatter_map(
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
  fig_map.update_traces(marker=dict(size=12))
  fig_map.update_layout(
      showlegend=False, margin={"r": 0, "t": 0, "l": 0, "b": 0}
  )

  event = st.plotly_chart(
      fig_map,
      use_container_width=True,
      on_select="rerun",
      selection_mode="points",
      key="station_map",
  )

  if event and event.selection and event.selection.points:
    clicked_station = event.selection.points["customdata"]
    if clicked_station != st.session_state.selected_station:
      st.session_state.selected_station = clicked_station
      st.rerun()

with col_data:
  col_select, col_download = st.columns([2, 1], vertical_alignment="bottom")

  with col_select:
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
    with col_download:
      csv_bytes = prepare_csv(messdaten)
      st.download_button(
          label="📥 CSV herunterladen",
          data=csv_bytes,
          file_name=f"messdaten_{station_id}.csv",
          mime="text/csv",
          use_container_width=True,
      )

    alle_metriken = messdaten["metrik_name"].dropna().unique()

    for metrik in alle_metriken:
      messdaten_single = (
          messdaten[messdaten["metrik_name"] == metrik]
          .dropna(subset=["value"])
          .sort_values("timestamp")
      )

      if messdaten_single.empty:
        continue

      einheit = messdaten_single["metrik_einheit"].values[0]
      aktuell = messdaten_single.iloc[-1]

      st.subheader(f"{metrik} ({einheit})")
      st.metric(
          label=(
              f"Aktueller Wert ({aktuell['timestamp'].strftime('%d.%m.%Y %H:%M')})"
          ),
          value=f"{aktuell['value']:.2f} {einheit}",
      )

      fig_line = px.line(
          messdaten_single,
          x="timestamp",
          y="value",
          labels={
              "timestamp": "Zeitpunkt",
              "value": f"{metrik} ({einheit})",
          },
      )
      # Y-Achse eng an den tatsächlichen Wertebereich anpassen
      fig_line.update_yaxes(autorange=True, fixedrange=False)
      fig_line.update_layout(
          height=300,
          margin={"r": 10, "t": 10, "l": 10, "b": 10},
          hovermode="x unified",
      )

      st.plotly_chart(fig_line, use_container_width=True)
      st.divider()
