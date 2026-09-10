# 🗺️ My First WebGIS: Spatial Field Assessment Tool

An interactive, web-based spatial field assessment application designed for dynamic on-site observations, environmental audits, and spatial data collection. 

This platform enables researchers, field surveyors, and urban assessors to systematically record, map, and evaluate physical spatial attributes, public space quality, accessibility features, and localized environmental conditions in real time.

---

## 🌟 Key Features

* **Interactive Mapping Interface:** Pan, zoom, and explore vector and raster spatial layers with smooth performance across desktop and mobile devices in the field.
* **On-Site Field Data Entry:** Capture geolocated observations, drop spatial markers, and fill out site evaluation forms directly on the interactive map.
* **Structured Observation Workflows:** Record standardized spatial metrics, infrastructure quality scores, accessibility barriers, and behavioral usage patterns.
* **Layer Management & Spatial Overlays:** Toggle between baseline layers (OpenStreetMap, high-resolution satellite imagery, light/dark basemaps) and contextual vector datasets.
* **Mobile-Optimized Layout:** Lightweight and responsive UI built for field deployment on tablets and mobile devices.

---

## 🛠️ Tech Stack & Libraries

* **Frontend:** HTML5, CSS3, JavaScript (ES6+)
* **Mapping Engine:** [Leaflet.js](https://leafletjs.com/) / [Mapbox GL JS](https://docs.mapbox.com/mapbox-gl-js/)
* **Spatial Data Formats:** GeoJSON, KML, Shapefile / TopoJSON
* **Styling & Components:** Custom CSS / Bootstrap / Tailwind CSS
* **Data Storage / Backend:** Supabase / Firebase / GeoServer *(Update based on your setup)*

---

## 📁 Repository Structure

```text
my-first-webgis/
├── css/
│   └── style.css          # Custom layout and mobile field styling
├── js/
│   ├── main.js            # Core WebGIS & Leaflet map initialization
│   └── field-assessment.js# Form logic & spatial data capture functions
├── data/
│   ├── study-area.geojson # Spatial boundaries and baseline site layers
│   └── assessment-schema.json # Field evaluation criteria and schema
├── assets/                # Custom markers, icons, and media
├── index.html             # Main entry point and assessment interface
└── README.md              # Project documentation