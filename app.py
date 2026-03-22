import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
import firebase_admin
from firebase_admin import credentials, db
import os

# --- 1. הגדרות דף ועיצוב RTL ---
st.set_page_config(page_title="שבצ''קדם - ניהול בזמן אמת", layout="wide")

st.markdown("""
    <style>
    .main { direction: rtl; text-align: right; }
    div.stButton > button { width: 100%; border-radius: 10px; height: 3em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>🛡️ שבצ''קדם - מערכת ניהול שבצ''קים בזמן אמת</h1>", unsafe_allow_html=True)

# --- 2. חיבור ל-Firebase באמצעות הקובץ ---
def init_firebase():
    if not firebase_admin._apps:
        try:
            # שליפת המידע מה-Secrets
            secret_info = dict(st.secrets["firebase_service_account"])
            
            # טיפול יסודי במפתח הפרטי
            if "private_key" in secret_info:
                pk = secret_info["private_key"]
                # מחליף ירידות שורה כתובות (\n) בירידות שורה אמיתיות
                pk = pk.replace("\\n", "\n")
                # מסיר גרשיים מיותרים ורווחים שאולי השתרבבו
                pk = pk.strip().strip('"')
                secret_info["private_key"] = pk

            cred = credentials.Certificate(secret_info)
            firebase_admin.initialize_app(cred, {
                'databaseURL': "https://shavtsakedem-default-rtdb.europe-west1.firebasedatabase.app/"
            })
        except Exception as e:
            st.error(f"שגיאה בחיבור ל-Firebase: {e}")
            st.stop()

# --- 3. פונקציות נתונים ---
def get_teams_from_db():
    try:
        ref = db.reference('teams')
        teams = ref.get()
        if not teams: return []
        if isinstance(teams, dict):
            return [v for v in teams.values()]
        return [t for t in teams if t is not None]
    except Exception as e:
        return []

def update_team_in_db(team_id, lat, lon):
    db.reference(f'teams/{team_id}').update({
        'lat': lat,
        'lon': lon,
        'active': True
    })

# --- 4. לוגיקה עסקית ---
teams_data = get_teams_from_db()
loc = get_geolocation()

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📲 דיווח מפקדים")
    user_code = st.text_input("הכנס קוד מפקד:", type="password")
    found_team = next((t for t in teams_data if str(t.get('code')) == user_code), None)
    
    if found_team:
        team_id = found_team['id']
        st.success(f"שלום מפקד {found_team['name']}")
        if st.button(f"עדכן מיקום נוכחי", key=f"btn_{team_id}"):
            if loc:
                update_team_in_db(team_id, loc['coords']['latitude'], loc['coords']['longitude'])
                st.toast("המיקום עודכן בהצלחה!")
                st.rerun()
            else:
                st.error("נא לאשר גישת מיקום בדפדפן")
    elif user_code != "":
        st.error("קוד שגוי")

with col2:
    st.subheader("🌍 מפת כוחות")
    m = folium.Map(location=[31.5, 34.8], zoom_start=8)
    for team in teams_data:
        if team.get('active') and 'lat' in team:
            folium.CircleMarker(
                location=[team['lat'], team['lon']],
                radius=12, color="red", fill=True, popup=team['name']
            ).add_to(m)
    st_folium(m, width=700, height=500)