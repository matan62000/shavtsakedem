import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
import firebase_admin
from firebase_admin import credentials, db
import os
import base64
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz # לטיפול בשעון ישראל

# --- 1. הגדרות דף ---
st.set_page_config(page_title="שבצ''קדם - ניהול בזמן אמת", layout="wide")

# פונקציה לטעינת תמונה והמרתה לפורמט שהדפדפן מבין (Base64)
def get_image_base64(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except Exception:
        return None

# טעינת התמונות מהתיקייה הראשית
logo_path = "kedem.png"
bg_path = "kedem1.jpeg"

logo_base64 = get_image_base64(logo_path)
bg_base64 = get_image_base64(bg_path)

# הכנת סטייל הרקע - רק אם התמונה קיימת
if bg_base64:
    bg_css = f"""
    [data-testid="stAppViewContainer"] {{
        background-image: url("data:image/png;base64,{bg_base64}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    """
else:
    bg_css = """
    [data-testid="stAppViewContainer"] {
        background-color: #1e2b1e; 
    }
    """

# --- 2. הזרקת עיצוב (CSS) ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;700&display=swap');
    {bg_css}
    [data-testid="stVerticalBlock"] {{
        background-color: rgba(255, 255, 255, 0.9);
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }}
    html, body, [data-testid="stSidebar"] {{
        direction: rtl;
        text-align: right;
        font-family: 'Assistant', sans-serif;
    }}
    div.stButton > button {{ 
        width: 100%; 
        border-radius: 10px; 
        height: 3.5em; 
        font-weight: bold; 
        background-color: #2e5a27;
        color: white;
        border: none;
    }}
    div.stButton > button:hover {{ background-color: #3a7531; }}
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    </style>
    """, unsafe_allow_html=True)

# --- 3. בניית הכותרת ---
if logo_base64:
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" width="120">'
else:
    logo_html = '<div style="font-size: 50px;">🛡️</div>'

st.markdown(f"""
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 10px;">
        {logo_html}
        <h1 style="margin-top: 10px; text-align: center;">מערכת שבצ''קדם - ניהול כוחות בזמן אמת</h1>
    </div>
    <hr>
    """, unsafe_allow_html=True)

# --- 4. פונקציות ליבה ו-Firebase ---
def init_firebase():
    if not firebase_admin._apps:
        try:
            if "firebase_service_account" not in st.secrets:
                st.error("❌ לא נמצאו הגדרות Firebase ב-Secrets")
                st.stop()
            secret_info = dict(st.secrets["firebase_service_account"])
            if "private_key" in secret_info:
                pk = secret_info["private_key"]
                pk = pk.replace("\\n", "\n").strip().strip('"')
                secret_info["private_key"] = pk
            cred = credentials.Certificate(secret_info)
            firebase_admin.initialize_app(cred, {
                'databaseURL': "https://shavtsakedem-default-rtdb.europe-west1.firebasedatabase.app/"
            })
        except Exception as e:
            st.error(f"שגיאה בחיבור ל-Firebase: {e}")
            st.stop()

st_autorefresh(interval=30000, limit=None, key="fscounter")
init_firebase()

def get_teams_from_db():
    try:
        ref = db.reference('teams')
        teams = ref.get()
        if not teams: return []
        if isinstance(teams, dict):
            return [v for v in teams.values() if v is not None]
        return [t for t in teams if t is not None]
    except Exception: return []

def update_team_in_db(team_id, lat, lon):
    try:
        israel_tz = pytz.timezone('Asia/Jerusalem')
        current_time = datetime.now(israel_tz).strftime("%H:%M:%S")
        db.reference(f'teams/{team_id}').update({
            'lat': lat, 'lon': lon, 'active': True, 'last_seen': current_time
        })
        return True
    except Exception: return False

# --- 5. לוגיקה ותצוגה ---
teams_data = get_teams_from_db()
loc = get_geolocation()
israel_tz = pytz.timezone('Asia/Jerusalem')
now = datetime.now(israel_tz)

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📲 דיווח מפקדים")
    user_code = st.text_input("הכנס קוד מפקד:", type="password")
    found_team = next((t for t in teams_data if str(t.get('code')) == user_code), None)
    
    if found_team:
        team_id = found_team.get('id')
        st.success(f"שלום מפקד {found_team.get('name')}")
        
        auto_upload = st.toggle("🛰️ שידור מיקום אוטומטי (חי)", value=False, key="auto_up")
        
        if auto_upload:
            if loc and 'coords' in loc:
                lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
                # מנגנון מניעת כפילויות - מעדכן רק אם זז מעל 10 מטר
                last_lat = st.session_state.get('last_lat_sent', 0)
                if abs(last_lat - lat) > 0.0001:
                    if update_team_in_db(team_id, lat, lon):
                        st.session_state.last_lat_sent = lat
                st.info("🛰️ שידור חי פעיל. נא להשאיר דף פתוח.")
        else:
            if st.button(f"📍 עדכן מיקום ידני"):
                if loc and 'coords' in loc:
                    lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
                    if update_team_in_db(team_id, lat, lon):
                        st.toast("עודכן!", icon="🚀")
                        st.rerun()
    elif user_code != "":
        st.error("❌ קוד שגוי")

with col2:
    st.subheader("🌍 מפת כוחות בזמן אמת")
    m = folium.Map(location=[31.5, 34.8], zoom_start=8)
    has_active_teams = False
    table_rows = []

    for team in teams_data:
        if team.get('active') and 'lat' in team and 'lon' in team:
            has_active_teams = True
            last_seen_str = team.get('last_seen', '')
            icon_color, status_emoji = "red", "🔴"
            
            try:
                last_time = datetime.strptime(last_seen_str, "%H:%M:%S").replace(
                    year=now.year, month=now.month, day=now.day)
                last_time = israel_tz.localize(last_time)
                diff = (now - last_time).total_seconds() / 60
                if diff <= 15: icon_color, status_emoji = "green", "🟢"
                elif diff <= 30: icon_color, status_emoji = "orange", "🟡"
            except: pass

            popup_html = f"<div dir='rtl'><b>צוות: {team.get('name')}</b><br>עדכון: {last_seen_str}</div>"
            folium.Marker(
                location=[team['lat'], team['lon']],
                popup=folium.Popup(popup_html, max_width=200),
                tooltip=team.get('name'),
                icon=folium.Icon(color=icon_color, icon="info-sign")
            ).add_to(m)

            table_rows.append({
                "סטטוס": status_emoji,
                "שם הצוות": team.get('name'),
                "קוד מפקד": team.get('code'),
                "חברי צוות": ", ".join(team.get('members', [])) if team.get('members') else "אין רשימה",
                "עדכון אחרון": last_seen_str,
                "מיקום": f"{team.get('lat', 0):.4f}, {team.get('lon', 0):.4f}"
            })
    
    st_folium(m, width="100%", height=500, key="main_map")
    if not has_active_teams: st.info("ממתין לדיווחים...")

# --- 6. טבלת בקרה וסיכום ---
st.markdown("---")
st.subheader("📊 סיכום סטטוס כוחות בשטח")

if table_rows:
    df = pd.DataFrame(table_rows)
    m1, m2 = st.columns([1, 1])
    m1.metric("סה\"כ צוותים פעילים", len(table_rows))
    
    csv = df.to_csv(index=False, encoding='utf-16', sep='\t').encode('utf-16')
    m2.download_button('📥 הורד דו"ח לאקסל', csv, f"report_{now.strftime('%H%M')}.csv", 'text/csv')
    st.dataframe(df, use_container_width=True, hide_index=True)