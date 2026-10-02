import streamlit as st
from supabase import create_client
import pandas as pd
import joblib

# --- PAGE CONFIGURATION (Must be the first Streamlit command) ---
st.set_page_config(
    page_title="Concrete Curing Analytics",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 1. Connect to Supabase
url = "https://icneaaqjtrlujhwqtnrs.supabase.co"
key = "sb_publishable_SW2ROPWfLIpC4TdnAXV_Mg_oqc0STTq"
supabase = create_client(url, key)

# Load ML Model
@st.cache_resource
def load_model():
    try:
        return joblib.load('concrete_strength_model.pkl')
    except Exception as e:
        return None

model = load_model()

# 2. Manage Login State
if "user" not in st.session_state:
    st.session_state.user = None

# 3. Login Screen (Centered and Professional)
if st.session_state.user is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🏗️ Concrete Strength Monitor</h1>", unsafe_allow_html=True)
        st.markdown("<h4 style='text-align: center; color: gray;'>IoT Curing & Predictive Analytics</h4>", unsafe_allow_html=True)
        st.write("---")
        
        email = st.text_input("Administrator Email")
        password = st.text_input("Password", type="password")
        
        if st.button("Secure Login", use_container_width=True):
            try:
                response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = response.user
                st.rerun()
            except Exception as e:
                st.error("Authentication failed. Please verify your credentials.")

# 4. Main Dashboard Application
else:
    # --- SIDEBAR UI ---
    with st.sidebar:
        st.markdown("### ⚙️ System Status")
        st.success("Database Connected")
        if model:
            st.success("ML Engine Online")
        else:
            st.warning("ML Engine Offline (Missing .pkl)")
            
        st.write("---")
        if st.button("Logout", use_container_width=True):
            st.session_state.user = None
            st.rerun()

    # --- MAIN CONTENT AREA ---
    st.title("Live Concrete Curing Dashboard")
    
    tab1, tab2, tab3 = st.tabs(["🔴 Live Sensor Stream", "📂 Offline CSV Analytics", "🧠 ML Prediction Engine"])
    
    def display_dashboard(df):
        if set(['age_h', 'slab_temp', 'strength_mpa']).issubset(df.columns):
            latest_temp = df['slab_temp'].iloc[-1]
            latest_strength = df['strength_mpa'].iloc[-1]
            max_strength = df['strength_mpa'].max()
            
            st.markdown("### 📊 Key Performance Indicators")
            m1, m2, m3 = st.columns(3)
            m1.metric(label="Current Slab Temperature", value=f"{latest_temp:.1f} °C")
            m2.metric(label="Latest Estimated Strength", value=f"{latest_strength:.1f} MPa")
            m3.metric(label="Peak Strength Recorded", value=f"{max_strength:.1f} MPa")
            
            st.write("---")
            
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.markdown("**Temperature Profile over Time**")
                st.line_chart(df, x="age_h", y="slab_temp", color="#ff4b4b")
            with col_chart2:
                st.markdown("**Strength Development Profile**")
                st.line_chart(df, x="age_h", y="strength_mpa", color="#0068c9")
            
            st.write("---")
            st.markdown("### 🚦 Framework Removal Status")
            
            if latest_strength < 15:
                st.error(f"🔴 **CRITICAL ALERT:** Current strength is {latest_strength:.1f} MPa. **DO NOT** remove framework.")
            elif 15 <= latest_strength < 20:
                st.warning(f"🟡 **CAUTION:** Current strength is {latest_strength:.1f} MPa. Curing is progressing normally.")
            else:
                st.success(f"🟢 **SAFE TO PROCEED:** Target achieved at {latest_strength:.1f} MPa. Framework can be safely removed.")
        else:
            st.warning("⚠️ Core columns ('age_h', 'slab_temp', 'strength_mpa') missing. Automated logic disabled.")
            
        st.write("---")
        with st.expander("🛠️ Interactive Custom Graph Builder", expanded=False):
            st.markdown("Select any data columns from your dataset to generate custom visualizations:")
            col_x, col_y = st.columns(2)
            with col_x:
                x_axis = st.selectbox("Select X-Axis", df.columns, index=0)
            with col_y:
                y_axis = st.selectbox("Select Y-Axis", df.columns, index=min(1, len(df.columns)-1))
            
            if x_axis and y_axis:
                st.line_chart(df, x=x_axis, y=y_axis)
        
        st.markdown("### 📋 Sensor Data Log")
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Export Data Log as CSV",
            data=csv,
            file_name='concrete_sensor_log.csv',
            mime='text/csv',
        )

    # --- TAB 1: Live Supabase Data ---
    with tab1:
        st.write("Fetching real-time telemetry from the database...")
        try:
            response = supabase.table("strength_view").select("*").order("ts").execute()
            if response.data:
                live_df = pd.DataFrame(response.data)
                display_dashboard(live_df)
            else:
                st.info("Awaiting sensor data. No records found in the database.")
        except Exception as e:
            st.error(f"Database connection error: {e}")

    # --- TAB 2: CSV Upload ---
    with tab2:
        st.write("Upload historical sensor logs to test the analytics engine offline.")
        uploaded_file = st.file_uploader("Upload CSV Dataset", type="csv")
        
        if uploaded_file is not None:
            try:
                csv_df = pd.read_csv(uploaded_file)
                st.success("Dataset loaded successfully.")
                display_dashboard(csv_df)
            except Exception as e:
                st.error(f"Error parsing file: {e}")

    # --- TAB 3: ML PREDICTION TOOL ---
    with tab3:
        st.markdown("### 🧠 Predictive Strength Modeling")
        st.write("Manually enter curing conditions to run the machine learning algorithm.")
        
        st.write("---")
        col_ml1, col_ml2 = st.columns(2)
        with col_ml1:
            input_age = st.number_input("Age of Concrete (Hours)", min_value=0.0, value=24.0, step=0.5)
        with col_ml2:
            input_temp = st.number_input("Slab Temperature (°C)", min_value=-10.0, max_value=60.0, value=25.0, step=0.5)
        
        st.write("")
        if st.button("Run Prediction Model", type="primary"):
            if model:
                input_data = pd.DataFrame([[input_age, input_temp]], columns=['age_h', 'slab_temp'])
                prediction = model.predict(input_data)[0]
                
                st.markdown(f"### **Predicted Strength:** {prediction:.2f} MPa")
                
                if prediction < 15:
                    st.error("🔴 **DO NOT** remove framework.")
                elif 15 <= prediction < 20:
                    st.warning("🟡 Curing is progressing.")
                else:
                    st.success("🟢 **SAFE** to remove framework.")
            else:
                st.error("Machine Learning model is offline. Please ensure 'concrete_strength_model.pkl' is uploaded to GitHub.")
