import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import os

# פונקציה לחיבור בטוח
def init_firebase():
    if not firebase_admin._apps:
        # פתרון לבעיית נתיבים: מחפש את הקובץ בתיקייה שבה נמצא הסקריפט הנוכחי
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, "service_account.json")
        
        # אם לא מצא בתיקיית pages (במידה והקובץ בתיקייה הראשית)
        if not os.path.exists(json_path):
            parent_dir = os.path.dirname(current_dir)
            json_path = os.path.join(parent_dir, "service_account.json")

        if os.path.exists(json_path):
            try:
                cred = credentials.Certificate(json_path)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': "https://shavtsakedem-default-rtdb.europe-west1.firebasedatabase.app/"
                })
            except Exception as e:
                st.error(f"שגיאה פנימית במפתח: {e}")
                st.stop()
        else:
            st.error(f"קובץ service_account.json לא נמצא! וודא שהוא בתיקייה הראשית.")
            st.stop()

init_firebase()

st.set_page_config(page_title="ניהול מערכת", layout="wide")

# --- מנגנון נעילה ---
ADMIN_PASSWORD = "Matan4261!" 
if "admin_authenticated" not in st.session_state:
    st.session_state["admin_authenticated"] = False

if not st.session_state["admin_authenticated"]:
    st.title("🔐 גישה מוגבלת")
    pwd_input = st.text_input("הכנס קוד מנהל:", type="password")
    if st.button("כניסה"):
        if pwd_input == ADMIN_PASSWORD:
            st.session_state["admin_authenticated"] = True
            st.rerun()
        else:
            st.error("קוד שגוי!")
    st.stop()

st.title("⚙️ ניהול כוחות")

# תצוגת צוותים (כאן קרתה השגיאה)
try:
    ref = db.reference('teams')
    teams_data = ref.get()
    
    if teams_data:
        # המרה למבנה רשימה אם זה מילון
        if isinstance(teams_data, dict):
            teams_list = [v for v in teams_data.values() if v is not None]
        else:
            teams_list = [t for t in teams_data if t is not None]

        for team in teams_list:
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                col1.write(f"**{team.get('name', 'ללא שם')}** | קוד: {team.get('code', 'אין')}")
                if col2.button("מחק", key=f"del_{team.get('id')}"):
                    db.reference(f"teams/{team.get('id')}").delete()
                    st.rerun()
    else:
        st.info("אין צוותים רשומים כרגע.")

except Exception as e:
    st.error(f"שגיאה בתקשורת עם Firebase: {e}")
    st.info("זה קורה בדרך כלל כשהמפתח ב-JSON לא תקין. נסה להוריד מפתח חדש מהקונסול.")

# הוספת צוות חדש (מתחת לרשימה)
with st.expander("➕ הוספת צוות חדש"):
    with st.form("add_team"):
        name = st.text_input("שם הצוות")
        code = st.text_input("קוד גישה")
        if st.form_submit_button("שמור"):
            if name and code:
                # מציאת ה-ID הפנוי הבא
                existing = db.reference('teams').get()
                new_id = len(existing) if existing else 0
                db.reference(f'teams/{new_id}').set({
                    "id": new_id, "name": name, "code": str(code), "active": False
                })
                st.success("נוסף!")
                st.rerun()