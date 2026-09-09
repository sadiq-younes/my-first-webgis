import json
import folium
from folium.plugins import Draw
import geopandas as gpd
import streamlit as st
from streamlit_folium import st_folium
from sqlalchemy import text

st.set_page_config(page_title="WebGIS PostGIS Integration", layout="wide")
st.title("🗺️ WebGIS with PostGIS Database Persistence")

# 1. Establish SQL Connection via Streamlit Secrets
db_conn = st.connection("postgresql", type="sql")

# 2. Ensure Table Exists with PostGIS Geometry Support
with db_conn.session as session:
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS spatial_features (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            geom GEOMETRY(Geometry, 4326),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """))
    session.commit()

# 3. Read Existing Features from PostGIS
def load_saved_features():
    query = "SELECT id, name, ST_AsGeoJSON(geom) as geojson FROM spatial_features;"
    return db_conn.query(query, ttl=0)

saved_data = load_saved_features()

col1, col2 = st.columns([3, 2])

with col1:
    m = folium.Map(location=[-41.2865, 174.7762], zoom_start=13, tiles="OpenStreetMap")

    # Render saved features from PostGIS onto the map
    if not saved_data.empty:
        for _, row in saved_data.iterrows():
            try:
                geom = json.loads(row["geojson"])
                label = row["name"] if row["name"] else f"Feature #{row['id']}"
                folium.GeoJson(geom, tooltip=label).add_to(m)
            except Exception:
                pass

    # Add Drawing toolbar
    draw_control = Draw(
        export=True,
        position="topleft",
        draw_options={
            "polyline": True, 
            "polygon": True, 
            "marker": True, 
            "rectangle": True, 
            "circle": False, 
            "circlemarker": False
        },
        edit_options={"edit": True, "remove": True}
    )
    draw_control.add_to(m)
    
    output = st_folium(m, width="100%", height=550)

with col2:
    st.subheader("📌 Feature Attributes & PostGIS Save")

    all_drawings = output.get("all_drawings") if output and isinstance(output, dict) else None

    if all_drawings and len(all_drawings) > 0:
        st.success(f"Captured {len(all_drawings)} shape(s) in active session")

        # Form to assign names and trigger SQL insert
        with st.form("postgis_save_form"):
            st.write("### Assign Feature Names")
            
            drawing_payloads = []
            for idx, feature in enumerate(all_drawings):
                geom_type = feature.get("geometry", {}).get("type", "Feature")
                
                feat_name = st.text_input(
                    label=f"Name for {geom_type} #{idx + 1}:",
                    value=f"Site {geom_type} #{idx + 1}",
                    key=f"db_name_{idx}"
                )
                
                geom_json_str = json.dumps(feature["geometry"])
                drawing_payloads.append((feat_name, geom_json_str))

            save_submitted = st.form_submit_button("💾 Save to PostGIS Database", type="primary")

        if save_submitted:
            with db_conn.session as session:
                for name, geojson_str in drawing_payloads:
                    # SQL INSERT converting GeoJSON directly into native PostGIS geometry
                    sql_query = text("""
                        INSERT INTO spatial_features (name, geom)
                        VALUES (:name, ST_GeomFromGeoJSON(:geom));
                    """)
                    session.execute(sql_query, {"name": name, "geom": geojson_str})
                
                session.commit()
            
            st.success("Successfully written to PostGIS database!")
            st.rerun()

    # Display database content summary
    st.write("### Records Currently in PostGIS")
    if not saved_data.empty:
        st.dataframe(saved_data[["id", "name"]], use_container_width=True)
    else:
        st.info("No spatial records saved in database yet.")
