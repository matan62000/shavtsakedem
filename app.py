import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
import firebase_admin
from firebase_admin import credentials, db
import os
from streamlit_autorefresh import st_autorefresh

# --- 1. הגדרות דף ועיצוב RTL ---
st.set_page_config(page_title="שבצ''קדם - ניהול בזמן אמת", layout="wide")

def get_image_base64(path):
    try:
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except FileNotFoundError:
        return None # מחזיר None אם הקובץ לא נמצא

# טעינת סמל הגדוד (תחליף את הנתיב לשם הקובץ שלך!)
logo_path = "assets/logo.png" 
logo_base64 = get_image_base64(logo_path)

# בניית ה-HTML של הכותרת עם הסמל
header_html = f"""
<div style="direction: rtl; text-align: right; display: flex; align-items: center; justify-content: center; gap: 20px; padding: 10px; margin-bottom: 20px;">
"""
if logo_base64:
    header_html += f'<img src="data:image/png;base64,{logo_base64}" width="80" alt="סמל הגדוד">'

header_html += """
    <h1 style='margin: 0; font-family: sans-serif; font-size: 2.5em;'>🛡️ שבצ''קדם - מערכת ניהול שבצ''קים</h1>
</div>
"""

# הזרקת ה-CSS המעודכן (RTL ועיצוב כפתורים)
st.markdown("""
    <style>
    .main { direction: rtl; text-align: right; font-family: sans-serif; }
    div.stButton > button { 
        width: 100%; 
        border-radius: 10px; 
        height: 3em; 
        font-weight: bold; 
        background-color: #4CAF50; /* ירוק */
        color: white;
        border: none;
    }
    div.stButton > button:hover {
        background-color: #45a049; /* ירוק כהה יותר בריחוף */
    }
    /* הסרת תפריטים מובנים של Streamlit למראה נקי */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# הצגת הכותרת עם הסמל
st.markdown(header_html, unsafe_allow_html=True)

st.markdown("""
    <style>
    .main { direction: rtl; text-align: right; }
    div.stButton > button { width: 100%; border-radius: 10px; height: 3em; font-weight: bold; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>🛡️ שבצ''קדם - מערכת ניהול שבצ''קים בזמן אמת</h1>", unsafe_allow_html=True)

# --- 2. חיבור ל-Firebase ---
def init_firebase():
    if not firebase_admin._apps:
        try:
            # בדיקה אם ה-Secrets קיימים
            if "firebase_service_account" not in st.secrets:
                st.error("❌ לא נמצאו הגדרות Firebase ב-Secrets של המערכת")
                st.stop()

            # שליפת המידע מה-Secrets
            secret_info = dict(st.secrets["firebase_service_account"])
            
            # טיפול יסודי במפתח הפרטי (המרת \n לירידות שורה אמיתיות)
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

count = st_autorefresh(interval=30000, limit=None, key="fscounter")

# הפעלת האתחול
init_firebase()

# --- 3. פונקציות נתונים ---
def get_teams_from_db():
    try:
        ref = db.reference('teams')
        teams = ref.get()
        if not teams: return []
        # הפיכת הנתונים לרשימה נקייה (מטפל גם במילון וגם ברשימה עם None)
        if isinstance(teams, dict):
            return [v for v in teams.values() if v is not None]
        return [t for t in teams if t is not None]
    except Exception as e:
        st.sidebar.error(f"שגיאה בשליפת נתונים: {e}")
        return []

def update_team_in_db(team_id, lat, lon):
    try:
        # עדכון המיקום והגדרת הצוות כפעיל
        db.reference(f'teams/{team_id}').update({
            'lat': lat,
            'lon': lon,
            'active': True
        })
        return True
    except Exception as e:
        st.error(f"שגיאה בעדכון מסד הנתונים: {e}")
        return False

# --- 4. לוגיקה עסקית ותצוגה ---
teams_data = get_teams_from_db()

# קריאת מיקום בזמן אמת מהדפדפן
loc = get_geolocation()

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📲 דיווח מפקדים")
    user_code = st.text_input("הכנס קוד מפקד:", type="password")
    
    # חיפוש הצוות לפי הקוד שהוזן
    found_team = next((t for t in teams_data if str(t.get('code')) == user_code), None)
    
    if found_team:
        team_id = found_team.get('id')
        st.success(f"שלום מפקד {found_team.get('name', 'לא ידוע')}")
        
        if st.button(f"📍 עדכן מיקום נוכחי ושלח כוחות", key=f"btn_{team_id}"):
            if loc and 'coords' in loc:
                lat = loc['coords']['latitude']
                lon = loc['coords']['longitude']
                if update_team_in_db(team_id, lat, lon):
                    st.toast("✅ המיקום עודכן בהצלחה!", icon="🚀")
                    st.rerun()
            else:
                st.error("⚠️ לא ניתן לקבל מיקום. נא לאשר גישת GPS בדפדפן ולנסות שוב.")
    elif user_code != "":
        st.error("❌ קוד שגוי או צוות לא קיים")

with col2:
    st.subheader("🌍 מפת כוחות בזמן אמת")
    
    # הגדרת מרכז המפה (לפי המיקום המדווח הראשון או מרכז הארץ)
    center_lat, center_lon = 31.5, 34.8
    m = folium.Map(location=[center_lat, center_lon], zoom_start=8, control_scale=True)
    
    # הוספת סמנים לכל הצוותים הפעילים
    has_active_teams = False
    for team in teams_data:
        if team.get('active') and 'lat' in team and 'lon' in team:
            # 1. הכנת רשימת חברי הצוות כטקסט
            members = team.get('members', [])
            members_text = ", ".join(members) if members else "אין חברים רשומים"
            
            # 2. בניית תוכן ה-Popup (מה שיופיע כשלוחצים)
            # אפשר להשתמש ב-HTML בסיסי לעיצוב
            popup_html = f"""
            <div style="direction: rtl; text-align: right; font-family: sans-serif;">
                <b>צוות:</b> {team.get('name')}<br>
                <b>חברי צוות:</b> {members_text}<br>
                <b>קוד:</b> {team.get('code')}
            </div>
            """
            
            folium.Marker(
                location=[team['lat'], team['lon']],
                popup=folium.Popup(popup_html, max_width=300), # הצגת הפרטים בלחיצה
                tooltip=team.get('name'), # הצגת השם בריחוף עכבר
                icon=folium.Icon(color="red", icon="info-sign")
            ).add_to(m)
    
    # הצגת המפה
    st_folium(m, width="100%", height=500)
    
    if not has_active_teams:
        st.info("ממתין לדיווחים מהשטח... כרגע אין צוותים פעילים על המפה.")

# כפתור רענון ידני בתחתית
if st.button("🔄 רענן נתוני מפה"):
    st.rerun()