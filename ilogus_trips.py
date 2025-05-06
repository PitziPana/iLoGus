import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gtfs_kit as gk

# 🚌 Cargar feed GTFS
feed = gk.read_feed("gtfs_bilbobus_barrios_altitud_CORREGIDO.zip", dist_units="km")

# 📅 Preparar calendario
calendar = feed.calendar.copy()
calendar["start_date"] = pd.to_datetime(calendar["start_date"], format="%Y%m%d")
calendar["end_date"] = pd.to_datetime(calendar["end_date"], format="%Y%m%d")
dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo", "Todo el periodo"]

# 🔽 Selector de líneas
rutas = feed.routes.copy()
rutas["selector"] = rutas["route_short_name"] + " · " + rutas["route_long_name"]
rutas = rutas.sort_values("route_short_name")

# 🧭 Interfaz
st.title("🚍 iLoGus · Visor de Líneas de Bilbobus")
st.markdown("Visualiza los viajes programados por línea y día de la semana, con horarios y trazado geográfico.")

linea_seleccionada = st.selectbox("Selecciona una línea:", rutas["selector"])
dia_seleccionado = st.selectbox("Selecciona un día:", dias_semana)

# 🧩 route_id seleccionado
route_short_name = linea_seleccionada.split(" · ")[0]
route_id = rutas[rutas["route_short_name"] == route_short_name].iloc[0]["route_id"]

# 🚏 Filtrar viajes
trips_linea = feed.trips[feed.trips["route_id"] == route_id]
servicio_ids = set()

if dia_seleccionado != "Todo el periodo":
    dia_num = dias_semana.index(dia_seleccionado)
    hoy = pd.Timestamp.today().normalize()

    for _, row in calendar.iterrows():
        if row.start_date <= hoy <= row.end_date and row.iloc[1 + dia_num] == 1:
            servicio_ids.add(row.service_id)

    trips_linea = trips_linea[trips_linea["service_id"].isin(servicio_ids)]

# ⏰ Añadir horarios
primeras_paradas = feed.stop_times[feed.stop_times["stop_sequence"] == 1][["trip_id", "departure_time"]]
trips_con_horario = trips_linea.merge(primeras_paradas, on="trip_id", how="left")

# 🧭 Agrupar por shape_id
agrupado = trips_con_horario.groupby("shape_id").agg({
    "trip_id": list,
    "departure_time": list,
    "trip_headsign": lambda x: x.mode().values[0] if not x.mode().empty else ""
}).reset_index()
agrupado["num_trips"] = agrupado["trip_id"].apply(len)

if agrupado.empty:
    st.warning("⚠️ No hay viajes disponibles para esta línea en el día seleccionado.")
    st.stop()

# 🔁 Mostrar cada recorrido
for _, row in agrupado.iterrows():
    shape_id = row["shape_id"]
    destino = row["trip_headsign"]
    st.markdown(f"### 🚌 Recorrido hacia **{destino}** · {row['num_trips']} salidas programadas")

    # 🧾 Tabla compacta en 3 columnas
    horarios = list(zip(row["trip_id"], row["departure_time"]))
    bloques = [horarios[i:i+3] for i in range(0, len(horarios), 3)]

    html_tabla = "<table style='font-size:14px;'>"
    html_tabla += "<tr><th>Recorrido programado</th><th>Hora de salida</th>" * 3 + "</tr>"
    for bloque in bloques:
        html_tabla += "<tr>"
        for trip_id, hora in bloque:
            html_tabla += f"<td>{trip_id}</td><td>{hora}</td>"
        if len(bloque) < 3:
            html_tabla += "<td></td><td></td>" * (3 - len(bloque))
        html_tabla += "</tr>"
    html_tabla += "</table>"

    st.markdown(html_tabla, unsafe_allow_html=True)

    # 🗺️ Trazado del shape
    shape_df = feed.shapes[feed.shapes["shape_id"] == shape_id].sort_values("shape_pt_sequence")
    coords = shape_df[["shape_pt_lat", "shape_pt_lon"]].values.tolist()
    mapa = folium.Map(location=coords[len(coords)//2], zoom_start=13)
    folium.PolyLine(coords, color="blue", weight=4).add_to(mapa)

    # 📍 Añadir paradas del recorrido
    trip_representativo = row["trip_id"][0]
    stops_ids = feed.stop_times[feed.stop_times["trip_id"] == trip_representativo].sort_values("stop_sequence")["stop_id"].tolist()
    stops_df = feed.stops[feed.stops["stop_id"].isin(stops_ids)].set_index("stop_id")

    for stop_id in stops_ids:
        parada = stops_df.loc[stop_id]
        lat = parada["stop_lat"]
        lon = parada["stop_lon"]
        nombre = parada["stop_name"]

        # Obtener horarios de paso por esa parada
        horarios_parada = feed.stop_times[
            (feed.stop_times["stop_id"] == stop_id) & (feed.stop_times["trip_id"].isin(row["trip_id"]))
        ].sort_values("departure_time")["departure_time"].tolist()

        popup_text = f"<b>{nombre}</b><br/>"
        popup_text += "🕒 Salidas:<br/>" + "<br/>".join(horarios_parada)

        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            color="darkred",
            fill=True,
            fill_color="red",
            fill_opacity=0.9,
            tooltip=nombre,
            popup=folium.Popup(popup_text, max_width=250)
        ).add_to(mapa)

    # Mostrar mapa
    st_folium(mapa, width=750, height=450)
    st.markdown("---")
