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
                creds_dict = dict(st.secrets["firebase"])

                # 🔥 תיקון קריטי
                private_key = creds_dict["private_key"]
                
                # אם יש שורות אמיתיות → זה בסדר
                # אם יש \n → נהפוך אותם
                if "\\n" in private_key:
                    private_key = private_key.replace("\\n", "\n")

                creds_dict["private_key"] = private_key

                cred = credentials.Certificate(creds_dict)

                firebase_admin.initialize_app(cred, {
                    'databaseURL': "https://shavtsakedem-default-rtdb.europe-west1.firebasedatabase.app/"
                })

                st.success("🔥 Firebase initialized")

            else:
                st.error("❌ לא נמצאו secrets")

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

# --- בתוך ממשק הוספת/עריכת צוות ---
with st.expander("➕ הוספת צוות חדש"):
    new_team_name = st.text_input("שם הצוות:")
    new_team_code = st.text_input("קוד כניסה (מספרים):")
    # שדה חדש לחברי הצוות
    team_members_input = st.text_area("חברי הצוות (הפרד שמות בפסיק):", placeholder="ישראל ישראלי, משה כהן...")

    if st.button("צור צוות"):
        if new_team_name and new_team_code:
            # הפיכת הטקסט לרשימה של שמות נקיים מרווחים
            members_list = [m.strip() for m in team_members_input.split(",") if m.strip()]
            
            new_id = str(len(get_teams_from_db()) + 1)
            db.reference(f'teams/{new_id}').set({
                'id': new_id,
                'name': new_team_name,
                'code': new_team_code,
                'members': members_list, # שמירת הרשימה ב-Firebase
                'active': False
            })
            st.success(f"צוות {new_team_name} נוצר!")
            st.rerun()