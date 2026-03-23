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

# --- 1. הגדרות תצורה וקבועים ---
st.set_page_config(page_title="שבצ'קדם - ניהול בזמן אמת", layout="wide")
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')
PATH_COLORS = ['blue', 'purple', 'darkred', 'orange', 'cadetblue', 'darkgreen', 'black', 'magenta']

# --- 2. פונקציות עזר (Utils) ---

@st.cache_data
def get_image_base64(path):
    if not os.path.exists(path): return None
    try:
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except Exception: return None

def init_firebase():
    if not firebase_admin._apps:
        try:
            secret_info = dict(st.secrets["firebase_service_account"])
            secret_info["private_key"] = secret_info["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(secret_info)
            firebase_admin.initialize_app(cred, {
                'databaseURL': "https://shavtsakedem-default-rtdb.europe-west1.firebasedatabase.app/"
            })
        except Exception as e: st.error(f"שגיאה בחיבור ל-Firebase: {e}")

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

# --- 3. פעולות מול Database ---

def get_teams_from_db():
    try:
        ref = db.reference('teams').get()
        if not ref: return []
        return [v for v in ref.values() if v] if isinstance(ref, dict) else [t for t in ref if t]
    except Exception: return []

def update_team_in_db(team_id, lat, lon):
    try:
        current_time = datetime.now(ISRAEL_TZ).strftime("%H:%M:%S")
        ref = db.reference(f'teams/{team_id}')
        ref.update({'lat': lat, 'lon': lon, 'active': True, 'last_seen': current_time})
        ref.child('history').push({'lat': lat, 'lon': lon, 'time': current_time})
        return True
    except Exception: return False

# --- 4. עיצוב ו-UI (CSS המלא והמפורט) ---

logo_base64 = get_image_base64("kedem.png")
bg_base64 = get_image_base64("kedem1.jpeg")
bg_style = f"[data-testid='stAppViewContainer'] {{ background-image: url('data:image/png;base64,{bg_base64}'); background-size: cover; background-position: center; background-attachment: fixed; }}" if bg_base64 else ""

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;700&display=swap');
    {bg_style}
    [data-testid="stVerticalBlock"] {{ background-color: rgba(255, 255, 255, 0.92); padding: 20px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }}
    html, body, [data-testid="stSidebar"], .stMarkdown {{ direction: rtl; text-align: right; font-family: 'Assistant', sans-serif; }}
    @media (max-width: 768px) {{ .stDeployButton {{display:none;}} #MainMenu, header, footer {{visibility: hidden;}} [data-testid="stVerticalBlock"] {{ padding: 10px; }} }}
    div.stButton > button {{ width: 100%; border-radius: 10px; font-weight: bold; background-color: #2e5a27; color: white; height: 3.5em; transition: 0.3s; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
    div.stButton > button:hover {{ background-color: #3e7a35; transform: translateY(-1px); }}
    .footer-credit {{ position: fixed; left: 15px; bottom: 15px; font-size: 0.75rem; color: rgba(0,0,0,0.6); background-color: rgba(255,255,255,0.4); padding: 2px 8px; border-radius: 5px; z-index: 100; }}
    header, footer {{visibility: hidden;}}
    .stDataFrame {{ border-radius: 10px; overflow: hidden; }}
    </style>
    <div class="footer-credit">נוצר ע"י מתן בוחבוט</div>
    """, unsafe_allow_html=True)

# --- 5. לוגיקה מרכזית ---

if "is_drawing" not in st.session_state: st.session_state.is_drawing = False
if not st.session_state.is_drawing: st_autorefresh(interval=15000, key="fscounter")

init_firebase()
if logo_base64: st.markdown(f'<div style="text-align: center;"><img src="data:image/png;base64,{logo_base64}" width="85"></div>', unsafe_allow_html=True)

# --- השורה המתוקנת (שורה 101 המקורית) ---
st.markdown("""
<div style='text-align: center;'>
    <h1 style='margin-bottom: 0; font-size: 2rem; color: #1e3d1a;'>מערכת שבצ'קדם</h1>
    <p style='color: #4a4a4a; font-size: 0.9rem; margin-top: 0; font-weight: bold;'>ניהול ושליטה בכוחות - נוצר ע"י מתן בוחבוט</p>
</div>
""", unsafe_allow_html=True)

teams_data = get_teams_from_db()
loc = get_geolocation()
now = datetime.now(ISRAEL_TZ)

col1, col2 = st.columns([1, 2])

with col1:
    with st.expander("📲 פאנל דיווח מפקדים", expanded=True):
        user_code = st.text_input("הכנס קוד מפקד:", type="password")
        found_team = next((t for t in teams_data if str(t.get('code')) == user_code), None)
        if found_team:
            st.success(f"מפקד זוהה: **{found_team.get('name')}**")
            auto_up = st.toggle("🛰️ הפעל שידור מיקום אוטומטי", value=False)
            if loc and 'coords' in loc:
                lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
                if auto_up:
                    if abs(st.session_state.get('last_lat', 0) - lat) > 0.00001:
                        if update_team_in_db(found_team.get('id'), lat, lon): st.session_state.last_lat = lat
                elif st.button("📍 עדכון מיקום ידני"):
                    if update_team_in_db(found_team.get('id'), lat, lon): st.rerun()
        elif user_code: st.error("❌ קוד מפקד לא תקין")

    with st.expander("🛠️ כלי ניהול חמ\"ל"):
        if st.button("🗑️ איפוס נתיבי תנועה"):
            try:
                ref = db.reference('teams').get()
                if ref:
                    for key in (ref.keys() if isinstance(ref, dict) else range(len(ref))):
                        if ref[key]: db.reference(f'teams/{key}/history').delete()
                st.rerun()
            except: pass
        if st.button("🎯 מחק את כל סימוני המפה"):
            db.reference('map_drawings').delete()
            st.rerun()

with col2:
    st.subheader("🌍 תמונת מצב כוחות")
    active_teams = [t for t in teams_data if t.get('active')]
    sel_team = st.selectbox("התמקד בצוות ספציפי:", ["הצג את כל הצוותים"] + [t.get('name') for t in active_teams])

    m_lat, m_lon, m_zoom = 31.5, 34.8, 8
    if sel_team != "הצג את כל הצוותים":
        target = next((t for t in active_teams if t.get('name') == sel_team), None)
        if target: m_lat, m_lon, m_zoom = target['lat'], target['lon'], 15

    m = folium.Map(location=[m_lat, m_lon], zoom_start=m_zoom, control_scale=True)
    
    draw_db = db.reference('map_drawings').get()
    if draw_db:
        for d_key in draw_db:
            try: folium.GeoJson(draw_db[d_key]).add_to(m)
            except: continue

    Draw(export=False, draw_options={'polyline':True,'rectangle':True,'polygon':True,'circle':False,'marker':True}, edit_options={'edit':False}).add_to(m)

    table_rows = []
    for idx, team in enumerate(teams_data):
        if team.get('active') and 'lat' in team:
            status_color, emoji, icon_type = get_status_info(team.get('last_seen'), now)
            p_color = PATH_COLORS[idx % len(PATH_COLORS)]
            m_str = ", ".join(team.get('members', [])) if team.get('members') else "לא הוזנו חברים"
            table_rows.append({"סטטוס": emoji, "שם הצוות": team.get('name'), "צבע נתיב": p_color, "חברי צוות": m_str, "עדכון אחרון": team.get('last_seen'), "מיקום": f"{team['lat']:.4f}, {team['lon']:.4f}"})
            
            if sel_team == "הצג את כל הצוותים" or team.get('name') == sel_team:
                if 'history' in team and isinstance(team['history'], dict):
                    pts = [[p['lat'], p['lon']] for p in team['history'].values() if 'lat' in p]
                    if len(pts) > 1: folium.PolyLine(pts, color=p_color, weight=4, opacity=0.6).add_to(m)
                folium.Marker([team['lat'], team['lon']], popup=team.get('name'), icon=folium.Icon(color=status_color, icon=icon_type, prefix="fa" if icon_type=="running" else "glyphicon")).add_to(m)
    
    map_res = st_folium(m, width=None, height=480, key="FINAL_SAFE_MAP", use_container_width=True)

    if map_res and map_res.get("all_drawings"):
        if len(map_res["all_drawings"]) > (len(draw_db) if draw_db else 0):
            st.session_state.is_drawing = True
            db.reference('map_drawings').push(map_res["all_drawings"][-1])
            st.session_state.is_drawing = False
            st.rerun()

if table_rows:
    st.markdown("---")
    df = pd.DataFrame(table_rows)[["סטטוס", "שם הצוות", "צבע נתיב", "חברי צוות", "עדכון אחרון", "מיקום"]]
    m1, m2 = st.columns([1, 1])
    m1.metric("סה\"כ צוותים בשטח", len(table_rows))
    csv_out = df.to_csv(index=False, encoding='utf-16', sep='\t').encode('utf-16')
    m2.download_button(label='📥 הורד דוח פעילות (Excel)', data=csv_out, file_name=f"shavtsakedem_report_{now.strftime('%H%M')}.csv", mime='text/csv')
    st.dataframe(df, use_container_width=True, hide_index=True)