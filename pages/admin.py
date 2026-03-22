import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import os

def init_firebase():
    if not firebase_admin._apps:
        try:
            # הגדרת הנתיב לקובץ שהורדת ושמת בתיקייה
            json_path = "service_account.json"
            
            if os.path.exists(json_path):
                # טעינה ישירה מהקובץ הפיזי - הדרך הכי בטוחה
                cred = credentials.Certificate(json_path)
            else:
                # גיבוי: אם הקובץ לא נמצא, ננסה להשתמש ב-Secrets
                s_acc = dict(st.secrets["firebase_service_account"])
                if "private_key" in s_acc:
                    s_acc["private_key"] = s_acc["private_key"].replace("\\n", "\n")
                cred = credentials.Certificate(s_acc)

            firebase_admin.initialize_app(cred, {
                'databaseURL': "https://shavtsakedem-default-rtdb.europe-west1.firebasedatabase.app/"
            })
        except Exception as e:
            st.error(f"שגיאה בחיבור ל-Firebase: {e}")
            st.stop()

init_firebase()

# --- ממשק המנהל ---
st.set_page_config(page_title="ניהול מערכת", layout="wide")
st.title("⚙️ לוח ניהול צוותים")

# מנגנון סיסמה
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    pwd = st.text_input("הכנס קוד מנהל:", type="password")
    if st.button("כניסה"):
        if pwd == "Matan4261!":
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("קוד שגוי")
    st.stop()

# ניהול צוותים
try:
    ref = db.reference('teams')
    data = ref.get()
    if data:
        items = data.items() if isinstance(data, dict) else enumerate(data)
        for key, team in items:
            if team:
                with st.container(border=True):
                    c1, c2 = st.columns([4,1])
                    c1.write(f"**{team.get('name')}** (קוד: {team.get('code')})")
                    if c2.button("מחק", key=f"del_{key}"):
                        db.reference(f'teams/{key}').delete()
                        st.rerun()
    else:
        st.info("אין צוותים.")
except Exception as e:
    st.error(f"שגיאה: {e}")

# הוספה
with st.expander("➕ הוסף צוות"):
    with st.form("add"):
        n = st.text_input("שם")
        c = st.text_input("קוד")
        if st.form_submit_button("שמור"):
            if n and c:
                exist = db.reference('teams').get()
                idx = len(exist) if exist else 0
                db.reference(f'teams/{idx}').set({"id": idx, "name": n, "code": c})
                st.rerun()