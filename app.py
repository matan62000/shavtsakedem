import streamlit as st
import pd as pd
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

# --- 1. הגדרות תצורה וקבועים ---
st.set_page_config(page_title="שבצ''קדם - ניהול בזמן אמת", layout="wide")
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')

# --- 2. פונקציות עזר (Utils) ---

@st.cache_data
def get_image_base64(path):
    """טעינת תמונה והמרתה ל-Base64 עם caching לביצועים"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except Exception:
        return None

def init_firebase():
    """אתחול חיבור ל-Firebase"""
    if not firebase_admin._apps:
        try:
            secret_info = dict(st.secrets["firebase_service_account"])
            secret_info["private_key"] = secret_info["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(secret_info)
            firebase_admin.initialize_app(cred, {
                'databaseURL': "https://shavtsakedem-default-rtdb.europe-west1.firebasedatabase.app/"
            })
        except Exception as e:
            st.error(f"שגיאה בחיבור ל-Firebase: {e}")

def get_status_info(last_seen_str, now_dt):
    """חישוב צבע, אייקון וסטטוס לפי זמן עדכון אחרון"""
    if not last_seen_str:
        return "red", "🔴", "info-sign"
    try:
        lt = ISRAEL_TZ.localize(datetime.strptime(last_seen_str, "%H:%M:%S").replace(
            year=now_dt.year, month=now_dt.month, day=now_dt.day))
        diff = (now_dt - lt).total_seconds() / 60
        
        if diff <= 15: return "green", "🟢", "running"
        if diff <= 30: return "orange", "🟡", "info-sign"
        return "red", "🔴", "info-sign"
    except:
        return "red", "🔴", "info-sign"

# --- 3. פעולות מול Database ---

def get_teams_from_db():
    try:
        ref = db.reference('teams').get()
        if not ref: return []
        return [v for v in ref.values() if v] if isinstance(ref, dict) else [t for t in ref if t]
    except Exception:
        return []

def update_team_in_db(team_id, lat, lon):
    try:
        current_time = datetime.now(ISRAEL_TZ).strftime("%H:%M:%S")
        ref = db.reference(f'teams/{team_id}')
        
        # עדכון מיקום ראשי
        ref.update({
            'lat': lat, 'lon': lon, 'active': True, 'last_seen': current_time
        })
        
        # הוספה להיסטוריה
        ref.child('history').push({
            'lat': lat, 'lon': lon, 'time': current_time
        })
        return True
    except Exception:
        return False

# --- 4. עיצוב ו-UI (CSS) ---

logo_base64 = get_image_base64("kedem.png")
bg_base64 = get_image_base64("kedem1.jpeg")

bg_style = f"""
    [data-testid="stAppViewContainer"] {{
        background-image: url("data:image/png;base64,{bg_base64}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
""" if bg_base64 else ""

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;700&display=swap');
    {bg_style}
    [data-testid="stVerticalBlock"] {{
        background-color: rgba(255, 255, 255, 0.92);
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }}
    html, body, [data-testid="stSidebar"], .stMarkdown {{
        direction: rtl;
        text-align: right;
        font-family: 'Assistant', sans-serif;
    }}
    div.stButton > button {{ 
        width: 100%; border-radius: 10px; font-weight: bold; 
        background-color: #2e5a27; color: white; height: 3em;
    }}
    #MainMenu, footer, header {{visibility: hidden;}}
    </style>
    """, unsafe_allow_html=True)

# --- 5. לוגיקה מרכזית של האפליקציה ---

st_autorefresh(interval=10000, key="fscounter")
init_firebase()

# כותרת
if logo_base64:
    st.markdown(f'<div style="text-align: center;"><img src="data:image/png;base64,{logo_base64}" width="100"></div>', unsafe_allow_html=True)
st.markdown("<h1 style='text-align: center;'>מערכת שבצ''קדם - ניהול כוחות</h1>", unsafe_allow_html=True)

teams_data = get_teams_from_db()
loc = get_geolocation()
now = datetime.now(ISRAEL_TZ)

col1, col2 = st.columns([1, 2])

# --- פאנל דיווח (צד ימין) ---
with col1:
    st.subheader("📲 דיווח מפקדים")
    user_code = st.text_input("הכנס קוד מפקד:", type="password")
    found_team = next((t for t in teams_data if str(t.get('code')) == user_code), None)
    
    if found_team:
        team_id = found_team.get('id')
        st.success(f"שלום מפקד {found_team.get('name')}")
        auto_up = st.toggle("🛰️ שידור מיקום חי", value=False, key="auto_up")
        
        if loc and 'coords' in loc:
            lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
            if auto_up:
                last_lat = st.session_state.get('last_lat_sent', 0)
                if abs(last_lat - lat) > 0.00005: 
                    if update_team_in_db(team_id, lat, lon):
                        st.session_state.last_lat_sent = lat
                st.info("🛰️ שידור חי פעיל")
            elif st.button("📍 עדכן מיקום ידני"):
                update_team_in_db(team_id, lat, lon)
                st.rerun()
    elif user_code:
        st.error("❌ קוד שגוי")

# --- מפה (צד שמאל) ---
with col2:
    st.subheader("🌍 מפת כוחות")
    m = folium.Map(location=[31.5, 34.8], zoom_start=8)
    table_rows = []

    for team in teams_data:
        if team.get('active') and 'lat' in team:
            color, emoji, icon_type = get_status_info(team.get('last_seen'), now)
            
            # שליפת חברי הצוות (חדש)
            members_list = team.get('members', [])
            members_str = ", ".join(members_list) if members_list else "אין רשימת חברים"
            
            # ציור נתיב (היסטוריה)
            if 'history' in team and isinstance(team['history'], dict):
                points = [[p['lat'], p['lon']] for p in team['history'].values() if 'lat' in p]
                if len(points) > 1:
                    folium.PolyLine(points, color=color, weight=2, opacity=0.5, dash_array='5').add_to(m)

            # הוספת סמן למפה
            folium.Marker(
                [team['lat'], team['lon']],
                popup=f"<b>{team.get('name')}</b><br>חברים: {members_str}<br>עדכון: {team.get('last_seen')}",
                tooltip=team.get('name'),
                icon=folium.Icon(color=color, icon=icon_type, prefix="fa" if icon_type=="running" else "glyphicon")
            ).add_to(m)

            # הוספה לטבלה עם עמודת חברי צוות (חדש)
            table_rows.append({
                "סטטוס": emoji,
                "שם הצוות": team.get('name'),
                "חברי צוות": members_str,
                "עדכון אחרון": team.get('last_seen'),
                "מיקום": f"{team['lat']:.4f}, {team['lon']:.4f}"
            })
    
    st_folium(m, width="100%", height=450, key="main_map")

# --- 6. טבלה ודוחות ---
if table_rows:
    st.markdown("---")
    df = pd.DataFrame(table_rows)
    
    # סידור עמודות לטבלה נקייה
    columns_order = ["סטטוס", "שם הצוות", "חברי צוות", "עדכון אחרון", "מיקום"]
    df = df[columns_order]
    
    c1, c2 = st.columns([1, 1])
    c1.metric("צוותים פעילים", len(table_rows))
    
    csv = df.to_csv(index=False, encoding='utf-16', sep='\t').encode('utf-16')
    c2.download_button('📥 הורד דוח אקסל', csv, f"report_{now.strftime('%H%M')}.csv", 'text/csv')
    st.dataframe(df, use_container_width=True, hide_index=True)