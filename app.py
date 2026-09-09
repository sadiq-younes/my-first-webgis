import json
import folium
from folium.plugins import Draw
from folium.plugins import Draw, LocateControl
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
from sqlalchemy import text

st.set_page_config(page_title="PPGIS Place Assessment", layout="wide")
st.title("🗳️ PPGIS: Public Space Assessment & Rating Tool")
st.set_page_config(
    page_title="PPGIS Mobile Field Assessment", 
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.title("📱 PPGIS Field Assessment Tool")

# 1. Establish SQL Connection via Streamlit Secrets
# 1. Database Connection
db_conn = st.connection("postgresql", type="sql", connect_args={"sslmode": "require"})

# 2. Ensure Table Exists with PostGIS Geometry, Rank, and Comment Support
# 2. Database Schema Setup
with db_conn.session as session:
    # Auto-migrate table if upgrading from basic spatial_features
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS spatial_features (
            id SERIAL PRIMARY KEY,
@@ -27,27 +30,44 @@
    """))
    session.commit()

# 3. Read Existing PPGIS Features from PostGIS
# 3. Read Existing PPGIS Features
def load_saved_features():
    query = "SELECT id, name, rank, comment, ST_AsGeoJSON(geom) as geojson FROM spatial_features ORDER BY id ASC;"
    query = """
        SELECT id, name, rank, comment, created_at, ST_AsGeoJSON(geom) as geojson 
        FROM spatial_features 
        ORDER BY id ASC;
    """
    return db_conn.query(query, ttl=0)

saved_data = load_saved_features()

# Quality ranking color mapping
# Color Palette for Quality Ratings
RANK_COLORS = {
    "Excellent": "#2ecc71",  # Green
    "Good": "#3498db",       # Blue
    "Moderate": "#f1c40f",   # Yellow
    "Poor": "#e74c3c"        # Red
}

col1, col2 = st.columns([8, 2])
# Responsive Column Layout: Stacks naturally on mobile screens
col1, col2 = st.columns([7, 5])

with col1:
    m = folium.Map(location=[-41.2865, 174.7762], zoom_start=13, tiles="OpenStreetMap")
    st.subheader("1. Locate & Mark on Map")
    
    # Initialize Map (Default centered on Wellington, NZ)
    m = folium.Map(location=[-41.2865, 174.7762], zoom_start=14, tiles="OpenStreetMap")

    # Add GPS Location Button (Crucial for Mobile Fieldwork)
    LocateControl(
        auto_start=False,
        flyTo=True,
        keepCurrentZoomLevel=False,
        position="topleft",
        strings={"title": "Find My Location"}
    ).add_to(m)

    # Render saved PPGIS features onto map with rank-based styling and popups
    # Render saved PPGIS features
    if not saved_data.empty:
        for _, row in saved_data.iterrows():
            try:
@@ -56,184 +76,199 @@ def load_saved_features():
                color = RANK_COLORS.get(rank, "#95a5a6")

                popup_html = f"""
                <div style="font-family: sans-serif; min-width: 160px;">
                <div style="font-family: sans-serif; min-width: 150px;">
                    <h4 style="margin: 0 0 5px 0;">{row['name']}</h4>
                    <b>Rank:</b> <span style="color:{color}; font-weight:bold;">{rank}</span><br>
                    <b>Comment:</b> <i>{row['comment'] if row['comment'] else 'No comment provided.'}</i>
                    <b>Rating:</b> <span style="color:{color};">{rank}</span><br>
                    <b>Note:</b> {row['comment'] if row['comment'] else 'None'}
                </div>
                """

                folium.GeoJson(
                    geom,
                    style_function=lambda x, c=color: {
                        "fillColor": c, 
                        "color": c, 
                        "weight": 3, 
                        "fillOpacity": 0.5
                        "fillColor": c, "color": c, "weight": 3, "fillOpacity": 0.5
                    },
                    marker=folium.CircleMarker(
                        radius=7, 
                        fill_color=color, 
                        color="#000", 
                        weight=1, 
                        fill_opacity=0.8
                        radius=8, fill_color=color, color="#000", weight=1, fill_opacity=0.85
                    ),
                    tooltip=f"{row['name']} ({rank})",
                    popup=folium.Popup(popup_html, max_width=250)
                    popup=folium.Popup(popup_html, max_width=220)
                ).add_to(m)
            except Exception:
                pass

    # Add Drawing toolbar
    # Drawing Toolbar Optimized for Touch
    draw_control = Draw(
        export=True,
        export=False,
        position="topleft",
        draw_options={
            "polyline": True, 
            "polygon": True, 
            "marker": True, 
            "rectangle": True, 
            "circle": False, 
            "marker": True,
            "polyline": True,
            "polygon": True,
            "rectangle": True,
            "circle": False,
            "circlemarker": False
        },
        edit_options={"edit": True, "remove": True}
    )
    draw_control.add_to(m)

    output = st_folium(m, width="100%", height=600)
    # Set map height suitable for mobile screens
    output = st_folium(m, width="100%", height=450)

with col2:
    tab1, tab2, tab3 = st.tabs(["➕ Add Assessment", "✏️ Edit Record", "🗑️ Delete"])
    st.subheader("2. Enter Attribute Details")
    tab1, tab2, tab3 = st.tabs(["➕ Add New", "✏️ Edit", "🗑️ Delete"])

    # ------------------ TAB 1: ADD NEW PPGIS FEATURE ------------------
    # ------------------ TAB 1: ADD FEATURE ------------------
    with tab1:
        st.subheader("Submit Location Assessment")
        all_drawings = output.get("all_drawings") if output and isinstance(output, dict) else None

        if all_drawings and len(all_drawings) > 0:
            st.success(f"Captured {len(all_drawings)} active location drawing(s)")
            st.success(f"📍 {len(all_drawings)} active shape/marker(s) drawn")

            with st.form("postgis_save_form"):
            with st.form("mobile_save_form"):
                drawing_payloads = []
                for idx, feature in enumerate(all_drawings):
                    geom_type = feature.get("geometry", {}).get("type", "Feature")
                    st.markdown(f"**Location #{idx + 1} ({geom_type})**")
                    st.markdown(f"**Item #{idx + 1} ({geom_type})**")

                    feat_name = st.text_input(
                        label="Place Name / Label:",
                        value=f"Site {geom_type} #{idx + 1}",
                        key=f"db_name_{idx}"
                        "Place Name / Label:",
                        value=f"Site #{idx + 1}",
                        key=f"mb_name_{idx}"
                    )

                    feat_rank = st.selectbox(
                        label="Rate Quality:",
                        "Rate Quality:",
                        options=["Excellent", "Good", "Moderate", "Poor"],
                        index=1,
                        key=f"db_rank_{idx}"
                        key=f"mb_rank_{idx}"
                    )

                    feat_comment = st.text_area(
                        label="Observations / Comments:",
                        placeholder="Enter notes about access, safety, amenities, etc...",
                        key=f"db_comment_{idx}"
                        "Observations / Notes:",
                        placeholder="Safety, seating, access, lighting...",
                        key=f"mb_comment_{idx}"
                    )

                    geom_json_str = json.dumps(feature["geometry"])
                    drawing_payloads.append((feat_name, feat_rank, feat_comment, geom_json_str))
                    st.divider()

                save_submitted = st.form_submit_button("💾 Submit PPGIS Record", type="primary")
                submit_btn = st.form_submit_button("💾 Save Observation", type="primary", use_container_width=True)

            if save_submitted:
            if submit_btn:
                with db_conn.session as session:
                    for name, rank, comment, geojson_str in drawing_payloads:
                        sql_query = text("""
                            INSERT INTO spatial_features (name, rank, comment, geom)
                            VALUES (:name, :rank, :comment, ST_GeomFromGeoJSON(:geom));
                        """)
                        session.execute(sql_query, {
                            "name": name, 
                            "rank": rank, 
                            "comment": comment, 
                            "geom": geojson_str
                            "name": name, "rank": rank, "comment": comment, "geom": geojson_str
                        })
                    session.commit()
                
                st.success("Successfully written to PostGIS database!")
                st.success("Successfully saved to PostGIS!")
                st.rerun()
        else:
            st.info("Draw shapes or place markers on the map to add your assessment.")
            st.info("👆 Tap the marker or polygon icon on the map above to drop a point or draw an area.")

    # ------------------ TAB 2: EDIT EXISTING RECORD ------------------
    # ------------------ TAB 2: EDIT ------------------
    with tab2:
        st.subheader("Edit Assessment Details")
        if not saved_data.empty:
            feature_options = {f"ID #{row['id']} - {row['name']}": row['id'] for _, row in saved_data.iterrows()}
            selected_option = st.selectbox("Select Feature to Edit:", list(feature_options.keys()))
            selected_option = st.selectbox("Select Record:", list(feature_options.keys()))
            selected_id = feature_options[selected_option]

            # Fetch current row values
            current_row = saved_data[saved_data["id"] == selected_id].iloc[0]
            current_name = current_row["name"] or ""
            current_rank = current_row["rank"] if current_row["rank"] in RANK_COLORS else "Good"
            current_comment = current_row["comment"] or ""

            with st.form("edit_form"):
                updated_name = st.text_input("New Name:", value=current_name)
                
            with st.form("mobile_edit_form"):
                updated_name = st.text_input("Name:", value=current_name)
                rank_opts = ["Excellent", "Good", "Moderate", "Poor"]
                rank_idx = rank_opts.index(current_rank) if current_rank in rank_opts else 1
                updated_rank = st.selectbox("New Rank:", options=rank_opts, index=rank_idx)
                
                updated_comment = st.text_area("New Comment:", value=current_comment)
                updated_rank = st.selectbox("Rank:", options=rank_opts, index=rank_idx)
                updated_comment = st.text_area("Comment:", value=current_comment)

                edit_submitted = st.form_submit_button("✏️ Update Record", type="primary")
                edit_btn = st.form_submit_button("✏️ Update Record", type="primary", use_container_width=True)

            if edit_submitted:
            if edit_btn:
                with db_conn.session as session:
                    sql_query = text("""
                        UPDATE spatial_features
                        SET name = :name, rank = :rank, comment = :comment
                        WHERE id = :id;
                    """)
                    session.execute(sql_query, {
                        "name": updated_name, 
                        "rank": updated_rank, 
                        "comment": updated_comment, 
                        "id": selected_id
                        "name": updated_name, "rank": updated_rank, "comment": updated_comment, "id": selected_id
                    })
                    session.commit()
                st.success(f"Updated ID #{selected_id} successfully!")
                st.success("Record updated!")
                st.rerun()
        else:
            st.info("No spatial records available to edit.")
            st.info("No records available.")

    # ------------------ TAB 3: DELETE RECORD ------------------
    # ------------------ TAB 3: DELETE ------------------
    with tab3:
        st.subheader("Delete Feature")
        if not saved_data.empty:
            feature_options_del = {f"ID #{row['id']} - {row['name']}": row['id'] for _, row in saved_data.iterrows()}
            selected_del_option = st.selectbox("Select Feature to Delete:", list(feature_options_del.keys()))
            selected_del_option = st.selectbox("Select Record to Delete:", list(feature_options_del.keys()))
            selected_del_id = feature_options_del[selected_del_option]

            with st.form("delete_form"):
                st.warning(f"Are you sure you want to delete ID #{selected_del_id}?")
                delete_submitted = st.form_submit_button("🗑️ Permanent Delete", type="primary")
            with st.form("mobile_delete_form"):
                st.warning(f"Delete ID #{selected_del_id}?")
                del_btn = st.form_submit_button("🗑️ Delete", type="primary", use_container_width=True)

            if delete_submitted:
            if del_btn:
                with db_conn.session as session:
                    sql_query = text("DELETE FROM spatial_features WHERE id = :id;")
                    session.execute(sql_query, {"id": selected_del_id})
                    session.execute(text("DELETE FROM spatial_features WHERE id = :id;"), {"id": selected_del_id})
                    session.commit()
                st.success(f"Deleted feature ID #{selected_del_id} from PostGIS!")
                st.success("Deleted!")
                st.rerun()
        else:
            st.info("No spatial records available to delete.")
            st.info("No records available.")

    # Display database content summary table
    st.write("---")
    st.write("### Submitted PPGIS Records")
    if not saved_data.empty:
        st.dataframe(saved_data[["id", "name", "rank", "comment"]], use_container_width=True)
    else:
        st.info("No records saved in PostGIS yet.")
# ---------------- CSV EXPORT ----------------
st.write("---")
st.subheader("📥 Export Observations")

if not saved_data.empty:
    export_list = []
    for _, row in saved_data.iterrows():
        lon, lat = None, None
        if row.get("geojson"):
            try:
                g = json.loads(row["geojson"])
                if g.get("type") == "Point":
                    lon, lat = g["coordinates"][0], g["coordinates"][1]
            except Exception:
                pass

        export_list.append({
            "id": row["id"],
            "name": row["name"],
            "rank": row["rank"],
            "comment": row["comment"],
            "latitude": lat,
            "longitude": lon,
            "created_at": row["created_at"]
        })

    export_df = pd.DataFrame(export_list)
    
    csv_bytes = export_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📄 Download Data as CSV",
        data=csv_bytes,
        file_name="ppgis_field_data.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    with st.expander("View Submitted Data Table"):
        st.dataframe(export_df[["id", "name", "rank", "comment"]], use_container_width=True)
else:
    st.info("No observations recorded yet.")
