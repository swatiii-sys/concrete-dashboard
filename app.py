import streamlit as st
from supabase import create_client
import pandas as pd

# 1. Connect to Supabase
url = "https://icneaaqjtrlujhwqtnrs.supabase.co"
key = "sb_publishable_SW2ROPWfLIpC4TdnAXV_Mg_oqc0STTq"
supabase = create_client(url, key)

# 2. Manage Login State
if "user" not in st.session_state:
    st.session_state.user = None

# 3. Login Screen
if st.session_state.user is None:
    st.title("Concrete Strength Monitor")
    st.subheader("Authorized Access Only")
    
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = response.user
            st.rerun()
        except Exception as e:
            st.error("Login failed. Please check your credentials.")

# 4. Main Dashboard (Only visible after login)
else:
    st.title("Live Concrete Curing Dashboard")
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()

    # Create Navigation Tabs
    tab1, tab2 = st.tabs(["🔴 Live Data (Supabase)", "📂 Upload CSV Data"])
    
    # Helper Function: Draws charts and calculates alerts for ANY data provided
    def display_dashboard(df):
        st.subheader("Curing Metrics")
        col1, col2 = st.columns(2)
        
        # Ensure the CSV has the correct columns before drawing charts
        if set(['age_h', 'slab_temp', 'strength_mpa']).issubset(df.columns):
            with col1:
                st.write("Slab Temperature (°C)")
                st.line_chart(df, x="age_h", y="slab_temp")
            with col2:
                st.write("Estimated Strength (MPa)")
                st.line_chart(df, x="age_h", y="strength_mpa")
            
            # Framework Removal System Logic
            st.subheader("Framework Removal Status")
            latest_strength = df['strength_mpa'].iloc[-1]
            
            if latest_strength < 15:
                st.error(f"🔴 ALERT: Concrete strength is {latest_strength:.1f} MPa. DO NOT remove framework.")
            elif 15 <= latest_strength < 20:
                st.warning(f"🟡 CAUTION: Concrete strength is {latest_strength:.1f} MPa. Curing is progressing.")
            else:
                st.success(f"🟢 SAFE: Target achieved at {latest_strength:.1f} MPa. Framework can be safely removed.")
                
            st.write("### Raw Data Log")
            st.dataframe(df.tail(10))
        else:
            st.error("Error: Your CSV must contain columns named exactly 'age_h', 'slab_temp', and 'strength_mpa'.")

    # --- TAB 1: Live Supabase Data ---
    with tab1:
        st.write("Fetching live sensor readings from the database...")
        try:
            response = supabase.table("strength_view").select("*").order("ts").execute()
            if response.data:
                live_df = pd.DataFrame(response.data)
                display_dashboard(live_df)
            else:
                st.info("No sensor data found in the database.")
        except Exception as e:
            st.error(f"Failed to fetch data: {e}")

    # --- TAB 2: CSV Upload ---
    with tab2:
        st.write("Upload offline sensor logs to test the strength prediction algorithm.")
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        
        if uploaded_file is not None:
            try:
                csv_df = pd.read_csv(uploaded_file)
                st.success("File uploaded successfully!")
                display_dashboard(csv_df)
            except Exception as e:
                st.error(f"Error reading file: {e}")
