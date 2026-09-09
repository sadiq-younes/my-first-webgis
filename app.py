import json
import folium
from folium.plugins import Draw
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
from sqlalchemy import text

st.set_page_config(page_title="PPGIS Place Assessment", layout="wide")
st.title("🗳️ PPGIS: Public Space Assessment & Rating Tool")

# 1. Establish SQL Connection
db_conn = st.connection("postgresql", type="sql", connect_args={"sslmode": "require"})

# 2. Migration/Creation: Ensure table includes rank & comment columns
with db_conn.session as session:
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS ppgis_features (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            rank VARCHAR(50),
            comment TEXT,
            geom GEOMETRY(Geometry, 4326),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """))
    session.commit()

# 3. Read Existing PPGIS Features
def load_ppgis_features():
    query = "SELECT id, name, rank, comment, ST_AsGeoJSON(geom) as geojson FROM ppgis_features ORDER BY id ASC;"
    return db_conn.query(query, ttl=0)

saved_data = load_ppgis_features()

# Color mapping helper based on quality ranking
RANK_COLORS = {
    "Excellent": "#2ecc71",  # Green
    "Good": "#3498db",       # Blue
    "Moderate": "#f1c40f",   # Yellow
    "Poor": "#e74c3c"        # Red
}

col1, col2 = st.columns([7, 3])

with col1:
    m = folium.Map(location=[-41.2865, 174.7762], zoom_start=13, tiles="OpenStreetMap")

    # Render saved PPGIS features with color coding and rich popups
    if not saved_data.empty:
        for _, row in saved_data.iterrows():
            try:
                geom = json.loads(row["geojson"])
                rank = row["rank"] if row["rank"] else "Moderate"
                color = RANK_COLORS.get(rank, "#95a5a6")
                
                popup_content = f"""
                <div style="font-family: sans-serif; width: 180px;">
                    <b>{row['name']}</b><br>
                    <b>Rank:</b> <span style="color:{color}; font-weight:bold;">{rank}</span><br>
                    <b>Comment:</b> <i>{row['comment'] or 'No comments provided.'}</i>
                </div>
                """
                
                folium.GeoJson(
                    geom,
                    style_function=lambda x, col=color: {"fillColor": col, "color": col, "weight": 3, "fillOpacity": 0.5},
                    marker=folium.CircleMarker(radius=7, fill_color=color, color="#000", weight=1, fill_opacity=0.8),
                    tooltip=f"{row['name']} ({rank})",
                    popup=folium.Popup(popup_content, max_width=220)
                ).add_to(m)
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
    
    output = st_folium(m, width="100%", height=600)

with col2:
    tab1, tab2, tab3 = st.tabs(["➕ Add Feedback", "✏️ Edit Record", "🗑️ Delete"])

    # ------------------ TAB 1: ADD NEW PPGIS RECORD ------------------
    with tab1:
        st.subheader("Submit Location Feedback")
        all_drawings = output.get("all_drawings") if output and isinstance(output, dict) else None

        if all_drawings and len(all_drawings) > 0:
            st.success(f"Captured {len(all_drawings)} active location drawing(s)")

            with st.form("ppgis_save_form"):
                drawing_payloads = []
                for idx, feature in enumerate(all_drawings):
                    geom_type = feature.get("geometry", {}).get("type", "Feature")
                    st.markdown(f"**Location #{idx + 1} ({geom_type})**")
                    
                    feat_name = st.text_input("Place Name / Identifier:", value=f"Site #{idx + 1}", key=f"name_{idx}")
                    feat_rank = st.selectbox(
                        "Rate Quality:", 
                        ["Excellent", "Good", "Moderate", "Poor"], 
                        index=1, 
                        key=f"rank_{idx}"
                    )
                    feat_comment = st.text_area("Observations / Comments:", key=f"comment_{idx}")
                    
                    geom_json_str = json.dumps(feature["geometry"])
                    drawing_payloads.append((feat_name, feat_rank, feat_comment, geom_json_str))
                    st.divider()

                save_submitted = st.form_submit_button("💾 Submit PPGIS Assessment", type="primary")

            if save_submitted:
                with db_conn.session as session:
                    for name, rank, comment, geojson_str in drawing_payloads:
                        sql_query = text("""
                            INSERT INTO ppgis_features (name, rank, comment, geom)
                            VALUES (:name, :rank, :comment, ST_GeomFromGeoJSON(:geom));
                        """)
                        session.execute(sql_query, {"name": name, "rank": rank, "comment": comment, "geom": geojson_str})
                    session.commit()
                
                st.success("Feedback successfully saved to PostGIS!")
                st.rerun()
        else:
            st.info("Draw a marker, polyline, or area on the map to add your assessment.")

    # ------------------ TAB 2: EDIT EXISTING RECORD ------------------
    with tab2:
        st.subheader("Edit Assessment")
        if not saved_data.empty:
            feature_options = {f"ID #{row['id']} - {row['name']}": row['id'] for _, row in saved_data.iterrows()}
            selected_option = st.selectbox("Select Feature to Edit:", list(feature_options.keys()))
            selected_id = feature_options[selected_option]

            record = saved_data[saved_data["id"] == selected_id].iloc[0]
            
            with st.form("edit_ppgis_form"):
                updated_name = st.text_input("Name:", value=record["name"])
                ranks = ["Excellent", "Good", "Moderate", "Poor"]
                current_rank_idx = ranks.index(record["rank"]) if record["rank"] in ranks else 1
                updated_rank = st.selectbox("Rank:", ranks, index=current_rank_idx)
                updated_comment = st.text_area("Comment:", value=record["comment"] or "")
                
                edit_submitted = st.form_submit_button("✏️ Update Assessment", type="primary")

            if edit_submitted:
                with db_conn.session as session:
                    sql_query = text("""
                        UPDATE ppgis_features
                        SET name = :name, rank = :rank, comment = :comment
                        WHERE id = :id;
                    """)
                    session.execute(sql_query, {
                        "name": updated_name, 
                        "rank": updated_rank, 
                        "comment": updated_comment, 
                        "id": selected_id
                    })
                    session.commit()
                st.success(f"Record #{selected_id} updated!")
                st.rerun()
        else:
            st.info("No assessments available to edit.")

    # ------------------ TAB 3: DELETE RECORD ------------------
    with tab3:
        st.subheader("Remove Feedback")
        if not saved_data.empty:
            feature_options_del = {f"ID #{row['id']} - {row['name']}": row['id'] for _, row in saved_data.iterrows()}
            selected_del_option = st.selectbox("Select Record to Remove:", list(feature_options_del.keys()))
            selected_del_id = feature_options_del[selected_del_option]

            with st.form("delete_ppgis_form"):
                st.warning(f"Delete assessment ID #{selected_del_id} permanently?")
                delete_submitted = st.form_submit_button("🗑️ Confirm Delete", type="primary")

            if delete_submitted:
                with db_conn.session as session:
                    sql_query = text("DELETE FROM ppgis_features WHERE id = :id;")
                    session.execute(sql_query, {"id": selected_del_id})
                    session.commit()
                st.success(f"Assessment #{selected_del_id} removed!")
                st.rerun()
        else:
            st.info("No records available to delete.")

    # Summary Data View
    st.write("---")
    st.write("### Submitted PPGIS Feedback")
    if not saved_data.empty:
        st.dataframe(saved_data[["id", "name", "rank", "comment"]], use_container_width=True)
