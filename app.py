Site                City          Users
Midland Park        Wellington    35
Te Papa Plaza       Wellington    18
Riddiford Street    Wellington    42
Cuba Street         Wellington    27

import json
import folium
from folium.plugins import Draw
import geopandas as gpd
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title="My First WebGIS", layout="wide")

st.title("🗺️ Interactive WebGIS Digitizer")
st.write("Draw points, lines, or polygons on the map using the toolbar on the left.")

# Setup layout: Map on left, GeoJSON inspector on right
col1, col2 = st.columns([3, 2])

with col1:
    # Initialize Folium Map centered on Wellington
    m = folium.Map(location=[-41.2865, 174.7762], zoom_start=13, tiles="CartoDB positron")

    # Add Draw Control (allows points, lines, polygons, rectangles)
    draw_control = Draw(
        export=True,
        filename="digitized_features.geojson",
        position="topleft",
        draw_options={
            "polyline": True,
            "polygon": True,
            "circle": False,
            "circlemarker": False,
            "marker": True,
            "rectangle": True,
        },
        edit_options={"edit": True, "remove": True},
    )
    draw_control.add_to(m)

    # Render map and catch draw events
    output = st_folium(m, width="100%", height=550)

with col2:
    st.subheader("📌 Digitized Features Data")

    # Extract drawings from map output state
    all_drawings = output.get("all_drawings") if output else None

    if all_drawings and len(all_drawings) > 0:
        st.success(f"Captured {len(all_drawings)} feature(s)!")

        # Convert raw drawings into a GeoDataFrame
        try:
            geojson_data = {
                "type": "FeatureCollection",
                "features": all_drawings
            }
            gdf = gpd.GeoDataFrame.from_features(geojson_data, crs="EPSG:4326")
            
            # Display attribute summary table
            st.write("### Feature Summary")
            st.dataframe(gdf[["geometry"]], use_container_width=True)

            # Download button for spatial file
            geojson_str = json.dumps(geojson_data, indent=2)
            st.download_button(
                label="📥 Download GeoJSON File",
                data=geojson_str,
                file_name="digitized_features.geojson",
                mime="application/json"
            )

            # Raw GeoJSON Viewer
            with st.expander("View Raw GeoJSON Structure"):
                st.json(geojson_data)

        except Exception as e:
            st.error(f"Error parsing geometries: {e}")
    else:
        st.info("Use the drawing tools on the map to place markers or draw shapes. Drawn items will display here automatically.")