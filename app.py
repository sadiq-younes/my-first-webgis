import json
import folium
from folium.plugins import Draw, LocateControl
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
from sqlalchemy import text

st.set_page_config(page_title="PPGIS Assessment", layout="wide", initial_sidebar_state="expanded")

# Define Credentials (or load from st.secrets in production)
ADMIN_PASSCODE = "admin123"
FIELD_USER_PASSCODE = "field2026"  # Passcode required for field submissions

# ------------------ SIDEBAR: ACCESS CONTROL ------------------
st.sidebar.title("🔐 Access Control")

user_role = st.sidebar.radio("Select Portal Mode:", ["Field Collector", "Administrator"])

is_authenticated_user = False
is_admin = False

if user_role == "Field Collector":
    user_code = st.sidebar.text_input("Enter Field Access Code:", type="password")
    if user_code == FIELD_USER_PASSCODE or user_code == ADMIN_PASSCODE:
        is_authenticated_user = True
        st.sidebar.success("✅ Field Access Granted")
    elif user_code:
        st.sidebar.error("❌ Invalid Access Code")

elif user_role == "Administrator":
    admin_input = st.sidebar.text_input("Enter Admin Passcode:", type="password")
    if admin_input == ADMIN_PASSCODE:
        is_admin = True
        is_authenticated_user = True
        st.sidebar.success("🔓 Full Admin Access Granted")
    elif admin_input:
        st.sidebar.error("❌ Incorrect Admin Passcode")

st.title("📱 PPGIS Field Assessment Tool")

# 1. Database Connection
db_conn = st.connection("postgresql", type="sql", connect_args={"sslmode": "require"})

# 2. Schema Setup
with db_conn.session as session:
    session.execute(text("""
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
    session.commit()

# 3. Read Data
def load_saved_features():
    query = """
        SELECT id, name, rank, comment, submitted_by, created_at, ST_AsGeoJSON(geom) as geojson 
        FROM spatial_features 
        ORDER BY id ASC;
    """
    return db_conn.query(query, ttl=0)

saved_data = load_saved_features()

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
            "marker": is_authenticated_user,
            "polyline": is_authenticated_user,
            "polygon": is_authenticated_user,
            "rectangle": is_authenticated_user,
            "circle": False,
            "circlemarker": False
        },
        edit_options={"edit": is_admin, "remove": is_admin}
    )
    draw_control.add_to(m)
    
    output = st_folium(m, width="100%", height=450)

# ------------------ DATA ENTRY & MANAGEMENT ------------------
with col2:
    st.subheader("2. Data Entry & Actions")
    
    if not is_authenticated_user:
        st.warning("🔑 Please enter a valid Access Code in the sidebar to add observations or access administrative tools.")
    else:
        if is_admin:
            tab1, tab2, tab3 = st.tabs(["➕ Add New", "✏️ Edit (Admin)", "🗑️ Delete (Admin)"])
        else:
            tab1, = st.tabs(["➕ Add New"])
            st.caption("🔒 *Edit and Delete features are restricted to Administrators.*")

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
                        with db_conn.session as session:
                            for name, rank, comment, geojson_str in drawing_payloads:
                                sql_query = text("""
                                    INSERT INTO spatial_features (name, rank, comment, submitted_by, geom)
                                    VALUES (:name, :rank, :comment, :user, ST_GeomFromGeoJSON(:geom));
                                """)
                                session.execute(sql_query, {
                                    "name": name, "rank": rank, "comment": comment, "user": collector_name, "geom": geojson_str
                                })
                            session.commit()
                        st.success("Saved to PostGIS!")
                        st.rerun()
            else:
                st.info("👆 Tap the marker or drawing tool on the map to place an observation.")

        # ------------------ ADMIN TABS ------------------
        if is_admin:
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
                            with db_conn.session as session:
                                session.execute(text("""
                                    UPDATE spatial_features 
                                    SET name = :n, rank = :r, comment = :c 
                                    WHERE id = :id;
                                """), {"n": u_name, "r": u_rank, "c": u_comment, "id": sel_id})
                                session.commit()
                            st.success("Record updated!")
                            st.rerun()

            with tab3:
                if not saved_data.empty:
                    opts_del = {f"ID #{row['id']} - {row['name']}": row['id'] for _, row in saved_data.iterrows()}
                    del_id = opts_del[st.selectbox("Select Record to Delete:", list(opts_del.keys()))]

                    with st.form("del_form"):
                        st.warning(f"Delete ID #{del_id}?")
                        if st.form_submit_button("🗑️ Permanent Delete", type="primary", use_container_width=True):
                            with db_conn.session as session:
                                session.execute(text("DELETE FROM spatial_features WHERE id = :id;"), {"id": del_id})
                                session.commit()
                            st.success("Deleted!")
                            st.rerun()

# ---------------- EXPORT & TABLE VIEW ----------------
st.write("---")
if not saved_data.empty:
    st.dataframe(saved_data[["id", "name", "rank", "comment", "submitted_by", "created_at"]], use_container_width=True)
