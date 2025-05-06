import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gtfs_kit as gk
from datetime import datetime

# Cargar datos
feed = gk.read_feed("gtfs_bilbobus_barrios_altitud_CORREGIDO.zip", dist_units="km")
calendar = feed.calendar.copy()
calendar["start_date"] = pd.to_datetime(calendar["start_date"], format="%Y%m%d")
calendar["end_date"] = pd.to_datetime(calendar["end_date"], format="%Y%m%d")
dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo", "Todo el periodo"]

# Preparar selector de líneas
rutas = feed.routes.copy()
rutas["selector"] = rutas["route_short_name"] + " · " + rutas["route_long_name"]
rutas = rutas.sort_values("route_short_name")

# Interfaz
st.title("🚍 iLoGus · Visor de Líneas de Bilbobus")
st.markdown("Visualiza los viajes programados por línea y día de la semana, con horarios y trazado geográfico.")

linea_seleccionada = st.selectbox("Selecciona una línea:", rutas["selector"])
dia_seleccionado = st.selectbox("Selecciona un día:", dias_semana)

# Identificar route_id
route_short_name = linea_seleccionada.split(" · ")[0]
route_row = rutas[rutas["route_short_name"] == route_short_name].iloc[0]
route_id = route_row["route_id"]
nombre_largo = route_row["route_long_name"]

# Filtrar trips
trips_linea = feed.trips[feed.trips["route_id"] == route_id]
servicio_ids = set()

if dia_seleccionado != "Todo el periodo":
    dia_num = dias_semana.index(dia_seleccionado)
    hoy = pd.Timestamp.today().normalize()

    for _, row in calendar.iterrows():
        if row.start_date <= hoy <= row.end_date and row.iloc[1 + dia_num] == 1:
            servicio_ids.add(row.service_id)

    trips_linea = trips_linea[trips_linea["service_id"].isin(servicio_ids)]

# Unir con horarios
primeras_paradas = feed.stop_times[feed.stop_times["stop_sequence"] == 1][["trip_id", "departure_time"]]
trips_con_horario = trips_linea.merge(primeras_paradas, on="trip_id", how="left")

# Agrupar por shape_id
agrupado = trips_con_horario.groupby("shape_id").agg({
    "trip_id": list,
    "departure_time": list,
    "trip_headsign": lambda x: x.mode().values[0] if not x.mode().empty else ""
}).reset_index()
agrupado["num_trips"] = agrupado["trip_id"].apply(len)

# ✅ Función corregida
def calcular_frecuencia(horas):
    horas_limpias = [h for h in horas if h and h.strip()]
    if len(horas_limpias) < 2:
        return "No disponible"
    try:
        tiempos = [datetime.strptime(h, "%H:%M:%S") for h in horas_limpias]
        diferencias = [(t2 - t1).seconds for t1, t2 in zip(tiempos, tiempos[1:])]
        media = int(round(sum(differences) / len(differences) / 60))
        return f"cada {media} minutos"
    except Exception:
        return "Formato de hora no válido"

# Mostrar recorridos
for _, row in agrupado.iterrows():
    shape_id = row["shape_id"]
    destino = row["trip_headsign"]
    horas = sorted(row["departure_time"])
    frecuencia = calcular_frecuencia(horas)

    st.markdown(f"### 🚌 Línea {route_short_name} · {destino}")
    st.markdown(f"📆 Día: {dia_seleccionado} &nbsp;&nbsp;&nbsp;&nbsp; 🧭 {len(horas)} salidas programadas &nbsp;&nbsp;&nbsp;&nbsp; ⏱️ Frecuencia media: {frecuencia}")

    # Mostrar tabla de horarios (12 columnas, sin scroll)
    filas = [horas[i:i+12] for i in range(0, len(horas), 12)]
    html = "<table style='font-size:11px; text-align:center; border-spacing:4px;'>"
    for fila in filas:
        html += "<tr>" + "".join(f"<td>{h}</td>" for h in fila) + "</tr>"
    html += "</table>"
    st.markdown(html, unsafe_allow_html=True)

    # Mapa
    shape_df = feed.shapes[feed.shapes["shape_id"] == shape_id].sort_values("shape_pt_sequence")
    coords = shape_df[["shape_pt_lat", "shape_pt_lon"]].values.tolist()
    mapa = folium.Map(location=coords[len(coords)//2], zoom_start=13)
    folium.PolyLine(coords, color="blue", weight=4).add_to(mapa)

    # Paradas del trip representativo
    trip_rep = row["trip_id"][0]
    paradas_ids = feed.stop_times[feed.stop_times["trip_id"] == trip_rep].sort_values("stop_sequence")["stop_id"].tolist()
    stops_df = feed.stops[feed.stops["stop_id"].isin(paradas_ids)].set_index("stop_id")

    for stop_id in paradas_ids:
        parada = stops_df.loc[stop_id]
        lat = parada["stop_lat"]
        lon = parada["stop_lon"]
        nombre = parada["stop_name"]

        # Horarios por parada
        horarios = feed.stop_times[
            (feed.stop_times["stop_id"] == stop_id) &
            (feed.stop_times["trip_id"].isin(row["trip_id"]))
        ]["departure_time"].tolist()

        minutos = [int(h.split(":")[1]) for h in horarios if h and h.strip()]
        patron = pd.Series(minutos).mode()
        if len(patron) >= 1 and minutos.count(patron[0]) > len(minutos) * 0.6:
            popup_text = f"<b>{nombre}</b><br/><span style='font-size:11px;'>🕒 Paso aproximado: minuto {patron[0]:02d} de cada hora</span>"
        else:
            bloques = [horarios[i:i+6] for i in range(0, len(horarios), 6)]
            lineas = "<br/>".join(" • ".join(b) for b in bloques[:5])
            popup_text = f"<b>{nombre}</b><br/><span style='font-size:11px;'>🕒 Horarios teóricos:<br/>{lineas}</span>"

        folium.CircleMarker(
            location=(lat, lon),
            radius=4,
            color="red",
            fill=True,
            fill_opacity=0.7,
            popup=folium.Popup(popup_text, max_width=300)
        ).add_to(mapa)

    st_folium(mapa, width=700, height=450)
