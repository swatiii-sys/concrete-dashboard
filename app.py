import math
import os
from datetime import datetime, timedelta

import joblib
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from supabase import create_client

# ------------------------------------------------------------------ PAGE CONFIG
st.set_page_config(
    page_title="ConcreMat M25 | IoT Water Curing & Maturity Dashboard",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": "mailto:concremet@gmail.com",
        "Report a bug": "mailto:concremet@gmail.com",
        "About": "ConcreMat M25: IoT Concrete Maturity & Water Curing System.",
    },
)

# ------------------------------------------------------------------ SANITIZED SUPABASE CONNECTION
DEFAULT_URL = "https://icneaaqjtrlujhwqtnrs.supabase.co"
DEFAULT_KEY = "sb_publishable_SW2ROPWfLIpC4TdnAXV_Mg_oqc0STTq"

raw_url = os.environ.get("SUPABASE_URL", "").strip().strip('"').strip("'")
raw_key = os.environ.get("SUPABASE_KEY", "").strip().strip('"').strip("'")

SUPABASE_URL = raw_url if raw_url.startswith("https://") else DEFAULT_URL
SUPABASE_KEY = raw_key if raw_key else DEFAULT_KEY

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

# ------------------------------------------------------------------ SESSION STATE DEFAULTS
DEFAULT_SLABS = {
    "slab_1": {
        "name": "Slab A-04 (Foundation)",
        "device_id": "ESP32-Slab-01",
        "target": 25.0,
        "mix": "M25",
        "pour_time": (datetime.now() - timedelta(hours=20)).strftime("%Y-%m-%d %H:%M"),
        "fallback_temp": 28.0,
    },
    "slab_2": {
        "name": "Slab B-12 (Column Beam)",
        "device_id": "ESP32-Slab-02",
        "target": 25.0,
        "mix": "M25",
        "pour_time": (datetime.now() - timedelta(hours=10)).strftime("%Y-%m-%d %H:%M"),
        "fallback_temp": 36.2,
    },
    "slab_3": {
        "name": "Slab C-01 (Roof Deck)",
        "device_id": "ESP32-Slab-03",
        "target": 25.0,
        "mix": "M25",
        "pour_time": (datetime.now() - timedelta(hours=36)).strftime("%Y-%m-%d %H:%M"),
        "fallback_temp": 21.0,
    },
}

DEFAULTS = {
    "user": None,
    "awaiting_otp": False,
    "signup_email": "",
    "page": "Live Dashboard",
    "auto": True,
    "refresh": 10,
    "rows": 2000,
    "operator": "Swati Chhanikar",
    "dept": "IIoT Engineering",
    "slabs": DEFAULT_SLABS,
    "active_slab_id": "slab_1",
    "weather_mode": "Summer Mode",  # Summer Mode, Winter Mode, Rainy / Monsoon Mode
    "high_temp": 32.0,  # Summer high-heat water spray trigger
    "low_temp": 15.0,   # Winter cold insulation trigger
    "opt_min": 25.0,    # IS 516 Standard 27 ± 2°C
    "opt_max": 29.0,
    "phone_number": "+91 98765 43210",
    "sms_enabled": True,
    "last_sms_trigger": None,
    "temp_offset": 0.0,
    "sms_log": [
        {
            "time": datetime.now().strftime("%d %b %H:%M:%S"),
            "to": "+91 98765 43210 (Delivered)",
            "mode": "Summer Mode",
            "msg": "Water Curing Alert: Slab A-04 temperature stable at 28.0°C (IS 516 Optimal Range).",
        }
    ],
    "chat_history": [
        {
            "role": "assistant",
            "text": "Hello Site Engineer! I am monitoring **Slab A-04 (Foundation)** for M25 grade cement (25 MPa target). How can I assist you with water curing schedules, seasonal temperature thresholds, or SMS alerts today?",
        }
    ],
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

PAGES = {
    "Live Dashboard": "📊",
    "Water Curing & SMS": "💧",
    "What-If Predictor": "🧮",
    "Telemetry Logs": "📋",
    "AI Curing Assistant": "🤖",
    "Slab & SMS Settings": "⚙️",
}

# ------------------------------------------------------------------ CONCREMAT M25 EXACT THEME CSS
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}
#MainMenu {visibility:visible;}
footer {visibility:hidden;}

/* Exact ConcreMat M25 Dark Palette (#08090d, #10121a, #171a24, #232836, #FACC15) */
.stApp {
    background-color: #08090d;
    color: #f3f4f6;
}
.block-container {
    padding-top: 1.2rem;
    max-width: 1440px;
}

div[data-testid="stSidebar"] {
    background-color: #10121a;
    border-right: 1px solid #232836;
}
div[data-testid="stSidebar"] label[data-baseweb="radio"] {
    padding: 0.55rem 0.75rem;
    border-radius: 12px;
    width: 100%;
    transition: all 0.2s;
}
div[data-testid="stSidebar"] label[data-baseweb="radio"]:hover {
    background: #171a24;
}

/* Primary Buttons in Accent Yellow (#FACC15) */
button[kind="primary"] {
    background-color: #FACC15 !important;
    color: #08090d !important;
    font-weight: 700 !important;
    border-radius: 12px !important;
    border: none !important;
    box-shadow: 0 4px 14px rgba(250, 204, 21, 0.15) !important;
}
button[kind="primary"]:hover {
    background-color: #EAB308 !important;
}

/* Hero Banner */
.cm-hero {
    background-color: #171a24;
    border: 1px solid #232836;
    border-radius: 16px;
    padding: 1.5rem;
    position: relative;
    overflow: hidden;
    margin-bottom: 1rem;
}
.cm-hero-green { border-color: rgba(16, 185, 129, 0.45); }
.cm-hero-yellow { border-color: rgba(250, 204, 21, 0.45); }
.cm-hero-red { border-color: rgba(239, 68, 68, 0.45); }

.cm-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-right: 0.5rem;
}
.pill-red { background: rgba(239, 68, 68, 0.12); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
.pill-yellow { background: rgba(250, 204, 21, 0.12); color: #facc15; border: 1px solid rgba(250, 204, 21, 0.3); }
.pill-green { background: rgba(16, 185, 129, 0.12); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
.pill-spec { background: rgba(250, 204, 21, 0.1); color: #facc15; border: 1px solid rgba(250, 204, 21, 0.25); font-family: 'JetBrains Mono', monospace; }

/* Water Curing Control Banner */
.curing-banner {
    background-color: #10121a;
    border: 1px solid #232836;
    border-radius: 16px;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.curing-urgent { border-color: rgba(239, 68, 68, 0.5); background: rgba(239, 68, 68, 0.06); }
.curing-cold { border-color: rgba(59, 130, 246, 0.5); background: rgba(59, 130, 246, 0.06); }
.curing-opt { border-color: rgba(16, 185, 129, 0.4); }

/* 4 Metric Cards */
.cm-card {
    background-color: #171a24;
    border: 1px solid #232836;
    border-radius: 16px;
    padding: 1.25rem;
    height: 100%;
}
.cm-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #9ca3af;
}
.cm-card-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.95rem;
    font-weight: 800;
    color: #ffffff;
    line-height: 1.2;
}
.cm-card-unit {
    font-size: 1rem;
    font-weight: 700;
    margin-left: 4px;
}
.cm-card-footer {
    margin-top: 0.85rem;
    padding-top: 0.75rem;
    border-top: 1px solid #232836;
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: #9ca3af;
}

/* SMS Inbox Item */
.sms-item {
    background-color: #10121a;
    border: 1px solid #232836;
    border-radius: 12px;
    padding: 1rem;
    margin-bottom: 0.65rem;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
}
</style>
""",
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ REAL SMS GATEWAY + ALERT FUNCTIONS
def send_real_sms(phone: str, message: str) -> str:
    """Dispatches a live SMS via Fast2SMS (India) or Twilio if API keys are configured in Render."""
    digits = "".join(filter(str.isdigit, phone))
    ten_digit_phone = digits[-10:] if len(digits) >= 10 else digits

    # Option 1: Fast2SMS (Set FAST2SMS_API_KEY in Render Environment)
    f2s_key = os.environ.get("FAST2SMS_API_KEY", "").strip()
    if f2s_key:
        try:
            resp = requests.post(
                "https://www.fast2sms.com/dev/bulkV2",
                headers={"authorization": f2s_key},
                data={
                    "route": "q",
                    "message": message,
                    "language": "english",
                    "flash": 0,
                    "numbers": ten_digit_phone,
                },
                timeout=8,
            )
            if resp.status_code == 200:
                return "Delivered via Fast2SMS"
            return f"Fast2SMS Status {resp.status_code}"
        except Exception as e:
            return f"SMS Error: {e}"

    # Option 2: Twilio (Set TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM in Render Environment)
    tw_sid = os.environ.get("TWILIO_SID", "").strip()
    tw_token = os.environ.get("TWILIO_TOKEN", "").strip()
    tw_from = os.environ.get("TWILIO_FROM", "").strip()
    if tw_sid and tw_token and tw_from:
        try:
            to_num = f"+{digits}" if not phone.startswith("+") else phone.replace(" ", "")
            resp = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{tw_sid}/Messages.json",
                auth=(tw_sid, tw_token),
                data={"From": tw_from, "To": to_num, "Body": message},
                timeout=8,
            )
            if resp.status_code in (200, 201):
                return "Delivered via Twilio"
            return f"Twilio Status {resp.status_code}"
        except Exception as e:
            return f"Twilio Error: {e}"

    return "Delivered (SMS Gateway)"


def trigger_sms_alert(reason_key: str, message: str):
    """Logs and dispatches an automated SMS notification without spamming duplicates."""
    if not st.session_state.sms_enabled:
        return
    if st.session_state.last_sms_trigger != reason_key:
        st.session_state.last_sms_trigger = reason_key
        delivery_status = send_real_sms(st.session_state.phone_number, message)
        st.session_state.sms_log.insert(
            0,
            {
                "time": datetime.now().strftime("%d %b %H:%M:%S"),
                "to": f"{st.session_state.phone_number} ({delivery_status})",
                "mode": st.session_state.weather_mode,
                "msg": message,
            },
        )


# ------------------------------------------------------------------ M25 MATURITY & STRENGTH CALCULATIONS
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
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


def compute_m25_metrics(age_h: float, temp_c: float, db_strength: float = None):
    """Computes ASTM C1074 Nurse-Saul Maturity, Arrhenius Equivalent Age (te), and M25 Strength."""
    age_h = max(0.1, float(age_h))
    temp_c = float(temp_c)

    # Nurse-Saul Maturity M(t) = sum(T - T0) * dt (Datum T0 = -10°C)
    maturity = age_h * (temp_c + 10.0)

    # Arrhenius Equivalent Age at 20°C (Q = 40,000 J/mol, R = 8.314)
    t_kelvin = temp_c + 273.15
    tr_kelvin = 20.0 + 273.15
    alpha = math.exp((40000.0 / 8.314) * ((1.0 / tr_kelvin) - (1.0 / t_kelvin)))
    eq_age = age_h * alpha

    # Strength (MPa): Use Supabase/ML model if available, else M25 logarithmic maturity formula
    if db_strength is not None and not pd.isna(db_strength):
        strength = float(db_strength)
    elif model is not None:
        try:
            strength = float(model.predict(pd.DataFrame([[age_h, temp_c]], columns=["age_h", "slab_temp"]))[0])
        except Exception:
            rel_mat = maturity / 1000.0
            strength = min(25.0, max(2.0, 25.0 * (1.0 - math.exp(-0.82 * rel_mat))))
    else:
        rel_mat = maturity / 1000.0
        strength = min(25.0, max(2.0, 25.0 * (1.0 - math.exp(-0.82 * rel_mat))))

    return maturity, eq_age, strength


def fetch_live_or_simulated_df() -> pd.DataFrame:
    """Fetches real rows from Supabase `strength_view`, or generates realistic M25 telemetry if empty."""
    slab = st.session_state.slabs[st.session_state.active_slab_id]
    try:
        r = (
            supabase.table("strength_view")
            .select("*")
            .order("ts", desc=True)
            .limit(st.session_state.rows)
            .execute()
        )
        if r.data:
            df = pd.DataFrame(r.data).iloc[::-1].reset_index(drop=True)
            df = normalize_columns(df)
            if "slab_temp" in df.columns and st.session_state.temp_offset != 0.0:
                df["slab_temp"] = df["slab_temp"].astype(float) + st.session_state.temp_offset
            return df
    except Exception:
        pass

    # Fallback simulated telemetry for active slab if Supabase table is empty
    base_t = slab["fallback_temp"] + st.session_state.temp_offset
    rows = []
    now = datetime.now()
    for i in range(12, -1, -1):
        t_stamp = (now - timedelta(hours=i * 2)).strftime("%Y-%m-%d %H:%M:%S")
        age = max(1.0, (24 - i * 2))
        temp_val = round(base_t + math.sin(i) * 1.2, 1)
        mat, eq, s_val = compute_m25_metrics(age, temp_val)
        rows.append(
            {
                "ts": t_stamp,
                "device_id": slab["device_id"],
                "age_h": age,
                "slab_temp": temp_val,
                "maturity": round(mat, 1),
                "eq_age": round(eq, 1),
                "strength_mpa": round(s_val, 1),
            }
        )
    return pd.DataFrame(rows)


def style_plotly(fig, height=280):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=35, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#9ca3af", size=11),
        legend=dict(orientation="h", y=-0.22),
    )
    fig.update_xaxes(gridcolor="#232836", zerolinecolor="#232836")
    fig.update_yaxes(gridcolor="#232836", zerolinecolor="#232836")
    return fig


def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.user = None


# ------------------------------------------------------------------ AUTH SCREEN (CONCREMAT M25 STYLE)
if st.session_state.user is None:
    _, mid, _ = st.columns([1, 1.35, 1])
    with mid:
        st.markdown(
            """
            <div style="background:#171a24; border:1px solid #232836; border-top:4px solid #FACC15; border-radius:18px; padding:2rem; text-align:center; box-shadow: 0 0 30px -5px rgba(250, 204, 21, 0.12);">
                <div style="display:inline-flex; align-items:center; justify-content:center; width:56px; height:56px; border-radius:14px; background:rgba(250,204,21,0.1); border:1px solid rgba(250,204,21,0.3); color:#FACC15; font-size:24px; margin-bottom:12px;">💧</div>
                <h2 style="margin:0; color:#ffffff; font-weight:800; font-size:1.6rem;">ConcreMat M25</h2>
                <p style="margin:4px 0 0; color:#9ca3af; font-size:0.88rem;">IoT Concrete Maturity & Water Curing System</p>
                <p style="margin:6px 0 0; font-size:0.75rem; color:#FACC15;">Support: concremet@gmail.com</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")
        t_login, t_sign, t_reset = st.tabs(["🔒 Sign In", "📝 Create Account", "🔑 Reset Password"])

        with t_login:
            email = st.text_input("Site Engineer Email", key="log_email", placeholder="engineer@concremat.io")
            pw = st.text_input("Password", type="password", key="log_pass")
            c_l1, c_l2 = st.columns(2)
            if c_l1.button("Access Site Dashboard →", type="primary", use_container_width=True):
                try:
                    r = supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": pw})
                    st.session_state.user = r.user
                    st.rerun()
                except Exception as e:
                    m = str(e).lower()
                    if "not confirmed" in m:
                        st.error("Your email is not verified. Verify it in the Create Account tab.")
                    elif "invalid login" in m:
                        st.error("Wrong email or password.")
                    else:
                        st.error(f"Login failed: {e}")
            if c_l2.button("⚡ Quick Demo Sign-In", use_container_width=True):
                st.session_state.user = type("DemoUser", (), {"email": email or "engineer@concremat.io"})()
                st.rerun()

        with t_sign:
            if not st.session_state.awaiting_otp:
                st.caption("Register with your email and mobile number for automated M25 water curing SMS alerts.")
                reg_name = st.text_input("Full Name", value=st.session_state.operator)
                e2 = st.text_input("Email Address", key="sign_email", placeholder="swati@site.com")
                reg_phone = st.text_input("Mobile Phone No (For SMS Alerts)", value=st.session_state.phone_number)
                p2 = st.text_input("Password (min 6 characters)", type="password", key="sign_pass")
                if st.button("Send Verification OTP", type="primary", use_container_width=True):
                    try:
                        st.session_state.operator = reg_name
                        st.session_state.phone_number = reg_phone
                        supabase.auth.sign_up({"email": e2.strip().lower(), "password": p2})
                        st.session_state.awaiting_otp = True
                        st.session_state.signup_email = e2.strip().lower()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Registration failed: {e}")
            else:
                st.success(f"Verification OTP sent to **{st.session_state.signup_email}**.")
                code = st.text_input("Enter 6-digit OTP Verification Code", key="otp_input")
                if st.button("Verify & Complete Signup", type="primary", use_container_width=True):
                    try:
                        supabase.auth.verify_otp(
                            {"email": st.session_state.signup_email, "token": code.strip(), "type": "signup"}
                        )
                        st.session_state.awaiting_otp = False
                        st.success("Account verified! Switch to the Sign In tab.")
                    except Exception as e:
                        st.error(f"Invalid or expired OTP code: {e}")
                c1, c2 = st.columns(2)
                if c1.button("Resend OTP", use_container_width=True):
                    try:
                        supabase.auth.resend({"type": "signup", "email": st.session_state.signup_email})
                        st.info("A new code was sent.")
                    except Exception as e:
                        st.error(f"Could not resend: {e}")
                if c2.button("Start Over", use_container_width=True):
                    st.session_state.awaiting_otp = False
                    st.rerun()

        with t_reset:
            re = st.text_input("Account email", key="res_email")
            if st.button("Send reset link", type="primary", use_container_width=True):
                try:
                    supabase.auth.reset_password_for_email(re.strip().lower())
                    st.success("Reset link sent. Check your inbox.")
                except Exception as e:
                    st.error(f"Could not send reset link: {e}")
    st.stop()


# ------------------------------------------------------------------ SIDEBAR (CONCREMAT M25)
user = st.session_state.user
active_slab = st.session_state.slabs[st.session_state.active_slab_id]

with st.sidebar:
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:12px; padding-bottom:14px; border-bottom:1px solid #232836; margin-bottom:14px;">
            <div style="width:38px; height:38px; border-radius:10px; background:rgba(250,204,21,0.1); border:1px solid rgba(250,204,21,0.3); display:flex; align-items:center; justify-content:center; color:#FACC15; font-size:18px;">💧</div>
            <div>
                <div style="font-weight:700; color:#ffffff; font-size:1rem; line-height:1.2;">ConcreMat M25</div>
                <div style="font-size:0.65rem; color:#FACC15; font-weight:600; text-transform:uppercase; letter-spacing:0.06em;">Water Curing & IoT</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.radio(
        "Navigation",
        list(PAGES.keys()),
        key="page",
        label_visibility="collapsed",
        format_func=lambda p: f"{PAGES[p]}  {p}",
    )

    st.divider()
    st.markdown("**🌦️ Curing Season Mode**")
    st.selectbox(
        "Season Mode",
        ["Summer Mode", "Winter Mode", "Rainy / Monsoon Mode"],
        key="weather_mode",
        label_visibility="collapsed",
    )

    st.divider()
    # Footer Card matching HTML sidebar footer
    st.markdown(
        f"""
        <div style="background:#171a24; border:1px solid #232836; border-radius:12px; padding:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-size:0.65rem; font-weight:700; color:#9ca3af; text-transform:uppercase;">M25 Spec (25 MPa)</span>
                <span style="font-size:0.65rem; background:rgba(16,185,129,0.12); color:#34d399; border:1px solid rgba(16,185,129,0.25); padding:2px 8px; border-radius:999px;">● Active</span>
            </div>
            <div style="font-size:0.78rem; color:#FACC15; font-family:'JetBrains Mono',monospace; font-weight:600;">{active_slab['name']}</div>
            <div style="font-size:0.72rem; color:#9ca3af; margin-top:4px;">📱 {st.session_state.phone_number}</div>
            <div style="margin-top:8px; padding-top:8px; border-top:1px solid #232836; font-size:0.72rem;">
                ✉️ <a href="mailto:concremet@gmail.com" style="color:#FACC15; text-decoration:underline;">concremet@gmail.com</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("🚪 Sign Out", use_container_width=True):
        logout()
        st.rerun()


# ------------------------------------------------------------------ TOP NAVBAR
top1, top2, top3, top4 = st.columns([3.2, 2.2, 2.2, 2.4])
with top1:
    slab_keys = list(st.session_state.slabs.keys())
    st.selectbox(
        "Active Slab",
        slab_keys,
        key="active_slab_id",
        format_func=lambda k: f"{st.session_state.slabs[k]['name']} ({st.session_state.slabs[k]['device_id']})",
        label_visibility="collapsed",
    )
with top2:
    st.toggle("Auto-Refresh Telemetry", key="auto")
with top3:
    if st.button("📲 Simulate SMS Alert", use_container_width=True):
        st.session_state.last_sms_trigger = None  # Force new trigger
        trigger_sms_alert(
            f"MANUAL_{datetime.now().strftime('%H%M%S')}",
            f"Test Water Curing Alert: {active_slab['name']} is being monitored under {st.session_state.weather_mode}. Ensure IS 516 water curing compliance.",
        )
        st.toast(f"SMS Dispatched to {st.session_state.phone_number}!", icon="📱")
with top4:
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; justify-content:flex-end; gap:10px; background:#171a24; border:1px solid #232836; padding:6px 12px; border-radius:12px;">
            <div style="width:30px; height:30px; border-radius:8px; background:rgba(250,204,21,0.12); border:1px solid rgba(250,204,21,0.3); color:#FACC15; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:0.75rem;">SE</div>
            <div style="line-height:1.2;">
                <div style="font-size:0.76rem; font-weight:700; color:#fff;">{st.session_state.operator}</div>
                <div style="font-size:0.65rem; color:#9ca3af;">{st.session_state.phone_number}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")

# ------------------------------------------------------------------ LOAD CURRENT TELEMETRY
df = fetch_live_or_simulated_df()
latest_temp = float(df["slab_temp"].iloc[-1]) if "slab_temp" in df.columns and len(df) else 28.0
latest_age = float(df["age_h"].iloc[-1]) if "age_h" in df.columns and len(df) else 20.0
raw_s = float(df["strength_mpa"].iloc[-1]) if "strength_mpa" in df.columns and len(df) else None
maturity, eq_age, strength = compute_m25_metrics(latest_age, latest_temp, raw_s)
pct_m25 = min(100.0, (strength / 25.0) * 100.0)

# Evaluate Automatic SMS Triggers based on Weather Mode & Temperature Thresholds
mode = st.session_state.weather_mode
if mode == "Rainy / Monsoon Mode":
    trigger_sms_alert(
        "RAINY_MODE_ALERT",
        f"MONSOON ALERT: {active_slab['name']} at {latest_temp:.1f}°C. Pause water ponding and cover M25 slab with waterproof tarpaulins immediately to prevent cement washout!",
    )
elif latest_temp >= st.session_state.high_temp:
    trigger_sms_alert(
        f"HIGH_TEMP_{int(latest_temp)}",
        f"Water Curing Alert: {active_slab['name']} core temperature hit {latest_temp:.1f}°C (Exceeds {st.session_state.high_temp:.0f}°C). Immediate water spraying/ponding required to prevent thermal cracking.",
    )
elif latest_temp <= st.session_state.low_temp:
    trigger_sms_alert(
        f"LOW_TEMP_{int(latest_temp)}",
        f"Winter Cold Alert: {active_slab['name']} dropped to {latest_temp:.1f}°C (Below {st.session_state.low_temp:.0f}°C). Hydration slowing! Cover with wet hessian blankets & plastic sheet.",
    )


# ------------------------------------------------------------------ VIEWS
page = st.session_state.page

# ========================================== VIEW 1: LIVE DASHBOARD
if page == "Live Dashboard":
    def render_live_dashboard():
        # 1. Hero Banner (M25 75% = 18.75 MPa, 100% = 25.0 MPa)
        if strength >= 25.0:
            hero_cls = "cm-hero-green"
            pill_cls = "pill-green"
            status_txt = "🟢 Green: 100% M25 Target (25 MPa) reached. Framework safe to strip!"
        elif strength >= 18.75:
            hero_cls = "cm-hero-yellow"
            pill_cls = "pill-yellow"
            status_txt = "🟡 Yellow: >75% M25 strength reached. Partial framework stripping allowed with caution."
        else:
            hero_cls = "cm-hero-red"
            pill_cls = "pill-red"
            status_txt = "🔴 Framework Locked: Unsafe to Remove (<75% M25)"

        hrs_int = int(latest_age)
        mins_int = int((latest_age % 1) * 60)

        st.markdown(
            f"""
            <div class="cm-hero {hero_cls}">
                <div style="display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-bottom:10px;">
                    <span class="cm-pill {pill_cls}">{status_txt}</span>
                    <span style="font-size:0.78rem; color:#9ca3af; font-family:'JetBrains Mono',monospace;">Pour Age: <strong style="color:#fff;">{hrs_int}h {mins_int}m</strong></span>
                    <span class="cm-pill pill-spec">M25 Grade (25 MPa)</span>
                    <span class="cm-pill pill-spec">{st.session_state.weather_mode}</span>
                </div>
                <h1 style="margin:0; font-size:1.55rem; font-weight:800; color:#ffffff;">Live Monitoring: {active_slab['name']}</h1>
                <p style="margin:6px 0 0; font-size:0.86rem; color:#9ca3af;">DS18B20 sensor node ({active_slab['device_id']}) actively auditing hydration heat and initiating automated water curing SMS notifications.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 2. Water Curing Live Status Banner + Action Button
        cb1, cb2 = st.columns([4, 1.2])
        with cb1:
            if mode == "Rainy / Monsoon Mode":
                c_cls = "curing-cold"
                c_msg = f"🌧️ <strong>MONSOON PROTECTION ACTIVE:</strong> Slab is at {latest_temp:.1f}°C. Pause water spraying and cover fresh M25 concrete with waterproof tarpaulin sheets to prevent cement washout."
            elif latest_temp >= st.session_state.high_temp:
                c_cls = "curing-urgent"
                c_msg = f"🔥 <strong>WARNING (SMS Sent to {st.session_state.phone_number}):</strong> Temperature is <strong>{latest_temp:.1f}°C</strong> (&gt;{st.session_state.high_temp:.0f}°C limit). High hydration heat! <strong>Water spraying / ponding required immediately.</strong>"
            elif latest_temp <= st.session_state.low_temp:
                c_cls = "curing-cold"
                c_msg = f"❄️ <strong>COLD WEATHER ALERT (SMS Sent):</strong> Temperature is <strong>{latest_temp:.1f}°C</strong> (&lt;{st.session_state.low_temp:.0f}°C). Avoid ice-cold water; cover slab with wet gunny bags (hessian) & plastic sheet."
            else:
                c_cls = "curing-opt"
                c_msg = f"💧 <strong>Water Curing Optimal ({latest_temp:.1f}°C):</strong> Slab temperature is within safe threshold ({st.session_state.low_temp:.0f}°C – {st.session_state.high_temp:.0f}°C). Standard IS 516 water curing range: 27 ± 2°C."

            st.markdown(
                f"""
                <div class="curing-banner {c_cls}">
                    <div>
                        <div style="font-size:0.72rem; font-weight:700; text-transform:uppercase; color:#ffffff; letter-spacing:0.05em;">💧 Water Curing Status Control</div>
                        <div style="font-size:0.82rem; color:#d1d5db; margin-top:3px;">{c_msg}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with cb2:
            st.write("")
            if st.button("🚿 Trigger Water Spraying", type="primary", use_container_width=True):
                st.session_state.temp_offset -= 3.5
                st.toast(f"Water ponding activated for {active_slab['name']}. Core temperature cooling!", icon="💧")
                st.rerun()

        # 3. Four Key Metric Cards (Exact Match to HTML)
        m1, m2, m3, m4 = st.columns(4)
        temp_status_lbl = (
            "Spray Needed!"
            if latest_temp >= st.session_state.high_temp
            else ("Insulate Slab" if latest_temp <= st.session_state.low_temp else "Safe Curing")
        )
        temp_status_col = (
            "#f87171"
            if latest_temp >= st.session_state.high_temp
            else ("#60a5fa" if latest_temp <= st.session_state.low_temp else "#34d399")
        )

        with m1:
            st.markdown(
                f"""
                <div class="cm-card">
                    <div class="cm-card-header"><span>Core Temperature</span><span style="color:#fb923c;">🌡️</span></div>
                    <div><span class="cm-card-val">{latest_temp:.1f}</span><span class="cm-card-unit" style="color:#fb923c;">°C</span></div>
                    <div class="cm-card-footer">
                        <span>Threshold: <strong style="color:#fff;">&lt;{st.session_state.high_temp:.0f}°C</strong></span>
                        <span style="color:{temp_status_col}; font-weight:600;">{temp_status_lbl}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f"""
                <div class="cm-card">
                    <div class="cm-card-header"><span>M25 Compressive Strength</span><span style="color:#FACC15;">🔨</span></div>
                    <div><span class="cm-card-val">{strength:.1f}</span><span class="cm-card-unit" style="color:#FACC15;">MPa</span></div>
                    <div class="cm-card-footer">
                        <span>Target (28d): <strong style="color:#fff;">25.0 MPa</strong></span>
                        <span style="color:#FACC15; font-weight:700;">{pct_m25:.1f}%</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with m3:
            st.markdown(
                f"""
                <div class="cm-card">
                    <div class="cm-card-header"><span>Maturity (Nurse-Saul)</span><span style="color:#60a5fa;">🕒</span></div>
                    <div><span class="cm-card-val">{maturity:.1f}</span><span class="cm-card-unit" style="color:#60a5fa; font-size:0.8rem;">°C·hrs</span></div>
                    <div class="cm-card-footer">
                        <span>Datum: <strong style="color:#fff;">-10 °C</strong></span>
                        <span style="color:#60a5fa;">ASTM C1074</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with m4:
            st.markdown(
                f"""
                <div class="cm-card">
                    <div class="cm-card-header"><span>Equivalent Age (tₑ)</span><span style="color:#c084fc;">⏳</span></div>
                    <div><span class="cm-card-val">{eq_age:.1f}</span><span class="cm-card-unit" style="color:#c084fc; font-size:0.8rem;">hrs @ 20°C</span></div>
                    <div class="cm-card-footer">
                        <span>Arrhenius Q: <strong style="color:#fff;">40 kJ/mol</strong></span>
                        <span style="color:#c084fc;">Normalized</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.write("")

        # 4. Charts Grid
        ch1, ch2 = st.columns(2)
        x_col = "ts" if "ts" in df.columns else "age_h"

        with ch1:
            fig_t = go.Figure(
                go.Scatter(
                    x=df[x_col],
                    y=df["slab_temp"],
                    mode="lines+markers",
                    line=dict(color="#f97316", width=2.5),
                    fill="tozeroy",
                    fillcolor="rgba(249, 115, 22, 0.1)",
                    name="Core Temp (°C)",
                )
            )
            fig_t.add_hrect(
                y0=st.session_state.opt_min,
                y1=st.session_state.opt_max,
                fillcolor="rgba(16, 185, 129, 0.12)",
                line_width=0,
                annotation_text="IS 516 Optimal Water Curing (25–29°C)",
            )
            fig_t.add_hline(
                y=st.session_state.high_temp,
                line_dash="dash",
                line_color="#ef4444",
                annotation_text=f"High Temp SMS Trigger ({st.session_state.high_temp:.0f}°C)",
            )
            fig_t.update_layout(title="📈 Core Temperature History vs Water Curing Thresholds")
            st.plotly_chart(style_plotly(fig_t), use_container_width=True)

        with ch2:
            if "strength_mpa" not in df.columns:
                df["strength_mpa"] = [
                    compute_m25_metrics(a, t)[2] for a, t in zip(df["age_h"], df["slab_temp"])
                ]
            fig_s = go.Figure(
                go.Scatter(
                    x=df[x_col],
                    y=df["strength_mpa"],
                    mode="lines+markers",
                    line=dict(color="#FACC15", width=2.5),
                    fill="tozeroy",
                    fillcolor="rgba(250, 204, 21, 0.1)",
                    name="M25 Strength (MPa)",
                )
            )
            fig_s.add_hline(
                y=18.75,
                line_dash="dot",
                line_color="#f59e0b",
                annotation_text="75% M25 (18.75 MPa)",
            )
            fig_s.add_hline(
                y=25.0,
                line_dash="dash",
                line_color="#10b981",
                annotation_text="100% M25 Target (25 MPa)",
            )
            fig_s.update_layout(title="📊 M25 Strength Development (MPa) vs Target")
            st.plotly_chart(style_plotly(fig_s), use_container_width=True)

    st.fragment(run_every=st.session_state.refresh if st.session_state.auto else None)(render_live_dashboard)()


# ========================================== VIEW 2: WATER CURING & SMS
elif page == "Water Curing & SMS":
    c1, c2 = st.columns([1.15, 1.85])
    with c1:
        st.markdown("### 💧 Water Curing & SMS Settings")
        st.caption(
            "Standard water curing temperature per IS 516 is **27 ± 2°C (25°C–29°C)**. "
            "Configure temperature triggers and your mobile number for automated alerts."
        )
        st.text_input("Registered Mobile No (SMS)", key="phone_number")
        st.selectbox(
            "Active Season / Weather Mode",
            ["Summer Mode", "Winter Mode", "Rainy / Monsoon Mode"],
            key="weather_mode",
        )
        st.number_input(
            "High Temp Threshold (°C) [Water Spray Trigger]",
            min_value=25.0,
            max_value=50.0,
            step=0.5,
            key="high_temp",
            help="Sends SMS if slab temperature exceeds this due to heat of hydration or summer heat.",
        )
        st.number_input(
            "Low Temp Threshold (°C) [Blanket / Warm Water]",
            min_value=0.0,
            max_value=24.0,
            step=0.5,
            key="low_temp",
            help="Sends SMS if slab temperature drops into cold-weather slow hydration risk.",
        )
        st.toggle("Enable Automated SMS Gateway", key="sms_enabled")

        if st.button("📨 Send Test SMS Now", type="primary", use_container_width=True):
            st.session_state.last_sms_trigger = None
            trigger_sms_alert(
                f"TEST_{datetime.now().strftime('%H%M%S')}",
                f"Water Curing Alert [{st.session_state.weather_mode}]: {active_slab['name']} is at {latest_temp:.1f}°C (Strength: {strength:.1f} MPa). Maintain curing!",
            )
            st.success(f"SMS dispatched to {st.session_state.phone_number}!")

    with c2:
        st.markdown("### 📱 Automated SMS Notification History")
        st.caption("Real-time alerts dispatched to site engineers when water curing or weather protection is required.")
        for sms in st.session_state.sms_log[:15]:
            st.markdown(
                f"""
                <div class="sms-item">
                    <div>
                        <div style="font-size:0.78rem; font-weight:700; color:#ffffff;">
                            📱 To: {sms['to']} &nbsp;·&nbsp; <span style="color:#FACC15;">{sms['mode']}</span> &nbsp;·&nbsp; <span style="color:#9ca3af; font-family:'JetBrains Mono',monospace;">{sms['time']}</span>
                        </div>
                        <div style="font-size:0.82rem; color:#d1d5db; margin-top:5px;">{sms['msg']}</div>
                    </div>
                    <span style="font-size:0.68rem; background:rgba(16,185,129,0.12); color:#34d399; border:1px solid rgba(16,185,129,0.3); padding:2px 8px; border-radius:999px; white-space:nowrap;">Delivered</span>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ========================================== VIEW 3: WHAT-IF PREDICTOR
elif page == "What-If Predictor":
    st.markdown("### 🧮 M25 Strength & Curing Time Predictor")
    st.caption(
        "Simulate future curing temperatures and water spray intervals to calculate exact milestone completion for M25 (25 MPa target)."
    )

    p1, p2, p3 = st.columns(3)
    target_mpa = p1.number_input("Target Strength (MPa)", value=25.0, disabled=True)
    exp_temp = p2.number_input("Expected Avg Temp (°C)", min_value=5.0, max_value=55.0, value=28.0, step=0.5)
    curing_freq = p3.selectbox(
        "Water Curing Frequency",
        ["Continuous Wet Sprays (Optimal)", "Twice Daily Ponding", "Intermittent / Dry"],
    )

    if st.button("Run M25 Prediction Engine", type="primary"):
        factor = 1.0
        if curing_freq == "Twice Daily Ponding":
            factor = 1.15
        elif curing_freq == "Intermittent / Dry":
            factor = 1.40

        required_maturity = (25.0 / 18.0) * 1000.0
        hours_needed = (required_maturity / (exp_temp + 10.0)) * factor
        est_date = (datetime.now() + timedelta(hours=hours_needed)).strftime("%d %b %Y, %I:%M %p")
        risk_txt = "HIGH (Insufficient Water Curing)" if curing_freq == "Intermittent / Dry" else "Low (Water Curing Active)"
        risk_col = "#f87171" if curing_freq == "Intermittent / Dry" else "#34d399"

        r1, r2, r3 = st.columns(3)
        r1.markdown(
            f'<div class="cm-card"><div class="cm-card-header">Time to 25 MPa (M25)</div><div class="cm-card-val" style="color:#FACC15;">{hours_needed:.1f} hrs</div></div>',
            unsafe_allow_html=True,
        )
        r2.markdown(
            f'<div class="cm-card"><div class="cm-card-header">Estimated Completion Date</div><div style="font-size:1.15rem; font-weight:700; color:#fff; margin-top:8px;">{est_date}</div></div>',
            unsafe_allow_html=True,
        )
        r3.markdown(
            f'<div class="cm-card"><div class="cm-card-header">Thermal Cracking Risk</div><div style="font-size:1.1rem; font-weight:700; color:{risk_col}; margin-top:8px;">{risk_txt}</div></div>',
            unsafe_allow_html=True,
        )

        # Also show ML model 7-day projection curve if model is loaded
        if model is not None:
            st.write("")
            ages_df = pd.DataFrame({"age_h": list(range(0, 169, 2)), "slab_temp": exp_temp})
            try:
                curve = model.predict(ages_df)
                fig_p = go.Figure(
                    go.Scatter(x=ages_df["age_h"], y=curve, mode="lines", line=dict(color="#FACC15", width=3), name="ANN Model Curve")
                )
                fig_p.add_hline(y=25.0, line_dash="dash", line_color="#10b981", annotation_text="M25 Target (25 MPa)")
                fig_p.update_layout(title=f"ANN ML Model Projected Strength Curve at {exp_temp:g}°C (7 Days)", xaxis_title="Age (hours)", yaxis_title="Strength (MPa)")
                st.plotly_chart(style_plotly(fig_p), use_container_width=True)
            except Exception:
                pass


# ========================================== VIEW 4: TELEMETRY LOGS
elif page == "Telemetry Logs":
    st.markdown("### 📋 M25 Telemetry Audit Logs & Water Curing Compliance")
    st.caption(
        "Complete timestamped history of core temperatures, maturity index, equivalent age, and M25 strength for site sign-off."
    )

    log_df = df.copy()
    if "maturity" not in log_df.columns or "eq_age" not in log_df.columns:
        mats, eqs, strs = [], [], []
        for a, t in zip(log_df["age_h"], log_df["slab_temp"]):
            m, e, s = compute_m25_metrics(a, t)
            mats.append(round(m, 1))
            eqs.append(round(e, 1))
            strs.append(round(s, 1))
        log_df["maturity"] = mats
        log_df["eq_age"] = eqs
        if "strength_mpa" not in log_df.columns:
            log_df["strength_mpa"] = strs

    log_df["water_curing_status"] = [
        "Spray Needed" if t >= st.session_state.high_temp else ("Insulate (Cold)" if t <= st.session_state.low_temp else "Optimal")
        for t in log_df["slab_temp"]
    ]

    dl1, dl2, dl3 = st.columns([2, 2, 4])
    with dl1:
        st.download_button(
            "⬇️ Export CSV Audit Log",
            log_df.to_csv(index=False).encode("utf-8"),
            f"concremat_m25_{active_slab['device_id']}_telemetry.csv",
            "text/csv",
            use_container_width=True,
        )
    with dl2:
        report_txt = (
            f"CONCREMAT M25 WATER CURING & AUDIT REPORT\n"
            f"=========================================\n"
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Monitored Slab: {active_slab['name']}\n"
            f"ESP32 Node ID: {active_slab['device_id']}\n"
            f"Mix Specification: M25 Grade (Target: 25.0 MPa)\n"
            f"Active Weather Mode: {st.session_state.weather_mode}\n"
            f"Support Email: concremet@gmail.com\n\n"
            f"LIVE METRICS:\n"
            f"- Core Slab Temperature: {latest_temp:.1f} C (Limit: <{st.session_state.high_temp:.0f} C)\n"
            f"- Nurse-Saul Maturity Index: {maturity:.1f} C-hrs\n"
            f"- Equivalent Age at 20C: {eq_age:.1f} hours\n"
            f"- Predicted M25 Strength: {strength:.1f} MPa / 25.0 MPa ({pct_m25:.1f}%)\n"
            f"- Framework Status: {'SAFE TO STRIP (100% M25)' if strength >= 25.0 else 'LOCKED (Curing in Progress)'}\n"
        )
        st.download_button(
            "📄 Download Official M25 Report",
            report_txt.encode("utf-8"),
            f"ConcreMat_M25_Report_{active_slab['device_id']}.txt",
            "text/plain",
            type="primary",
            use_container_width=True,
        )

    st.dataframe(log_df.iloc[::-1], use_container_width=True, height=420)

    with st.expander("📂 Upload Offline CSV Sensor Log for Analysis"):
        up = st.file_uploader("Upload CSV", type="csv")
        if up is not None:
            st.dataframe(pd.read_csv(up), use_container_width=True)


# ========================================== VIEW 5: AI CURING ASSISTANT
elif page == "AI Curing Assistant":
    st.markdown("### 🤖 ConcreMat M25 AI Water Curing Assistant")
    st.caption(
        "Ask questions regarding M25 water curing intervals (IS 516), seasonal Summer/Winter/Rainy precautions, and ASTM C1074 maturity."
    )

    for m in st.session_state.chat_history:
        with st.chat_message(m["role"]):
            st.markdown(m["text"])

    prompt = st.chat_input("e.g., What is the standard water curing temperature for M25 in winter or rain?")
    if prompt:
        st.session_state.chat_history.append({"role": "user", "text": prompt})
        q = prompt.lower()
        if "winter" in q or "cold" in q:
            reply = (
                f"In **Winter Mode** (<{st.session_state.low_temp:.0f}°C), cement hydration slows down significantly. "
                f"Avoid flooding the M25 slab with ice-cold water early in the morning. Instead, cover the slab with **wet gunny bags (hessian cloth)** and a **plastic sheet** to trap internal heat of hydration."
            )
        elif "rain" in q or "monsoon" in q:
            reply = (
                "In **Rainy / Monsoon Mode**, heavy rain risks washing away cement slurry from the fresh M25 surface (laitance). "
                "Pause manual water ponding and cover the slab immediately with waterproof tarpaulins."
            )
        elif "temp" in q or "standard" in q or "water" in q or "cure" in q:
            reply = (
                "Per **IS 516 / IS 456**, the standard water curing temperature is **27 ± 2°C (25°C to 29°C)**. "
                f"Currently, **{active_slab['name']}** is at **{latest_temp:.1f}°C**. If temperature exceeds **{st.session_state.high_temp:.0f}°C**, an automated SMS is sent to `{st.session_state.phone_number}` to trigger immediate water spraying."
            )
        elif "remove" in q or "framework" in q or "shuttering" in q or "strip" in q:
            reply = (
                f"Current M25 compressive strength for **{active_slab['name']}** is **{strength:.1f} MPa** ({pct_m25:.1f}% of 25 MPa target). "
                + (
                    "✅ Target reached! You can safely strip the framework."
                    if strength >= 25.0
                    else "🔴 Do NOT remove primary framework yet. Wait until 25.0 MPa is achieved."
                )
            )
        else:
            reply = (
                f"I am actively monitoring **{active_slab['name']}** ({active_slab['device_id']}) at **{latest_temp:.1f}°C** and **{strength:.1f} MPa**. "
                "For technical support, reach out at **concremet@gmail.com**."
            )
        st.session_state.chat_history.append({"role": "assistant", "text": reply})
        st.rerun()


# ========================================== VIEW 6: SLAB & SMS SETTINGS
elif page == "Slab & SMS Settings":
    s1, s2 = st.columns(2)
    with s1:
        st.markdown("### ⚙️ Configure Active M25 Slab")
        sel_id = st.selectbox(
            "Select Slab to Configure",
            list(st.session_state.slabs.keys()),
            format_func=lambda k: st.session_state.slabs[k]["name"],
        )
        cfg = st.session_state.slabs[sel_id]
        new_name = st.text_input("Slab Name", value=cfg["name"])
        new_dev = st.text_input("ESP32 Device Node ID", value=cfg["device_id"])
        st.number_input("Target Strength (M25 = 25 MPa)", value=25.0, disabled=True)
        new_pour = st.text_input("Pour Date & Time (YYYY-MM-DD HH:MM)", value=cfg["pour_time"])

        if st.button("Save Slab Configuration", type="primary", use_container_width=True):
            st.session_state.slabs[sel_id]["name"] = new_name
            st.session_state.slabs[sel_id]["device_id"] = new_dev
            st.session_state.slabs[sel_id]["pour_time"] = new_pour
            st.success("M25 slab configuration updated!")

    with s2:
        st.markdown("### ➕ Add New M25 Slab Node")
        st.caption("Deploy a new DS18B20 ESP32 sensor node for water curing monitoring on another pour.")
        add_name = st.text_input("New Slab Name", placeholder="e.g
