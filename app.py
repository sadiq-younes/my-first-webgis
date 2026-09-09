import json
import folium
from folium.plugins import Draw
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
from sqlalchemy import text

st.set_page_config(page_title="WebGIS PostGIS Integration", layout="wide")
st.title("🗺️ WebGIS with PostGIS Database Persistence")

# 1. Establish SQL Connection via Streamlit Secrets
db_conn = st.connection("postgresql", type="sql", connect_args={"sslmode": "require"})

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
    query = "SELECT id, name, ST_AsGeoJSON(geom) as geojson FROM spatial_features ORDER BY id ASC;"
    return db_conn.query(query, ttl=0)

saved_data = load_saved_features()

col1, col2 = st.columns([7, 3])

with col1:
    m = folium.Map(location=[-41.2865, 174.7762], zoom_start=13, tiles="OpenStreetMap")

    # Render saved features from PostGIS onto the map
    if not saved_data.empty:
        for _, row in saved_data.iterrows():
            try:
                geom = json.loads(row["geojson"])
                label = f"ID #{row['id']}: {row['name']}" if row['name'] else f"Feature #{row['id']}"
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
    tab1, tab2, tab3 = st.tabs(["➕ Add New", "✏️ Edit Name", "🗑️ Delete"])

    # ------------------ TAB 1: ADD NEW FEATURES ------------------
    with tab1:
        st.subheader("Save Active Session Drawings")
        all_drawings = output.get("all_drawings") if output and isinstance(output, dict) else None

        if all_drawings and len(all_drawings) > 0:
            st.success(f"Captured {len(all_drawings)} shape(s) in active session")

            with st.form("postgis_save_form"):
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

                save_submitted = st.form_submit_button("💾 Save to PostGIS", type="primary")

            if save_submitted:
                with db_conn.session as session:
                    for name, geojson_str in drawing_payloads:
                        sql_query = text("""
                            INSERT INTO spatial_features (name, geom)
                            VALUES (:name, ST_GeomFromGeoJSON(:geom));
                        """)
                        session.execute(sql_query, {"name": name, "geom": geojson_str})
                    session.commit()
                
                st.success("Successfully written to PostGIS database!")
                st.rerun()
        else:
            st.info("Draw shapes on the map to save new records.")

    # ------------------ TAB 2: EDIT EXISTING FEATURES ------------------
    with tab2:
        st.subheader("Edit Feature Name")
        if not saved_data.empty:
            feature_options = {f"ID #{row['id']} - {row['name']}": row['id'] for _, row in saved_data.iterrows()}
            selected_option = st.selectbox("Select Feature to Edit:", list(feature_options.keys()))
            selected_id = feature_options[selected_option]

            # Get current name
            current_name = saved_data[saved_data["id"] == selected_id]["name"].values[0]
            
            with st.form("edit_form"):
                updated_name = st.text_input("New Name:", value=current_name)
                edit_submitted = st.form_submit_button("✏️ Update Record", type="primary")

            if edit_submitted:
                with db_conn.session as session:
                    sql_query = text("""
                        UPDATE spatial_features
                        SET name = :name
                        WHERE id = :id;
                    """)
                    session.execute(sql_query, {"name": updated_name, "id": selected_id})
                    session.commit()
                st.success(f"Updated ID #{selected_id} successfully!")
                st.rerun()
        else:
            st.info("No spatial records available to edit.")

    # ------------------ TAB 3: DELETE FEATURES ------------------
    with tab3:
        st.subheader("Delete Feature")
        if not saved_data.empty:
            feature_options_del = {f"ID #{row['id']} - {row['name']}": row['id'] for _, row in saved_data.iterrows()}
            selected_del_option = st.selectbox("Select Feature to Delete:", list(feature_options_del.keys()))
            selected_del_id = feature_options_del[selected_del_option]

            with st.form("delete_form"):
                st.warning(f"Are you sure you want to delete ID #{selected_del_id}?")
                delete_submitted = st.form_submit_button("🗑️ Permanent Delete", type="primary")

            if delete_submitted:
                with db_conn.session as session:
                    sql_query = text("DELETE FROM spatial_features WHERE id = :id;")
                    session.execute(sql_query, {"id": selected_del_id})
                    session.commit()
                st.success(f"Deleted feature ID #{selected_del_id} from PostGIS!")
                st.rerun()
        else:
            st.info("No spatial records available to delete.")

    # Display database content summary table below tabs
    st.write("---")
    st.write("### Current PostGIS Records")
    if not saved_data.empty:
        st.dataframe(saved_data[["id", "name"]], use_container_width=True)
