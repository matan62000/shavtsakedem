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
import json

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

def update_team_in_db(team_id, lat, lon):
    try:
        current_time = datetime.now(ISRAEL_TZ).strftime("%H:%M:%S")
        ref = db.reference(f'teams/{team_id}')
        ref.update({'lat': lat, 'lon': lon, 'active': True, 'last_seen': current_time})
        ref.child('history').push({'lat': lat, 'lon': lon, 'time': current_time})
        return True
    except: return False

# --- 4. עיצוב (CSS המלא ללא חיתוכים) ---
logo_base64 = get_image_base64("kedem.png")
bg_base64 = get_image_base64("kedem1.jpeg")
bg_style = f"[data-testid='stAppViewContainer'] {{ background-image: url('data:image/png;base64,{bg_base64}'); background-size: cover; background-position: center; background-attachment: fixed; }}" if bg_base64 else ""

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;700&display=swap');
    {bg_style}
    
    /* עיצוב גמיש כדי לא לחנוק את המפה */
    [data-testid="stVerticalBlock"] {{
        background-color: rgba(255, 255, 255, 0.92);
        padding: 15px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }}
    
    html, body, [data-testid="stSidebar"], .stMarkdown {{
        direction: rtl; text-align: right; font-family: 'Assistant', sans-serif;
    }}

    div.stButton > button {{ 
        width: 100%; border-radius: 10px; font-weight: bold; 
        background-color: #2e5a27; color: white; height: 3.5em; transition: 0.3s;
    }}
    
    .footer-credit {{
        position: fixed; left: 15px; bottom: 15px; font-size: 0.7rem; color: rgba(0,0,0,0.5); z-index: 100;
    }}
    header, footer {{visibility: hidden;}}
    </style>
    <div class="footer-credit">נוצר ע"י מתן בוחבוט</div>
    """, unsafe_allow_html=True)

# --- 5. לוגיקה ---
st_autorefresh(interval=20000, key="fscounter") # 20 שניות ליציבות
init_firebase()

if logo_base64:
    st.markdown(f'<div style="text-align: center;"><img src="data:image/png;base64,{logo_base64}" width="85"></div>', unsafe_allow_html=True)

st.markdown('<div style="text-align: center;"><h1 style="margin-bottom: 0; font-size: 2rem; color: #1e3d1a;">מערכת שבצ\'קדם</h1><p style="color: #4a4a4a; font-size: 0.9rem; margin-top: 0;">ניהול ושליטה בכוחות - מתן בוחבוט</p></div>', unsafe_allow_html=True)

teams_data = get_teams_from_db()
loc = get_geolocation()
now = datetime.now(ISRAEL_TZ)

col1, col2 = st.columns([1, 2])

with col1:
    with st.expander("📲 דיווח מפקדים", expanded=True):
        u_code = st.text_input("קוד מפקד:", type="password")
        team = next((t for t in teams_data if str(t.get('code')) == u_code), None)
        if team:
            st.success(f"שלום {team.get('name')}")
            auto = st.toggle("🛰️ שידור חי", value=False)
            if loc and 'coords' in loc:
                lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
                if auto:
                    last_lat = st.session_state.get('last_lat', 0)
                    if abs(last_lat - lat) > 0.00001:
                        if update_team_in_db(team.get('id'), lat, lon): st.session_state.last_lat = lat
                elif st.button("📍 עדכן מיקום ידני"):
                    if update_team_in_db(team.get('id'), lat, lon): st.rerun()
        elif u_code: st.error("❌ קוד שגוי")

    with st.expander("🛠️ ניהול חמ\"ל"):
        if st.button("🗑️ נקה נתיבים"):
            ref = db.reference('teams').get()
            if ref:
                for k in (ref.keys() if isinstance(ref, dict) else range(len(ref))):
                    if ref[k]: db.reference(f'teams/{k}/history').delete()
            st.rerun()
        if st.button("🎯 מחק ציורים"):
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

    # בניית המפה
    m = folium.Map(location=[m_lat, m_lon], zoom_start=m_zoom, control_scale=True)
    
    # טעינת ציורים
    draw_db = db.reference('map_drawings').get()
    if draw_db:
        for d in draw_db.values(): folium.GeoJson(d).add_to(m)

    # כלי ציור
    Draw(export=False, draw_options={'polyline':True,'rectangle':True,'polygon':True,'circle':False,'marker':True}, edit_options={'edit': False}).add_to(m)

    table_rows = []
    for idx, t in enumerate(teams_data):
        if t.get('active') and 'lat' in t:
            color, emo, icon = get_status_info(t.get('last_seen'), now)
            p_color = PATH_COLORS[idx % len(PATH_COLORS)]
            m_str = ", ".join(t.get('members', [])) if t.get('members') else "אין רשימה"
            
            table_rows.append({
                "סטטוס": emo, "שם הצוות": t.get('name'), "צבע נתיב": p_color,
                "חברי צוות": m_str, "עדכון אחרון": t.get('last_seen'), "מיקום": f"{t['lat']:.4f}, {t['lon']:.4f}"
            })

            if sel_name == "הצג הכל" or t.get('name') == sel_name:
                if 'history' in t and isinstance(t['history'], dict):
                    pts = [[p['lat'], p['lon']] for p in t['history'].values() if 'lat' in p]
                    if len(pts) > 1: folium.PolyLine(pts, color=p_color, weight=4, opacity=0.6).add_to(m)
                folium.Marker([t['lat'], t['lon']], popup=t.get('name'), icon=folium.Icon(color=color, icon=icon, prefix="fa" if icon=="running" else "glyphicon")).add_to(m)

    # הצגת המפה עם רוחב אוטומטי מלא
    map_res = st_folium(m, width=700, height=480, key="V4_STABLE")

    if map_res and map_res.get("all_drawings"):
        if len(map_res["all_drawings"]) > (len(draw_db) if draw_db else 0):
            db.reference('map_drawings').push(map_res["all_drawings"][-1])
            st.rerun()

# --- 6. טבלה ---
if table_rows:
    st.markdown("---")
    df = pd.DataFrame(table_rows)[["סטטוס", "שם הצוות", "צבע נתיב", "חברי צוות", "עדכון אחרון", "מיקום"]]
    csv = df.to_csv(index=False, encoding='utf-16', sep='\t').encode('utf-16')
    st.download_button('📥 הורד אקסל', csv, f"report_{now.strftime('%H%M')}.csv", 'text/csv')
    st.dataframe(df, use_container_width=True, hide_index=True)