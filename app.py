import json
import folium
from folium.plugins import Draw
import geopandas as gpd
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title="My First WebGIS", layout="wide")

st.title("🗺️ Interactive WebGIS Digitizer")
st.write("Draw points, lines, or polygons on the map using the toolbar on the left.")

# Setup layout: Map on left, GeoJSON inspector & form on right
col1, col2 = st.columns([3, 2])

with col1:
    # Initialize Folium Map centered on Wellington using reliable OpenStreetMap tiles
    m = folium.Map(
        location=[-41.2865, 174.7762], 
        zoom_start=13, 
        tiles="OpenStreetMap"
    )

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
    st.subheader("📌 Feature Attributes")

    # Safely extract drawings from map output state
    all_drawings = output.get("all_drawings") if output and isinstance(output, dict) else None

    if all_drawings and len(all_drawings) > 0:
        st.success(f"Captured {len(all_drawings)} feature(s)!")

        # Create input fields for each drawn feature to assign a Name attribute
        named_features = []
        
        st.write("### Assign Feature Names")
        with st.form("attribute_form"):
            for idx, feature in enumerate(all_drawings):
                geom_type = feature.get("geometry", {}).get("type", "Feature")
                
                # Retrieve existing name if available in session_state, else default to "Site #X"
                default_name = f"{geom_type} #{idx + 1}"
                feature_name = st.text_input(
                    label=f"Name for {geom_type} #{idx + 1}:",
                    value=default_name,
                    key=f"feature_name_{idx}"
                )
                
                # Make a shallow copy and set the 'name' attribute in GeoJSON properties
                feature_copy = dict(feature)
                if "properties" not in feature_copy or feature_copy["properties"] is None:
                    feature_copy["properties"] = {}
                
                feature_copy["properties"]["name"] = feature_name
                named_features.append(feature_copy)

            # Submit button to apply names to dataset
            submit_attributes = st.form_submit_button("Update Attributes")

        # Convert attributed drawings into a GeoDataFrame
        try:
            geojson_data = {
                "type": "FeatureCollection",
                "features": named_features
            }
            gdf = gpd.GeoDataFrame.from_features(geojson_data, crs="EPSG:4326")
            
            # Display summary table with the new 'name' column alongside geometry
            st.write("### Feature Summary Table")
            if "name" in gdf.columns:
                st.dataframe(gdf[["name", "geometry"]], use_container_width=True)
            else:
                st.dataframe(gdf[["geometry"]], use_container_width=True)

            # Download button for spatial file with embedded names
            geojson_str = json.dumps(geojson_data, indent=2)
            st.download_button(
                label="📥 Download GeoJSON with Attributes",
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
        st.info("Use the drawing tools on the map to place markers or draw shapes. Attribute forms will display here automatically.")
