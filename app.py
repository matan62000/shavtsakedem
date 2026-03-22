import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
import firebase_admin
from firebase_admin import credentials, db
import os
import base64  # הוספתי את ה-import החסר
from streamlit_autorefresh import st_autorefresh

# --- 1. הגדרות דף ---
st.set_page_config(page_title="שבצ''קדם - ניהול בזמן אמת", layout="wide")

# פונקציה לטעינת תמונה (לוגו)
def get_image_base64(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except Exception:
        return None

# הגדרת נתיבים
logo_path = "kedem.png"
logo_base64 = get_image_base64(logo_path)

# לינק לתמונת רקע מ-GitHub (וודא שהשם והמשתמש נכונים)
# אם אין לך עדיין לינק, שמתי כאן לינק גנרי של רקע צבאי/טקסטורה שחורה
BG_IMAGE_URL = "https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/background.jpg"

# --- 2. הזרקת עיצוב (CSS) כולל רקע ושקיפות ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;700&display=swap');
    
    /* הגדרת רקע לכל האתר */
    [data-testid="stAppViewContainer"] {{
        background-image: url("{BG_IMAGE_URL}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}

    /* יצירת שכבה חצי שקופה מעל הרקע כדי שהתוכן יהיה קריא */
    [data-testid="stVerticalBlock"] {{
        background-color: rgba(255, 255, 255, 0.9); /* לבן עם 90% שקיפות */
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }}

    html, body, [data-testid="stSidebar"] {{
        direction: rtl;
        text-align: right;
        font-family: 'Assistant', sans-serif;
    }}
    
    .main {{ direction: rtl; text-align: right; }}
    
    /* עיצוב כפתורים */
    div.stButton > button {{ 
        width: 100%; 
        border-radius: 10px; 
        height: 3em; 
        font-weight: bold; 
        background-color: #2e5a27; /* ירוק זית */
        color: white;
        border: none;
        transition: 0.3s;
    }}
    div.stButton > button:hover {{
        background-color: #45a049;
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    }}
    
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

init_firebase()

# --- 3. פונקציות נתונים ---
def get_teams_from_db():
    try:
        ref = db.reference('teams')
        teams = ref.get()
        if not teams: return []
        if isinstance(teams, dict):
            return [v for v in teams.values() if v is not None]
        return [t for t in teams if t is not None]
    except Exception as e:
        return []

def update_team_in_db(team_id, lat, lon):
    try:
        db.reference(f'teams/{team_id}').update({
            'lat': lat,
            'lon': lon,
            'active': True
        })
        return True
    except Exception:
        return False

# --- 4. לוגיקה עסקית ותצוגה ---
teams_data = get_teams_from_db()
loc = get_geolocation()

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📲 דיווח מפקדים")
    user_code = st.text_input("הכנס קוד מפקד:", type="password")
    
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
                st.error("⚠️ נא לאשר גישת GPS בדפדפן.")
    elif user_code != "":
        st.error("❌ קוד שגוי")

with col2:
    st.subheader("🌍 מפת כוחות בזמן אמת")
    
    m = folium.Map(location=[31.5, 34.8], zoom_start=8, control_scale=True)
    
    has_active_teams = False
    for team in teams_data:
        if team.get('active') and 'lat' in team and 'lon' in team:
            has_active_teams = True
            members = team.get('members', [])
            members_html = "<br>".join(members) if members else "אין חברים רשומים"
            
            popup_html = f"""
            <div style="direction: rtl; text-align: right; font-family: sans-serif; min-width: 150px;">
                <b style="color: #4CAF50;">צוות: {team.get('name')}</b><br>
                <hr style="margin: 5px 0;">
                <b>👥 חברים:</b><br>{members_html}<br>
                <b>🔑 קוד:</b> {team.get('code')}
            </div>
            """
            
            folium.Marker(
                location=[team['lat'], team['lon']],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=team.get('name'),
                icon=folium.Icon(color="red", icon="info-sign")
            ).add_to(m)
    
    st_folium(m, width="100%", height=500)
    
    if not has_active_teams:
        st.info("ממתין לדיווחים מהשטח...")

if st.button("🔄 רענן נתוני מפה"):
    st.rerun()