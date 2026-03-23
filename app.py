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
st.set_page_config(page_title="שבצ''קדם - ניהול בזמן אמת", layout="wide")
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')

# רשימת צבעים לנתיבים (כדי להבדיל בין צוותים)
PATH_COLORS = ['blue', 'purple', 'darkred', 'orange', 'cadetblue', 'darkgreen', 'black', 'magenta']

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
        if isinstance(ref, dict):
            return [v for v in ref.values() if v]
        else:
            return [t for t in ref if t]
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

# --- 4. עיצוב ו-UI (CSS המלא והמפורט) ---

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
    
    /* עיצוב כללי של בלוקים */
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

    /* התאמה לניידים */
    @media (max-width: 768px) {{
        .stDeployButton {{display:none;}}
        #MainMenu {{visibility: hidden;}}
        header {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        [data-testid="stVerticalBlock"] {{
            padding: 10px;
        }}
        .stDataFrame {{
            font-size: 12px;
        }}
    }}

    /* עיצוב כפתורים מתקדם */
    div.stButton > button {{ 
        width: 100%; 
        border-radius: 10px; 
        font-weight: bold; 
        background-color: #2e5a27; 
        color: white; 
        height: 3.5em;
        border: none;
        transition: all 0.3s ease;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }}
    
    div.stButton > button:hover {{
        background-color: #3e7a35;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        transform: translateY(-1px);
    }}

    .footer-credit {{
        position: fixed;
        left: 15px;
        bottom: 15px;
        font-size: 0.75rem;
        color: rgba(0,0,0,0.6);
        background-color: rgba(255,255,255,0.4);
        padding: 2px 8px;
        border-radius: 5px;
        z-index: 100;
    }}

    header, footer {{visibility: hidden;}}

    .stDataFrame {{
        border-radius: 10px;
        overflow: hidden;
    }}
    </style>
    
    <div class="footer-credit">נוצר ע"י מתן בוחבוט</div>
    """, unsafe_allow_html=True)

# --- 5. לוגיקה מרכזית ---

# ניהול רענון חכם למניעת קריסת המפה
if "draw_update" not in st.session_state:
    st.session_state.draw_update = False

if not st.session_state.draw_update:
    st_autorefresh(interval=12000, key="fscounter")

init_firebase()

if logo_base64:
    st.markdown(f'<div style="text-align: center;"><img src="data:image/png;base64,{logo_base64}" width="85"></div>', unsafe_allow_html=True)

st.markdown("""
    <div style="text-align: center;">
        <h1 style='margin-bottom: 0; font-size: 2rem; color: #1e3d1a;'>מערכת שבצ''קדם</h1>
        <p style='color: #4a4a4a; font-size: 0.9rem; margin-top: 0; font-weight: bold;'>ניהול ושליטה בכוחות - נוצר ע"י מתן בוחבוט</p>
    </div>
    """, unsafe_allow_html=True)

teams_data = get_teams_from_db()
loc = get_geolocation()
now = datetime.now(ISRAEL_TZ)

col1, col2 = st.columns([1, 2])

# --- פאנל ימין ---
with col1:
    with st.expander("📲 פאנל דיווח מפקדים", expanded=True):
        user_code = st.text_input("הכנס קוד מפקד אישי:", type="password")
        found_team = next((t for t in teams_data if str(t.get('code')) == user_code), None)
        
        if found_team:
            team_id = found_team.get('id')
            st.success(f"מפקד זוהה: **{found_team.get('name')}**")
            auto_up = st.toggle("🛰️ הפעל שידור מיקום אוטומטי", value=False, key="auto_up")
            if loc and 'coords' in loc:
                lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
                if auto_up:
                    last_lat = st.session_state.get('last_lat_sent', 0)
                    if abs(last_lat - lat) > 0.00001:
                        if update_team_in_db(team_id, lat, lon):
                            st.session_state.last_lat_sent = lat
                elif st.button("📍 עדכן מיקום ידני עכשיו"):
                    if update_team_in_db(team_id, lat, lon):
                        st.toast("עודכן!")
                        st.rerun()
        elif user_code:
            st.error("❌ קוד לא תקין")

    with st.expander("🛠️ כלי ניהול חמ\"ל"):
        if st.button("🗑️ איפוס נתיבי תנועה"):
            try:
                ref = db.reference('teams')
                all_t = ref.get()
                if all_t:
                    for key in (all_t.keys() if isinstance(all_t, dict) else range(len(all_t))):
                        if all_t[key]: db.reference(f'teams/{key}/history').delete()
                st.rerun()
            except: pass
        
        if st.button("🎯 מחק את כל סימוני המפה"):
            db.reference('map_drawings').delete()
            st.rerun()

# --- פאנל שמאל (המפה) ---
with col2:
    st.subheader("🌍 תמונת מצב כוחות")
    active_teams = [t for t in teams_data if t.get('active')]
    team_options = ["הצג את כל הצוותים"] + [t.get('name') for t in active_teams]
    selected_team = st.selectbox("התמקד בצוות ספציפי:", team_options)

    map_center, map_zoom = [31.5, 34.8], 8
    if selected_team != "הצג את כל הצוותים":
        target = next((t for t in active_teams if t.get('name') == selected_team), None)
        if target and 'lat' in target:
            map_center, map_zoom = [target['lat'], target['lon']], 15

    # יצירת המפה בצורה יציבה
    m = folium.Map(location=map_center, zoom_start=map_zoom, control_scale=True)

    # 1. טעינת סימונים
    draw_db = db.reference('map_drawings').get()
    if draw_db:
        for d_key in draw_db:
            folium.GeoJson(draw_db[d_key], name="סימון").add_to(m)

    # 2. כלי ציור
    Draw(export=False, draw_options={'polyline':True, 'rectangle':True, 'polygon':True, 'circle':True, 'marker':True}, edit_options={'edit': False}).add_to(m)

    table_rows = []
    for idx, team in enumerate(teams_data):
        if team.get('active') and 'lat' in team:
            s_color, emoji, i_type = get_status_info(team.get('last_seen'), now)
            p_color = PATH_COLORS[idx % len(PATH_COLORS)]
            m_str = ", ".join(team.get('members', [])) if team.get('members') else "לא הוזנו"
            
            table_rows.append({
                "סטטוס": emoji, "שם הצוות": team.get('name'), "צבע נתיב": p_color,
                "חברי צוות": m_str, "עדכון אחרון": team.get('last_seen'), "מיקום": f"{team['lat']:.4f}, {team['lon']:.4f}"
            })

            if selected_team == "הצג את כל הצוותים" or team.get('name') == selected_team:
                if 'history' in team and isinstance(team['history'], dict):
                    points = [[p['lat'], p['lon']] for p in team['history'].values() if 'lat' in p]
                    if len(points) > 1:
                        folium.PolyLine(points, color=p_color, weight=4, opacity=0.6).add_to(m)

                folium.Marker(
                    [team['lat'], team['lon']],
                    popup=f"<b>{team.get('name')}</b>",
                    icon=folium.Icon(color=s_color, icon=i_type, prefix="fa" if i_type=="running" else "glyphicon")
                ).add_to(m)
    
    # הצגת המפה עם המפתח הסטטי הקריטי למניעת "פתיחה וסגירה"
    map_result = st_folium(m, width="100%", height=480, key="main_static_map_system")

    # לוגיקת שמירה חכמה
    if map_result and map_result.get("all_drawings"):
        all_draws = map_result["all_drawings"]
        existing = len(draw_db) if draw_db else 0
        if len(all_draws) > existing:
            st.session_state.draw_update = True
            db.reference('map_drawings').push(all_draws[-1])
            st.session_state.draw_update = False
            st.rerun()

# --- 6. טבלה ודוחות ---
if table_rows:
    st.markdown("---")
    df = pd.DataFrame(table_rows)[["סטטוס", "שם הצוות", "צבע נתיב", "חברי צוות", "עדכון אחרון", "מיקום"]]
    c1, c2 = st.columns([1, 1])
    c1.metric("צוותים בשטח", len(table_rows))
    csv_out = df.to_csv(index=False, encoding='utf-16', sep='\t').encode('utf-16')
    c2.download_button('📥 הורד דוח אקסל', csv_out, f"report_{now.strftime('%H%M')}.csv", 'text/csv')
    st.dataframe(df, use_container_width=True, hide_index=True)