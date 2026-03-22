import streamlit as st
import firebase_admin
from firebase_admin import credentials, db

# חיבור ל-Firebase
FIREBASE_URL = "https://shavtsakedem-default-rtdb.europe-west1.firebasedatabase.app/"

if not firebase_admin._apps:
    cred = credentials.Certificate("service_account.json")
    firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})

st.set_page_config(page_title="ניהול מערכת", layout="wide")

# --- מנגנון נעילת דף מנהל ---
ADMIN_PASSWORD = "Matan4261!" # <--- שנה את זה לקוד שאתה רוצה!

if "admin_authenticated" not in st.session_state:
    st.session_state["admin_authenticated"] = False

if not st.session_state["admin_authenticated"]:
    st.title("🔐 גישה מוגבלת")
    pwd_input = st.text_input("הכנס קוד מנהל כדי להמשיך:", type="password")
    if st.button("כניסה"):
        if pwd_input == ADMIN_PASSWORD:
            st.session_state["admin_authenticated"] = True
            st.rerun()
        else:
            st.error("קוד שגוי!")
    st.stop() # עוצר את הרצת שאר הדף אם לא התחברת

# --- מכאן והלאה זה הקוד הקיים של דף הניהול ---
st.markdown("<h1 style='text-align: center;'>⚙️ ממשק ניהול צוותים</h1>", unsafe_allow_html=True)
if st.button("התנתק"):
    st.session_state["admin_authenticated"] = False
    st.rerun()

# --- הוספת צוות חדש (הקוד הקודם שלך ממשיך כאן) ---
with st.expander("➕ הוספת צוות חדש למערכת"):
    with st.form("add_team_form"):
        new_name = st.text_input("שם הצוות")
        new_members = st.text_input("חברי הצוות")
        new_code = st.text_input("קוד גישה למפקד")
        submitted = st.form_submit_button("צור צוות")
        
        if submitted and new_name and new_code:
            ref = db.reference('teams')
            teams = ref.get() or []
            new_id = len(teams)
            new_team = {
                "id": new_id, "name": new_name, "members": new_members,
                "code": str(new_code), "active": False, "lat": 31.5, "lon": 34.8
            }
            db.reference(f'teams/{new_id}').set(new_team)
            st.success(f"צוות {new_name} נוסף!")
            st.rerun()

# הצגת רשימת הצוותים (המשך הקוד הקודם...)
st.subheader("📋 צוותים רשומים")
teams_data = db.reference('teams').get()
if teams_data:
    for team in teams_data:
        if team:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.write(f"**{team['name']}**")
                c2.write(f"🔑 קוד: {team.get('code', 'N/A')}")
                if c3.button("מחק", key=f"del_{team['id']}"):
                    db.reference(f'teams/{team["id"]}').delete()
                    st.rerun()
