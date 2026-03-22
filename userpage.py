# --- אחרי ה-Login המצלח ---
if st.session_state.get("authenticated"):
    st.success(f"מחובר כצוות: {st.session_state.team_name}")

    # כאן נכנס הקוד של המיקום
    loc = get_geolocation() 
    
    if loc:
        lat = loc['coords']['latitude']
        lon = loc['coords']['longitude']
        
        # עדכון Firebase (כדי שהמנהל יראה אותם)
        db.reference(f'teams/{st.session_state.team_id}').update({
            'lat': lat,
            'lon': lon,
            'last_seen': str(datetime.now())
        })
        st.write("📍 המיקום שלך מעודכן במפה של המנהל")