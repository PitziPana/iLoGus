import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gtfs_kit as gk
from datetime import datetime
from PIL import Image

# Mostrar el logo
logo = Image.open("16pitzi.jpeg")
st.image(logo, width=120)

# Título y descripción
st.title("🚍 iLoGus · Visor de Líneas de Bilbobus")
st.markdown("Visualiza los viajes programados por línea y día de la semana, con horarios y trazado geográfico.")

# Cargar feed GTFS
feed = gk.read_feed("gtfs_bilbobus_barrios_altitud_CORREGIDO.zip", dist_units="km")

# Preparar calendario y días
calendar = feed.calendar.copy()
calendar["start_date"] = pd.to_datetime(calendar["start_date"], format="%Y%m%d")
calendar["end_date"] = pd.to_datetime(calendar["end_date"], format="%Y%m%d")
dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo", "Todo el periodo"]

# Selector de líneas
rutas = feed.routes.copy()
rutas["selector"] = rutas["route_short_name"] + " · " + rutas["route_long_name"]
rutas = rutas.sort_values("route_short_name")

# Selección por interfaz
linea_seleccionada = st.selectbox("Selecciona una línea:", rutas["selector"])
dia_seleccionado = st.selectbox("Selecciona un día:", dias_semana)

# Identificar route_id
route_short_name = linea_seleccionada.split(" · ")[0]
route_row = rutas[rutas["route_short_name"] == route_short_name].iloc[0]
route_id = route_row["route_id"]
nombre_largo = route_row["route_long_name"]

# Filtrar trips de la línea y día
trips_linea = feed.trips[feed.trips["route_id"] == route_id]
servicio_ids = set()

if dia_seleccionado != "Todo el periodo":
    dia_num = dias_semana.index(dia_seleccionado)
    hoy = pd.Timestamp.today().normalize()

    for _, row in calendar.iterrows():
        if row.start_date <= hoy <= row.end_date and row.iloc[1 + dia_num] == 1:
            servicio_ids.add(row.service_id)

    trips_linea = trips_linea[trips_linea["service_id"].isin(servicio_ids)]

# Unir con horarios de primera parada
primeras_paradas = feed.stop_times[feed.stop_times["stop_sequence"] == 1][["trip_id", "departure_time"]]
trips_con_horario = trips_linea.merge(primeras_paradas, on="trip_id", how="left")

# Agrupar por shape_id
agrupado = trips_con_horario.groupby("shape_id").agg({
    "trip_id": list,
    "departure_time": list,
    "trip_headsign": lambda x: x.mode().values[0] if not x.mode().empty else ""
}).reset_index()
agrupado["num_trips"] = agrupado["trip_id"].apply(len)

# Función para calcular frecuencia
def calcular_frecuencia(horas):
    try:
        tiempos = [datetime.strptime(h, "%H:%M:%S") for h in horas]
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

    st.markdown(f"### 🚌 Línea {route_short_name} · {nombre_largo.upper()}")
    st.markdown(f"📅 Día: {dia_seleccionado} &nbsp;&nbsp;&nbsp;&nbsp; 🕒 {len(horas)} salidas programadas &nbsp;&nbsp;&nbsp;&nbsp; ⏱️ Frecuencia media: {frecuencia}")

    # Tabla de horarios en columnas ajustadas
    filas = [horas[i:i+12] for i in range(0, len(horas), 12)]
    html = "<table style='font-size:11px; text-align:center; border-spacing:4px;'>"
    for fila in filas:
        html += "<tr>" + "".join(f"<td>{h}</td>" for h in fila) + "</tr>"
    html += "</table>"
    st.markdown(html, unsafe_allow_html=True)

    # Mapa de recorrido
    shape_df = feed.shapes[feed.shapes["shape_id"] == shape_id].sort_values("shape_pt_sequence")
    coords = shape_df[["shape_pt_lat", "shape_pt_lon"]].values.tolist()
    mapa = folium.Map(location=coords[len(coords)//2], zoom_start=13)
    folium.PolyLine(coords, color="blue", weight=4).add_to(mapa)

    # Paradas para todos los trips
    trips_usar = row["trip_id"]
    stop_times_sel = feed.stop_times[feed.stop_times["trip_id"].isin(trips_usar)]
    todas_paradas = stop_times_sel["stop_id"].unique()
    stops_df = feed.stops[feed.stops["stop_id"].isin(todas_paradas)].set_index("stop_id")

    for stop_id in todas_paradas:
        parada = stops_df.loc[stop_id]
        lat = parada["stop_lat"]
        lon = parada["stop_lon"]
        nombre = parada["stop_name"]

        horarios = stop_times_sel[stop_times_sel["stop_id"] == stop_id]["departure_time"].tolist()
        minutos = [int(h.split(":")[1]) for h in horarios]
        patron = pd.Series(minutos).mode()
        if len(patron) >= 1 and minutos.count(patron[0]) > len(minutos) * 0.6:
            popup_text = f"<b>{nombre}</b><br/><span style='font-size:11px;'>🕒 Paso aproximado: minuto {patron[0]:02d} de cada hora</span>"
        else:
            bloques = [horarios[i:i+6] for i in range(0, len(horarios), 6)]
            lineas = "<br/>".join(" • ".join(b) for b in bloques[:5])
            popup_text = f"<b>{nombre}</b><br/><span style='font-size:11px;'>🕒 Horarios teóricos:<br/>{lineas}</span>"

        folium.CircleMarker([lat, lon], radius=4, color="red", fill=True, fill_opacity=0.7, popup=folium.Popup(popup_text, max_width=300)).add_to(mapa)

    st_folium(mapa, width=800, height=450)
