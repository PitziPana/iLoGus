import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gtfs_kit as gk

# Cargar feed GTFS
feed = gk.read_feed("gtfs_bilbobus_barrios_altitud_CORREGIDO.zip", dist_units="km")

# Preparar calendario
calendar = feed.calendar.copy()
calendar["start_date"] = pd.to_datetime(calendar["start_date"], format="%Y%m%d")
calendar["end_date"] = pd.to_datetime(calendar["end_date"], format="%Y%m%d")

# Preparar selector de días
dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo", "Todo el periodo"]

# Preparar líneas con nombre corto y largo
rutas = feed.routes.copy()
rutas["selector"] = rutas["route_short_name"] + " · " + rutas["route_long_name"]
rutas = rutas.sort_values("route_short_name")

# Interfaz Streamlit
st.title("🚍 iLoGus · Visor de Líneas de Bilbobus")
st.markdown("Visualiza los viajes programados por línea y día de la semana, con horarios y trazado geográfico.")

linea_seleccionada = st.selectbox("Selecciona una línea:", rutas["selector"])
dia_seleccionado = st.selectbox("Selecciona un día:", dias_semana)

# Extraer route_id
route_short_name = linea_seleccionada.split(" · ")[0]
route_id = rutas[rutas["route_short_name"] == route_short_name].iloc[0]["route_id"]

# Filtrar trips de la línea
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
    "departure_time": list
}).reset_index()
agrupado["num_trips"] = agrupado["trip_id"].apply(len)

if agrupado.empty:
    st.warning("⚠️ No hay TRIPS disponibles para esta selección.")
    st.stop()

# Mostrar resultados
for _, row in agrupado.iterrows():
    st.markdown(f"### Shape ID: `{row['shape_id']}` · {row['num_trips']} viajes")

    horarios = pd.DataFrame({
        "trip_id": row["trip_id"],
        "hora_salida": row["departure_time"]
    })
    st.dataframe(horarios, hide_index=True, use_container_width=True)

    # Crear mapa
    shape_df = feed.shapes[feed.shapes["shape_id"] == row["shape_id"]].sort_values("shape_pt_sequence")
    coords = shape_df[["shape_pt_lat", "shape_pt_lon"]].values.tolist()
    mapa = folium.Map(location=coords[len(coords)//2], zoom_start=13)
    folium.PolyLine(coords, color="blue", weight=4).add_to(mapa)

    st_folium(mapa, width=700, height=400)
    st.markdown("---")
