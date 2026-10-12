import os
import streamlit as st
from supabase import create_client
import pandas as pd
import joblib

# --- PAGE CONFIGURATION (must be the first Streamlit call) ---
st.set_page_config(
    page_title="Concrete Curing Analytics",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 1. Supabase connection -------------------------------------------------
# Best practice: set SUPABASE_URL and SUPABASE_KEY in Render > Environment.
# The defaults below are your existing values (publishable key only).
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://icneaaqjtrlujhwqtnrs.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_SW2ROPWfLIpC4TdnAXV_Mg_oqc0STTq")

# FIX: keep ONE client per browser session so the login session is not lost on rerun
if "supabase" not in st.session_state:
    st.session_state.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase = st.session_state.supabase


@st.cache_resource
def load_model():
    try:
        return joblib.load("ann_concrete_strength_model.pkl")
    except Exception:
        return None


model = load_model()

# 2. Login state -----------------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "awaiting_otp" not in st.session_state:
    st.session_state.awaiting_otp = False
    st.session_state.signup_email = ""


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Accept both dashboard names and the generated-dataset names."""
    mapping = {
        "elapsed_hours": "age_h",
        "concrete_avg_temp_C": "slab_temp",
        "strength_MPa": "strength_mpa",
        "created_at": "ts",
    }
    for old, new in mapping.items():
        if old in df.columns and new not in df.columns:
            df = df.rename(columns={old: new})
    return df


def chart_frame(df: pd.DataFrame, max_points: int = 5000) -> pd.DataFrame:
    """Down-sample very long logs (e.g. 30 s data) so charts stay fast."""
    if len(df) > max_points:
        step = len(df) // max_points + 1
        return df.iloc[::step]
    return df


# 3. Authentication screen -------------------------------------------------
if st.session_state.user is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🏗️ Concrete Strength Monitor</h1>", unsafe_allow_html=True)
        st.markdown("<h4 style='text-align: center; color: gray;'>IoT Curing & Predictive Analytics</h4>", unsafe_allow_html=True)
        st.write("---")

        tab_login, tab_signup, tab_reset = st.tabs(["🔒 Login", "📝 Create Account", "🔑 Reset Password"])

        # --- LOGIN ---
        with tab_login:
            email_login = st.text_input("Email", key="log_email")
            password_login = st.text_input("Password", type="password", key="log_pass")
            if st.button("Secure Login", use_container_width=True):
                try:
                    response = supabase.auth.sign_in_with_password(
                        {"email": email_login.strip().lower(), "password": password_login}
                    )
                    st.session_state.user = response.user
                    st.rerun()
                except Exception as e:
                    msg = str(e)
                    if "not confirmed" in msg.lower():
                        st.error("Your email is not verified yet. Verify it in the Create Account tab or check your inbox.")
                    elif "invalid login" in msg.lower():
                        st.error("Wrong email or password.")
                    else:
                        st.error(f"Login failed: {msg}")   # shows the real reason

        # --- SIGN UP WITH OTP ---
        with tab_signup:
            if not st.session_state.awaiting_otp:
                st.info("Register a new account. We will send an OTP to verify your email.")
                email_signup = st.text_input("New Email", key="sign_email")
                password_signup = st.text_input("Create Password (min 6 characters)", type="password", key="sign_pass")

                if st.button("Send OTP", use_container_width=True):
                    try:
                        supabase.auth.sign_up({"email": email_signup.strip().lower(), "password": password_signup})
                        st.session_state.awaiting_otp = True
                        st.session_state.signup_email = email_signup.strip().lower()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Registration failed: {e}")
            else:
                st.success(f"An OTP has been sent to **{st.session_state.signup_email}**.")
                otp_code = st.text_input("Enter the OTP code", key="otp_input")

                if st.button("Verify OTP & Create Account", use_container_width=True):
                    try:
                        supabase.auth.verify_otp(
                            {"email": st.session_state.signup_email, "token": otp_code.strip(), "type": "signup"}
                        )
                        # verify_otp signs the user in on this client, so sign out and ask for a normal login
                        try:
                            supabase.auth.sign_out()
                        except Exception:
                            pass
                        st.success("Account verified! Open the Login tab and sign in.")
                        st.session_state.awaiting_otp = False
                    except Exception as e:
                        st.error(f"Invalid or expired OTP: {e}")

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Resend OTP", use_container_width=True):
                        try:
                            supabase.auth.resend({"type": "signup", "email": st.session_state.signup_email})
                            st.info("A new OTP was sent.")
                        except Exception as e:
                            st.error(f"Could not resend: {e}")
                with c2:
                    # FIX: st.button has no 'variant' argument
                    if st.button("Start Over", type="secondary", use_container_width=True):
                        st.session_state.awaiting_otp = False
                        st.rerun()

        # --- RESET PASSWORD ---
        with tab_reset:
            st.info("Enter your registered email to receive a password reset link.")
            reset_email = st.text_input("Account Email", key="res_email")
            if st.button("Send Reset Link", use_container_width=True):
                try:
                    # FIX: correct method name
                    supabase.auth.reset_password_for_email(reset_email.strip().lower())
                    st.success("Reset link sent! Please check your inbox.")
                except Exception as e:
                    st.error(f"Failed to send reset request: {e}")

# 4. Main dashboard --------------------------------------------------------
else:
    with st.sidebar:
        st.markdown("### 👤 User Profile")
        user_email = st.session_state.user.email
        short_id = st.session_state.user.id[:8] + "..."
        st.info(f"**Operator:** Swati Chhanikar\n\n**Dept:** IIoT Engineering\n\n**Email:** {user_email}\n\n**Sys ID:** {short_id}")

        st.write("---")
        st.markdown("### ⚙️ System Status")
        st.success("Database Connected")
        if model:
            st.success("ML Engine Online")
        else:
            st.warning("ML Engine Offline (Missing or incompatible .pkl)")

        st.write("---")
        if st.button("Logout", use_container_width=True):
            try:
                supabase.auth.sign_out()
            except Exception:
                pass
            st.session_state.user = None
            st.rerun()

    st.title("Live Concrete Curing Dashboard")
    tab1, tab2, tab3 = st.tabs(["🔴 Live Sensor Stream", "📂 Offline CSV Analytics", "🧠 ML Prediction Engine"])

    def display_dashboard(df, key_prefix):
        df = normalize_columns(df)
        plot_df = chart_frame(df)

        if {"age_h", "slab_temp", "strength_mpa"}.issubset(df.columns):
            latest_temp = df["slab_temp"].iloc[-1]
            latest_strength = df["strength_mpa"].iloc[-1]
            max_strength = df["strength_mpa"].max()

            st.markdown("### 📊 Key Performance Indicators")
            m1, m2, m3 = st.columns(3)
            m1.metric("Current Slab Temperature", f"{latest_temp:.1f} °C")
            m2.metric("Latest Estimated Strength", f"{latest_strength:.1f} MPa")
            m3.metric("Peak Strength Recorded", f"{max_strength:.1f} MPa")

            st.write("---")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Temperature Profile over Time**")
                st.line_chart(plot_df, x="age_h", y="slab_temp", color="#ff4b4b")
            with c2:
                st.markdown("**Strength Development Profile**")
                st.line_chart(plot_df, x="age_h", y="strength_mpa", color="#0068c9")

            st.write("---")
            st.markdown("### 🚦 Framework Removal Status")
            if latest_strength < 15:
                st.error(f"🔴 **CRITICAL ALERT:** Current strength is {latest_strength:.1f} MPa. **DO NOT** remove framework.")
            elif latest_strength < 20:
                st.warning(f"🟡 **CAUTION:** Current strength is {latest_strength:.1f} MPa. Curing is progressing normally.")
            else:
                st.success(f"🟢 **SAFE TO PROCEED:** Target achieved at {latest_strength:.1f} MPa. Framework can be safely removed.")
        else:
            st.warning("⚠️ Core columns ('age_h', 'slab_temp', 'strength_mpa') missing. Automated logic disabled.")

        st.write("---")
        with st.expander("🛠️ Interactive Custom Graph Builder", expanded=False):
            st.markdown("Select any data columns to generate custom visualizations:")
            cx, cy = st.columns(2)
            with cx:
                x_axis = st.selectbox("Select X-Axis", df.columns, index=0, key=f"{key_prefix}_x")
            with cy:
                y_axis = st.selectbox("Select Y-Axis", df.columns, index=min(1, len(df.columns) - 1), key=f"{key_prefix}_y")
            if x_axis and y_axis:
                st.line_chart(plot_df, x=x_axis, y=y_axis)

        st.markdown("### 📋 Sensor Data Log")
        st.dataframe(df.tail(2000), use_container_width=True)
        st.caption(f"Showing last {min(len(df), 2000)} of {len(df)} rows. The export below contains all rows.")

        st.download_button(
            "⬇️ Export Data Log as CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="concrete_sensor_log.csv",
            mime="text/csv",
            key=f"{key_prefix}_dl",
        )

    # --- TAB 1: live data ---
    with tab1:
        st.write("Fetching real-time telemetry from the database...")
        try:
            response = supabase.table("strength_view").select("*").order("ts").execute()
            if response.data:
                display_dashboard(pd.DataFrame(response.data), "live")
            else:
                st.info("Awaiting sensor data. No records found (or row-level security is blocking access).")
        except Exception as e:
            st.error(f"Database connection error: {e}")

    # --- TAB 2: CSV upload ---
    with tab2:
        st.write("Upload historical sensor logs to test the analytics engine offline.")
        uploaded_file = st.file_uploader("Upload CSV Dataset", type="csv")
        if uploaded_file is not None:
            try:
                csv_df = pd.read_csv(uploaded_file)
                st.success("Dataset loaded successfully.")
                display_dashboard(csv_df, "csv")
            except Exception as e:
                st.error(f"Error parsing file: {e}")

    # --- TAB 3: ML prediction ---
    with tab3:
        st.markdown("### 🧠 Predictive Strength Modeling")
        st.write("Manually enter curing conditions to run the machine learning algorithm.")
        st.write("---")
        m1, m2 = st.columns(2)
        with m1:
            input_age = st.number_input("Age of Concrete (Hours)", min_value=0.0, value=24.0, step=0.5)
        with m2:
            input_temp = st.number_input("Slab Temperature (°C)", min_value=-10.0, max_value=60.0, value=25.0, step=0.5)

        st.write("")
        if st.button("Run Prediction Model", type="primary"):
            if model:
                try:
                    X = pd.DataFrame([[input_age, input_temp]], columns=["age_h", "slab_temp"])
                    prediction = model.predict(X)[0]
                    st.markdown(f"### **Predicted Strength:** {prediction:.2f} MPa")
                    if prediction < 15:
                        st.error("🔴 **DO NOT** remove framework.")
                    elif prediction < 20:
                        st.warning("🟡 Curing is progressing.")
                    else:
                        st.success("🟢 **SAFE** to remove framework.")
                except Exception as e:
                    st.error(f"Model Execution Error: {e}. Ensure your model was trained on 'age_h' and 'slab_temp'.")
            else:
                st.error("Machine Learning model is offline. Upload 'ann_concrete_strength_model.pkl' next to app.py.")
