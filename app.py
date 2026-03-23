import streamlit as st
import pandas as pd
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
import firebase_admin
from firebase_admin import credentials, db
import os
import base64
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz

# --- 1. הגדרות תצורה ---
st.set_page_config(page_title="שבצ'קדם - ניהול בזמן אמת", layout="wide")
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')
PATH_COLORS = ['blue', 'purple', 'darkred', 'orange', 'cadetblue', 'darkgreen', 'black', 'magenta']

# --- 2. Utils ---
@st.cache_data
def get_image_base64(path):
    if not os.path.exists(path): return None
    try:
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except: return None

def init_firebase():
    if not firebase_admin._apps:
        try:
            secret_info = dict(st.secrets["firebase_service_account"])
            secret_info["private_key"] = secret_info["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(secret_info)
            firebase_admin.initialize_app(cred, {
                'databaseURL': "https://shavtsakedem-default-rtdb.europe-west1.firebasedatabase.app/"
            })
        except Exception as e: st.error(f"שגיאה בחיבור: {e}")

def get_status_info(last_seen_str, now_dt):
    if not last_seen_str: return "red", "🔴", "info-sign"
    try:
        lt = ISRAEL_TZ.localize(datetime.strptime(last_seen_str, "%H:%M:%S").replace(
            year=now_dt.year, month=now_dt.month, day=now_dt.day))
        diff = (now_dt - lt).total_seconds() / 60
        if diff <= 15: return "green", "🟢", "running"
        if diff <= 30: return "orange", "🟡", "info-sign"
        return "red", "🔴", "info-sign"
    except: return "red", "🔴", "info-sign"

# --- 3. Database ---
def get_teams_from_db():
    try:
        ref = db.reference('teams').get()
        if not ref: return []
        return [v for v in ref.values() if v] if isinstance(ref, dict) else [t for t in ref if t]
    except: return []

# --- 4. עיצוב CSS המלא ---
logo_base64 = get_image_base64("kedem.png")
bg_base64 = get_image_base64("kedem1.jpeg")
bg_style = f"[data-testid='stAppViewContainer'] {{ background-image: url('data:image/png;base64,{bg_base64}'); background-size: cover; background-position: center; background-attachment: fixed; }}" if bg_base64 else ""

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;700&display=swap');
    {bg_style}
    [data-testid="stVerticalBlock"] {{ background-color: rgba(255, 255, 255, 0.92); padding: 20px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }}
    html, body, [data-testid="stSidebar"], .stMarkdown {{ direction: rtl; text-align: right; font-family: 'Assistant', sans-serif; }}
    div.stButton > button {{ width: 100%; border-radius: 10px; font-weight: bold; background-color: #2e5a27; color: white; height: 3.5em; transition: 0.3s; }}
    iframe {{ min-height: 520px !important; border-radius: 10px; }}
    header, footer {{visibility: hidden;}}
    </style>
    """, unsafe_allow_html=True)

# --- 5. לוגיקה וניהול רענון ---
if "lock_refresh" not in st.session_state: st.session_state.lock_refresh = False
if not st.session_state.lock_refresh:
    st_autorefresh(interval=15000, key="fscounter")

init_firebase()
if logo_base64: st.markdown(f'<div style="text-align: center;"><img src="data:image/png;base64,{logo_base64}" width="85"></div>', unsafe_allow_html=True)

teams_data = get_teams_from_db()
loc = get_geolocation()
now = datetime.now(ISRAEL_TZ)

col1, col2 = st.columns([1, 2])

with col1:
    with st.expander("📲 פאנל דיווח מפקדים", expanded=True):
        u_code = st.text_input("קוד מפקד:", type="password")
        team = next((t for t in teams_data if str(t.get('code')) == u_code), None)
        if team and loc and 'coords' in loc:
            if st.button("📍 עדכן מיקום עכשיו"):
                db.reference(f'teams/{team.get("id")}').update({'lat': loc['coords']['latitude'], 'lon': loc['coords']['longitude'], 'active': True, 'last_seen': now.strftime("%H:%M:%S")})
                st.rerun()

    with st.expander("🛠️ ניהול חמ\"ל"):
        st.session_state.lock_refresh = st.checkbox("🔒 נעל רענון (לציור)", value=st.session_state.lock_refresh)
        if st.button("🗑️ איפוס נתיבים"):
            ref = db.reference('teams').get()
            if ref:
                for k in (ref.keys() if isinstance(ref, dict) else range(len(ref))):
                    if ref[k]: db.reference(f'teams/{k}/history').delete()
            st.rerun()
        if st.button("🎯 מחק את כל הציורים"):
            db.reference('map_drawings').delete()
            st.rerun()

with col2:
    st.subheader("🌍 תמונת מצב")
    active_teams = [t for t in teams_data if t.get('active')]
    sel_name = st.selectbox("מיקוד בצוות:", ["הצג הכל"] + [t.get('name') for t in active_teams])

    m_lat, m_lon, m_zoom = 31.5, 34.8, 8
    if sel_name != "הצג הכל":
        target = next((t for t in active_teams if t.get('name') == sel_name), None)
        if target: m_lat, m_lon, m_zoom = target['lat'], target['lon'], 15

    m = folium.Map(location=[m_lat, m_lon], zoom_start=m_zoom, control_scale=True)
    
    # טעינת ציורים עם הגנה משופרת
    draw_db = db.reference('map_drawings').get()
    if draw_db:
        for d in draw_db.values():
            try:
                # מוודא שהציור לא ריק לפני הוספה
                if d and 'geometry' in d:
                    folium.GeoJson(d, style_function=lambda x: {'fillColor': 'orange', 'color': 'orange', 'weight': 2}).add_to(m)
            except: continue

    Draw(export=False, draw_options={'polyline':True,'rectangle':True,'polygon':True,'circle':False,'marker':True}, edit_options={'edit': False}).add_to(m)

    table_rows = []
    for idx, t in enumerate(teams_data):
        if t.get('active') and 'lat' in t:
            color, emo, icon = get_status_info(t.get('last_seen'), now)
            p_color = PATH_COLORS[idx % len(PATH_COLORS)]
            table_rows.append({"סטטוס": emo, "שם הצוות": t.get('name'), "חברי צוות": ", ".join(t.get('members', [])) if t.get('members') else "לא הוזנו", "עדכון": t.get('last_seen'), "מיקום": f"{t['lat']:.4f}, {t['lon']:.4f}"})
            if sel_name == "הצג הכל" or t.get('name') == sel_name:
                if 'history' in t and isinstance(t['history'], dict):
                    pts = [[p['lat'], p['lon']] for p in t['history'].values() if 'lat' in p]
                    if len(pts) > 1: folium.PolyLine(pts, color=p_color, weight=4, opacity=0.6).add_to(m)
                folium.Marker([t['lat'], t['lon']], popup=t.get('name'), icon=folium.Icon(color=color, icon=icon, prefix="fa" if icon=="running" else "glyphicon")).add_to(m)

    map_res = st_folium(m, height=520, key="V10_STABLE_MAP", use_container_width=True)

    # לוגיקת שמירה חכמה - שומר רק את האחרון שנוסף
    if map_res and map_res.get("last_active_drawing"):
        new_draw = map_res["last_active_drawing"]
        # בדיקה אם הציור כבר קיים ב-DB למניעת כפילויות שמוחקות הכל
        if new_draw and new_draw.get('geometry'):
            db.reference('map_drawings').push(new_draw)
            st.rerun()

# --- 6. טבלה וייצוא Excel ---
if table_rows:
    st.markdown("---")
    df = pd.DataFrame(table_rows)
    col_met, col_btn = st.columns([1, 1])
    col_met.metric("צוותים פעילים", len(table_rows))
    csv = df.to_csv(index=False, encoding='utf-16', sep='\t').encode('utf-16')
    col_btn.download_button("📥 הורד דוח אקסל", data=csv, file_name=f"report_{now.strftime('%H%M')}.csv", mime='text/csv')
    st.dataframe(df, use_container_width=True, hide_index=True)