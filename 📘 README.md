# iLoGus

**iLoGus** es un visor interactivo de líneas de autobús urbanas basado en datos GTFS, desarrollado con Streamlit. Permite consultar los viajes (trips) programados por línea y día de la semana, mostrando los horarios de salida y el trazado real sobre el mapa.

---

## 🚀 ¿Qué ofrece?

- Selección de línea por número y nombre completo.
- Filtro por día de la semana o todo el periodo.
- Listado de trips con hora de salida.
- Agrupación por recorridos (`shape_id`).
- Visualización geográfica del trazado de cada viaje.

---

## 📂 Archivos incluidos

- `ilogus_trips.py` → Script principal de la app.
- `gtfs_bilbobus_barrios_altitud_CORREGIDO.zip` → Archivo GTFS corregido con barrios y altitud.
- `requirements.txt` → Librerías necesarias para ejecutar el proyecto.

---

## ▶️ Cómo ejecutarlo en local

1. Clona este repositorio:

```bash
git clone https://github.com/PitziPana/iLoGus.git
cd iLoGus
