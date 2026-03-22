import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
import firebase_admin
from firebase_admin import credentials, db

# --- 1. הגדרות דף ועיצוב RTL ---
st.set_page_config(page_title="שבצ''קדם - ניהול בזמן אמת", layout="wide")

st.markdown("""
    <style>
    .main { direction: rtl; text-align: right; }
    div.stButton > button { width: 100%; border-radius: 10px; height: 3em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>🛡️ שבצ''קדם - מערכת ניהול שבצ''קים בזמן אמת</h1>", unsafe_allow_html=True)

# --- 2. חיבור ל-Firebase ---
# החלף את הכתובת למטה בכתובת שהעתקת מה-Realtime Database שלך!
FIREBASE_URL = "https://shavtsakedem-default-rtdb.europe-west1.firebasedatabase.app/"

if not firebase_admin._apps:
    cred = credentials.Certificate("service_account.json")
    firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})

# --- 3. פונקציות עזר לנתונים ---
def get_teams_from_db():
    ref = db.reference('teams')
    teams = ref.get()
    if not teams:
        # נתונים ראשוניים אם המסד ריק
        initial_teams = [
            {"id": 0, "name": "צוות אלפא", "members": "ישראל, משה", "active": False, "lat": 31.76, "lon": 35.21},
            {"id": 1, "name": "צוות ברבו", "members": "דנה, רוני", "active": False, "lat": 32.08, "lon": 34.78},
        ]
        ref.set(initial_teams)
        return initial_teams
    return teams

def update_team_in_db(team_id, lat, lon):
    ref = db.reference(f'teams/{team_id}')
    ref.update({'lat': lat, 'lon': lon, 'active': True})

# --- שליפת נתונים מהענן ---
teams_data = get_teams_from_db()

# --- כאן מוסיפים את השורה שחסרה לך! ---
# השורה הזו יוצרת את רשימת הקודים מתוך מה שקיים ב-Firebase
COMMANDER_CODES = {str(t['code']): t['id'] for t in teams_data if t and 'code' in t}
# ---------------------------------------

# מיקום ה-GPS (הקוד הקיים שלך)
loc = get_geolocation()

# --- 4. ממשק משתמש ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🔑 כניסת מפקד צוות")
    
    # שים לב: כל השורות הבאות מיושרות בדיוק באותו קו מתחת ל-st.subheader
    user_code = st.text_input("הכנס קוד מפקד אישי:", type="password", key="commander_input")
    
    if user_code in COMMANDER_CODES:
        team_id = COMMANDER_CODES[user_code]
        # מוודא שה-ID קיים ברשימת הצוותים מה-Firebase
        team = next((t for t in teams_data if t and t['id'] == team_id), None)
        
        if team:
            st.success(f"שלום מפקד {team['name']}, גישת דיווח מאושרת.")
            with st.container(border=True):
                st.write(f"📌 דיווח מיקום עבור: **{team['name']}**")
                if st.button(f"עדכן מיקום נוכחי במפה", key=f"report_{team_id}"):
                    if loc:
                        update_team_in_db(team_id, loc['coords']['latitude'], loc['coords']['longitude'])
                        st.toast(f"המיקום של {team['name']} עודכן!")
                        st.rerun()
                    else:
                        st.error("ה-GPS לא זמין. וודא אישור מיקום בדפדפן.")
    
    elif user_code != "":
        st.error("קוד שגוי. פנה למנהל המערכת.")

with col2:
    st.subheader("🌍 מפת כוחות")
    m = folium.Map(location=[31.5, 34.8], zoom_start=8)
    
    for team in teams_data:
        # בדיקה שהצוות פעיל ויש לו נ"צ
        if team.get('active') and 'lat' in team:
            folium.CircleMarker(
                location=[team['lat'], team['lon']],
                radius=12, color="red", fill=True, fill_color="red", fill_opacity=0.6,
                popup=f"{team['name']}: {team['members']}"
            ).add_to(m)
            
            folium.map.Marker(
                [team['lat'], team['lon']],
                icon=folium.DivIcon(html=f'<div style="font-size: 12pt; color: red; font-weight: bold; width: 100px;">{team["name"]}</div>')
            ).add_to(m)
            
    st_folium(m, width="100%", height=600)