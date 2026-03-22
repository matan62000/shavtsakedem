import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# --- 1. פונקציית אתחול משופרת (מנקה זיכרון) ---
def init_firebase():
    if not firebase_admin._apps:
        try:
            if "firebase" in st.secrets:
                creds_dict = json.loads(json.dumps(st.secrets["firebase"]))
                # השורה הזו מטפלת בבעיה של ה-\n אם הוא בכל זאת מגיע כטקסט
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
                
                cred = credentials.Certificate(creds_dict)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': "https://shavtsakedem-default-rtdb.europe-west1.firebasedatabase.app/"
                })
            else:
                st.error("❌ לא נמצאו הגדרות ב-Secrets")
        except Exception as e:
            st.error(f"❌ שגיאה באתחול: {e}")

init_firebase()

# --- 2. הגדרות דף ---
st.set_page_config(page_title="ניהול מערכת שווים", layout="wide")

# --- 3. בדיקת סיסמה ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 כניסת מנהל")
    pwd = st.text_input("הכנס סיסמת מנהל:", type="password")
    if st.button("כניסה"):
        if pwd == "Matan4261!":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("🚫 סיסמה שגויה")
    st.stop()

# --- 4. ממשק ניהול הצוותים ---
st.title("⚙️ לוח ניהול צוותים")
st.success("✅ החיבור ל-Firebase הצליח!")

st.subheader("👥 צוותים רשומים במערכת")
try:
    # שליפת נתונים - כאן בדרך כלל קופצת שגיאת ה-Signature אם המפתח פגום
    teams_ref = db.reference('teams')
    teams = teams_ref.get()
    
    if teams:
        if isinstance(teams, list):
            items = [(i, t) for i, t in enumerate(teams) if t is not None]
        else:
            items = teams.items()

        for key, team in items:
            with st.container(border=True):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.write(f"🏷️ **שם:** {team.get('name')} | 🔑 **קוד:** {team.get('code')}")
                with col2:
                    if st.button("🗑️ מחק", key=f"del_{key}"):
                        db.reference(f'teams/{key}').delete()
                        st.toast(f"צוות {team.get('name')} נמחק!")
                        st.rerun()
    else:
        st.info("אין צוותים רשומים כרגע.")
except Exception as e:
    st.error(f"⚠️ שגיאה בשליפת נתונים: {e}")
    if "invalid_grant" in str(e):
        st.warning("🚨 השגיאה נמשכת? רוקן את הקובץ .streamlit/secrets.toml לגמרי ועשה ריסטרט ל-VS Code.")

# --- 5. הוספת צוות חדש ---
st.divider()
with st.expander("➕ הוסף צוות חדש למערכת"):
    with st.form("add_team_form", clear_on_submit=True):
        new_name = st.text_input("שם הצוות")
        new_code = st.text_input("קוד גישה")
        submit = st.form_submit_button("שמור צוות ✅")
        
        if submit:
            if new_name and new_code:
                existing_teams = db.reference('teams').get()
                new_index = len(existing_teams) if existing_teams else 0
                
                db.reference(f'teams/{new_index}').set({
                    "id": new_index,
                    "name": new_name,
                    "code": str(new_code),
                    "active": False,
                    "lat": 32.0,
                    "lon": 34.8
                })
                st.success(f"הצוות '{new_name}' נוסף בהצלחה!")
                st.rerun()