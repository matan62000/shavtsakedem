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
from datetime import datetime
import pytz

# --- 1. הגדרות דף ---
st.set_page_config(page_title="שבצ''קדם - ניהול בזמן אמת", layout="wide")

# פונקציה לטעינת תמונה והמרתה לפורמט Base64
def get_image_base64(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except Exception:
        return None

# טעינת התמונות
logo_path = "kedem.png"
bg_path = "kedem1.jpeg"
logo_base64 = get_image_base64(logo_path)
bg_base64 = get_image_base64(bg_path)

# עיצוב CSS מלא
bg_css = f"""
[data-testid="stAppViewContainer"] {{
    background-image: url("data:image/png;base64,{bg_base64}");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}}
""" if bg_base64 else "[data-testid='stAppViewContainer'] { background-color: #1e2b1e; }"

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

# כותרת עם לוגו
if logo_base64:
    st.markdown(f'<div style="text-align: center;"><img src="data:image/png;base64,{logo_base64}" width="120"></div>', unsafe_allow_html=True)
st.markdown("<h1 style='text-align: center;'>מערכת שבצ''קדם - ניהול כוחות בזמן אמת</h1><hr>", unsafe_allow_html=True)

# --- 2. Firebase & Autorefresh ---
def init_firebase():
    if not firebase_admin._apps:
        try:
            secret_info = dict(st.secrets["firebase_service_account"])
            secret_info["private_key"] = secret_info["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(secret_info)
            firebase_admin.initialize_app(cred, {'databaseURL': "https://shavtsakedem-default-rtdb.europe-west1.firebasedatabase.app/"})
        except Exception as e:
            st.error(f"שגיאה בחיבור ל-Firebase: {e}")

st_autorefresh(interval=30000, key="fscounter")
init_firebase()

def get_teams_from_db():
    try:
        ref = db.reference('teams').get()
        if not ref: return []
        if isinstance(ref, dict): return [v for v in ref.values() if v]
        return [t for t in ref if t]
    except: return []

def update_team_in_db(team_id, lat, lon):
    try:
        israel_tz = pytz.timezone('Asia/Jerusalem')
        current_time = datetime.now(israel_tz).strftime("%H:%M:%S")
        db.reference(f'teams/{team_id}').update({
            'lat': lat, 'lon': lon, 'active': True, 'last_seen': current_time
        })
        return True
    except: return False

# --- 3. לוגיקה ותצוגה ---
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
        auto_up = st.toggle("🛰️ שידור מיקום אוטומטי (חי)", value=False, key="auto_up")
        
        if auto_up and loc and 'coords' in loc:
            lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
            # מניעת רענון מיותר אם לא זז
            if abs(st.session_state.get('last_lat_sent', 0) - lat) > 0.0001:
                if update_team_in_db(team_id, lat, lon):
                    st.session_state.last_lat_sent = lat
            st.info("🛰️ שידור חי פעיל. נא להשאיר דף פתוח.")
        else:
            if st.button("📍 עדכן מיקום ידני"):
                if loc and 'coords' in loc:
                    update_team_in_db(team_id, loc['coords']['latitude'], loc['coords']['longitude'])
                    st.rerun()
    elif user_code != "":
        st.error("❌ קוד שגוי")

with col2:
    st.subheader("🌍 מפת כוחות בזמן אמת")
    m = folium.Map(location=[31.5, 34.8], zoom_start=8)
    table_rows = []
    has_active = False

    for team in teams_data:
        if team.get('active') and 'lat' in team:
            has_active = True
            last_seen_str = team.get('last_seen', '')
            icon_color, status_emoji = "red", "🔴"
            
            try:
                lt = israel_tz.localize(datetime.strptime(last_seen_str, "%H:%M:%S").replace(year=now.year, month=now.month, day=now.day))
                diff = (now - lt).total_seconds() / 60
                if diff <= 15: icon_color, status_emoji = "green", "🟢"
                elif diff <= 30: icon_color, status_emoji = "orange", "🟡"
            except: pass

            members = ", ".join(team.get('members', [])) if team.get('members') else "אין רשימה"
            folium.Marker(
                [team['lat'], team['lon']],
                popup=f"<b>צוות: {team.get('name')}</b><br>חברים: {members}<br>עדכון: {last_seen_str}",
                tooltip=team.get('name'),
                icon=folium.Icon(color=icon_color, icon="info-sign")
            ).add_to(m)

            table_rows.append({
                "סטטוס": status_emoji,
                "שם הצוות": team.get('name'),
                "קוד": team.get('code'),
                "עדכון אחרון": last_seen_str,
                "מיקום": f"{team['lat']:.4f}, {team['lon']:.4f}"
            })
    
    st_folium(m, width="100%", height=500, key="main_map")
    if st.button("🔄 רענן נתוני מפה עכשיו"):
        st.rerun()

# --- 4. טבלה ודוח אקסל ---
st.markdown("---")
st.subheader("📊 סיכום סטטוס כוחות בשטח")
if table_rows:
    df = pd.DataFrame(table_rows)
    m1, m2 = st.columns([1, 1])
    m1.metric("סה\"כ צוותים פעילים", len(table_rows))
    
    csv = df.to_csv(index=False, encoding='utf-16', sep='\t').encode('utf-16')
    m2.download_button('📥 הורד דו"ח לאקסל', csv, f"shavtsakedem_{now.strftime('%H%M')}.csv", 'text/csv')
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("ממתין לדיווחים...")