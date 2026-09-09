import json
import folium
from folium.plugins import Draw, LocateControl
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
from sqlalchemy import create_engine, text

st.set_page_config(page_title="PPGIS Assessment", layout="wide", initial_sidebar_state="expanded")

# ------------------ DATABASE CONNECTION ------------------
# Insert your Supabase database password below:
DB_PASSWORD = "YOUR_ACTUAL_PASSWORD"
DATABASE_URL = f"postgresql://postgres.qiehlzcixqhmcxgbinlu:{DB_PASSWORD}@db.qiehlzcixqhmcxgbinlu.supabase.co:5432/postgres?sslmode=require"

@st.cache_resource
def get_db_engine():
    return create_engine(DATABASE_URL)

try:
    engine = get_db_engine()
except Exception as e:
    st.error(f"Failed to connect to PostGIS: {e}")

st.title("📱 PPGIS Field Assessment Tool")

# 1. Schema Setup
with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS spatial_features (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            geom GEOMETRY(Geometry, 4326),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            rank VARCHAR(50),
            comment TEXT,
            submitted_by VARCHAR(100) DEFAULT 'Anonymous'
        );
    """))

# 2. Read Data
def load_saved_features():
    query = """
        SELECT id, name, rank, comment, submitted_by, created_at, ST_AsGeoJSON(geom) as geojson 
        FROM spatial_features 
        ORDER BY id ASC;
    """
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn)

try:
    saved_data = load_saved_features()
except Exception:
    saved_data = pd.DataFrame()

RANK_COLORS = {
    "Excellent": "#2ecc71",
    "Good": "#3498db",
    "Moderate": "#f1c40f",
    "Poor": "#e74c3c"
}

col1, col2 = st.columns([7, 5])

# ------------------ MAP RENDERING ------------------
with col1:
    st.subheader("1. Locate & Mark on Map")
    m = folium.Map(location=[-41.2865, 174.7762], zoom_start=14, tiles="OpenStreetMap")

    LocateControl(auto_start=False, flyTo=True, position="topleft").add_to(m)

    if not saved_data.empty:
        for _, row in saved_data.iterrows():
            try:
                geom = json.loads(row["geojson"])
                rank = row["rank"] if row["rank"] in RANK_COLORS else "Moderate"
                color = RANK_COLORS.get(rank, "#95a5a6")
                
                popup_html = f"""
                <div style="font-family: sans-serif; min-width: 150px;">
                    <h4 style="margin:0 0 5px 0;">{row['name']}</h4>
                    <b>Rating:</b> <span style="color:{color};">{rank}</span><br>
                    <b>Note:</b> {row['comment'] or 'None'}<br>
                    <small><b>By:</b> {row.get('submitted_by', 'Anonymous')}</small>
                </div>
                """
                
                folium.GeoJson(
                    geom,
                    style_function=lambda x, c=color: {"fillColor": c, "color": c, "weight": 3, "fillOpacity": 0.5},
                    marker=folium.CircleMarker(radius=8, fill_color=color, color="#000", weight=1, fill_opacity=0.85),
                    tooltip=f"{row['name']} ({rank})",
                    popup=folium.Popup(popup_html, max_width=220)
                ).add_to(m)
            except Exception:
                pass

    draw_control = Draw(
        position="topleft",
        draw_options={
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
    
    output = st_folium(m, width="100%", height=450)

# ------------------ DATA ENTRY & ACTIONS ------------------
with col2:
    st.subheader("2. Data Entry & Actions")
    
    tab1, tab2, tab3 = st.tabs(["➕ Add New", "✏️ Edit", "🗑️ Delete"])

    # ------------------ TAB 1: ADD FEATURE ------------------
    with tab1:
        all_drawings = output.get("all_drawings") if output and isinstance(output, dict) else None

        if all_drawings and len(all_drawings) > 0:
            st.success(f"📍 {len(all_drawings)} active shape/marker(s) drawn")

            with st.form("add_form"):
                collector_name = st.text_input("Your Name / Collector ID:", value="Field Observer")
                drawing_payloads = []
                
                for idx, feature in enumerate(all_drawings):
                    geom_type = feature.get("geometry", {}).get("type", "Feature")
                    st.markdown(f"**Item #{idx + 1} ({geom_type})**")
                    
                    feat_name = st.text_input("Place Name / Label:", value=f"Site #{idx + 1}", key=f"n_{idx}")
                    feat_rank = st.selectbox("Rating:", ["Excellent", "Good", "Moderate", "Poor"], index=1, key=f"r_{idx}")
                    feat_comment = st.text_area("Observations:", key=f"c_{idx}")
                    
                    geom_json_str = json.dumps(feature["geometry"])
                    drawing_payloads.append((feat_name, feat_rank, feat_comment, geom_json_str))

                if st.form_submit_button("💾 Save Observation", type="primary", use_container_width=True):
                    with engine.begin() as conn:
                        for name, rank, comment, geojson_str in drawing_payloads:
                            sql_query = text("""
                                INSERT INTO spatial_features (name, rank, comment, submitted_by, geom)
                                VALUES (:name, :rank, :comment, :user, ST_GeomFromGeoJSON(:geom));
                            """)
                            conn.execute(sql_query, {
                                "name": name, "rank": rank, "comment": comment, "user": collector_name, "geom": geojson_str
                            })
                    st.success("Saved to PostGIS!")
                    st.rerun()
        else:
            st.info("👆 Tap the marker or drawing tool on the map to place an observation.")

    # ------------------ TAB 2: EDIT FEATURE ------------------
    with tab2:
        if not saved_data.empty:
            opts = {f"ID #{row['id']} - {row['name']}": row['id'] for _, row in saved_data.iterrows()}
            sel_id = opts[st.selectbox("Select Record to Edit:", list(opts.keys()))]
            curr = saved_data[saved_data["id"] == sel_id].iloc[0]

            with st.form("edit_form"):
                u_name = st.text_input("Name:", value=curr["name"] or "")
                u_rank = st.selectbox("Rank:", ["Excellent", "Good", "Moderate", "Poor"], index=1)
                u_comment = st.text_area("Comment:", value=curr["comment"] or "")
                
                if st.form_submit_button("✏️ Update Record", type="primary", use_container_width=True):
                    with engine.begin() as conn:
                        conn.execute(text("""
                            UPDATE spatial_features 
                            SET name = :n, rank = :r, comment = :c 
                            WHERE id = :id;
                        """), {"n": u_name, "r": u_rank, "c": u_comment, "id": sel_id})
                    st.success("Record updated!")
                    st.rerun()
        else:
            st.info("No records available to edit.")

    # ------------------ TAB 3: DELETE FEATURE ------------------
    with tab3:
        if not saved_data.empty:
            opts_del = {f"ID #{row['id']} - {row['name']}": row['id'] for _, row in saved_data.iterrows()}
            del_id = opts_del[st.selectbox("Select Record to Delete:", list(opts_del.keys()))]

            with st.form("del_form"):
                st.warning(f"Delete ID #{del_id}?")
                if st.form_submit_button("🗑️ Permanent Delete", type="primary", use_container_width=True):
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM spatial_features WHERE id = :id;"), {"id": del_id})
                    st.success("Deleted!")
                    st.rerun()
        else:
            st.info("No records available to delete.")

# ---------------- EXPORT & TABLE VIEW ----------------
st.write("---")
if not saved_data.empty:
    st.dataframe(saved_data[["id", "name", "rank", "comment", "submitted_by", "created_at"]], use_container_width=True)
