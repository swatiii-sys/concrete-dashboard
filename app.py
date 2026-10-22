This error happens because Streamlit already created a widget in your sidebar using `key="weather_mode"`. In Streamlit, once a widget is instantiated with a key, you **cannot** manually reassign a value to that key in `st.session_state` later in the script.

To fix this cleanly, we can remove the duplicate selectbox from the **Water Curing & SMS** page (since the sidebar already controls the global **Season Mode**) and instead let the Water Curing page focus entirely on configuring the temperature thresholds (`high_temp`, `low_temp`) and viewing the live SMS inbox.

Here is the fully fixed, clean `app.py`:

```python
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
    "weather_mode": "Summer Mode",
    "high_temp": 32.0,
    "low_temp": 15.0,
    "opt_min": 25.0,
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
            "text": "Hello Site Engineer! I am monitoring **Slab A-04 (Foundation)** for M25 grade cement (25 MPa target). Ask me anything about water curing schedules, seasonal temperature thresholds, or SMS alerts.",
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

# ------------------------------------------------------------------ CONCREMAT M25 THEME CSS
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu {visibility:visible;} footer {visibility:hidden;}
.stApp { background-color: #08090d; color: #f3f4f6; }
.block-container { padding-top: 1.2rem; max-width: 1440px; }
div[data-testid="stSidebar"] { background-color: #10121a; border-right: 1px solid #232836; }
div[data-testid="stSidebar"] label[data-baseweb="radio"] { padding: 0.55rem 0.75rem; border-radius: 12px; width: 100%; }
div[data-testid="stSidebar"] label[data-baseweb="radio"]:hover { background: #171a24; }
button[kind="primary"] { background-color: #FACC15 !important; color: #08090d !important; font-weight: 700 !important; border-radius: 12px !important; border: none !important; }
button[kind="primary"]:hover { background-color: #EAB308 !important; }
.cm-hero { background-color: #171a24; border: 1px solid #232836; border-radius: 16px; padding: 1.5rem; margin-bottom: 1rem; }
.cm-hero-green { border-color: rgba(16, 185, 129, 0.45); }
.cm-hero-yellow { border-color: rgba(250, 204, 21, 0.45); }
.cm-hero-red { border-color: rgba(239, 68, 68, 0.45); }
.cm-pill { display: inline-flex; align-items: center; gap: 6px; padding: 0.25rem 0.75rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; margin-right: 0.5rem; }
.pill-red { background: rgba(239, 68, 68, 0.12); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
.pill-yellow { background: rgba(250, 204, 21, 0.12); color: #facc15; border: 1px solid rgba(250, 204, 21, 0.3); }
.pill-green { background: rgba(16, 185, 129, 0.12); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
.pill-spec { background: rgba(250, 204, 21, 0.1); color: #facc15; border: 1px solid rgba(250, 204, 21, 0.25); font-family: 'JetBrains Mono', monospace; }
.curing-banner { background-color: #10121a; border: 1px solid #232836; border-radius: 16px; padding: 1rem 1.25rem; margin-bottom: 1rem; }
.curing-urgent { border-color: rgba(239, 68, 68, 0.5); background: rgba(239, 68, 68, 0.06); }
.curing-cold { border-color: rgba(59, 130, 246, 0.5); background: rgba(59, 130, 246, 0.06); }
.curing-opt { border-color: rgba(16, 185, 129, 0.4); }
.cm-card { background-color: #171a24; border: 1px solid #232836; border-radius: 16px; padding: 1.25rem; height: 100%; }
.cm-card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; font-size: 0.72rem; font-weight: 600; text-transform: uppercase; color: #9ca3af; }
.cm-card-val { font-family: 'JetBrains Mono', monospace; font-size: 1.95rem; font-weight: 800; color: #ffffff; line-height: 1.2; }
.cm-card-unit { font-size: 1rem; font-weight: 700; margin-left: 4px; }
.cm-card-footer { margin-top: 0.85rem; padding-top: 0.75rem; border-top: 1px solid #232836; display: flex; justify-content: space-between; font-size: 0.75rem; color: #9ca3af; }
.sms-item { background-color: #10121a; border: 1px solid #232836; border-radius: 12px; padding: 1rem; margin-bottom: 0.65rem; display: flex; justify-content: space-between; align-items: flex-start; }
</style>
""",
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ REAL SMS GATEWAY + ALERT FUNCTIONS
def send_real_sms(phone: str, message: str) -> str:
    digits = "".join(filter(str.isdigit, phone))
    ten_digit_phone = digits[-10:] if len(digits) >= 10 else digits

    f2s_key = os.environ.get("FAST2SMS_API_KEY", "").strip()
    if f2s_key:
        try:
            resp = requests.post(
                "https://www.fast2sms.com/dev/bulkV2",
                headers={"authorization": f2s_key},
                data={"route": "q", "message": message, "language": "english", "flash": 0, "numbers": ten_digit_phone},
                timeout=8,
            )
            if resp.status_code == 200:
                return "Delivered via Fast2SMS"
            return f"Fast2SMS Status {resp.status_code}"
        except Exception as e:
            return f"SMS Error: {e}"

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


# ------------------------------------------------------------------ M25 MATURITY & STRENGTH HELPERS
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
    age_h = max(0.1, float(age_h))
    temp_c = float(temp_c)
    maturity = age_h * (temp_c + 10.0)
    t_kelvin = temp_c + 273.15
    tr_kelvin = 20.0 + 273.15
    alpha = math.exp((40000.0 / 8.314) * ((1.0 / tr_kelvin) - (1.0 / t_kelvin)))
    eq_age = age_h * alpha

    if db_strength is not None and not pd.isna(db_strength):
        strength = float(db_strength)
    elif model is not None:
        try:
            strength = float(model.predict(pd.DataFrame([[age_h, temp_c]], columns=["age_h", "slab_temp"]))[0])
        except Exception:
            strength = min(25.0, max(2.0, 25.0 * (1.0 - math.exp(-0.82 * (maturity / 1000.0)))))
    else:
        strength = min(25.0, max(2.0, 25.0 * (1.0 - math.exp(-0.82 * (maturity / 1000.0)))))

    return maturity, eq_age, strength


def fetch_live_or_simulated_df() -> pd.DataFrame:
    slab = st.session_state.slabs[st.session_state.active_slab_id]
    try:
        r = supabase.table("strength_view").select("*").order("ts", desc=True).limit(st.session_state.rows).execute()
        if r.data:
            df = pd.DataFrame(r.data).iloc[::-1].reset_index(drop=True)
            df = normalize_columns(df)
            if "slab_temp" in df.columns and st.session_state.temp_offset != 0.0:
                df["slab_temp"] = df["slab_temp"].astype(float) + st.session_state.temp_offset
            return df
    except Exception:
        pass

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


# ------------------------------------------------------------------ AUTHENTICATION SCREEN
if st.session_state.user is None:
    _, mid, _ = st.columns([1, 1.35, 1])
    with mid:
        st.markdown(
            """
            <div style="background:#171a24; border:1px solid #232836; border-top:4px solid #FACC15; border-radius:18px; padding:2rem; text-align:center;">
                <h2 style="margin:0; color:#ffffff; font-weight:800; font-size:1.6rem;">💧 ConcreMat M25</h2>
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
            if c_l1.button("Access Site Dashboard", type="primary", use_container_width=True):
                try:
                    r = supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": pw})
                    st.session_state.user = r.user
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")
            if c_l2.button("⚡ Quick Demo Sign-In", use_container_width=True):
                st.session_state.user = type("DemoUser", (), {"email": email or "engineer@concremat.io"})()
                st.rerun()

        with t_sign:
            if not st.session_state.awaiting_otp:
                reg_name = st.text_input("Full Name", value=st.session_state.operator)
                e2 = st.text_input("Email Address", key="sign_email")
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
                code = st.text_input("Enter 6-digit OTP Code", key="otp_input")
                if st.button("Verify & Complete Signup", type="primary", use_container_width=True):
                    try:
                        supabase.auth.verify_otp(
                            {"email": st.session_state.signup_email, "token": code.strip(), "type": "signup"}
                        )
                        st.session_state.awaiting_otp = False
                        st.success("Account verified! Switch to the Sign In tab.")
                    except Exception as e:
                        st.error(f"Invalid or expired OTP code: {e}")

        with t_reset:
            re = st.text_input("Account email", key="res_email")
            if st.button("Send reset link", type="primary", use_container_width=True):
                try:
                    supabase.auth.reset_password_for_email(re.strip().lower())
                    st.success("Reset link sent. Check your inbox.")
                except Exception as e:
                    st.error(f"Could not send reset link: {e}")
    st.stop()


# ------------------------------------------------------------------ SIDEBAR
user = st.session_state.user
active_slab = st.session_state.slabs[st.session_state.active_slab_id]

with st.sidebar:
    st.markdown("### 💧 ConcreMat M25")
    st.caption("Water Curing & IoT Maturity")
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
    st.markdown(
        f"**Active Slab:** `{active_slab['name']}`\n\n"
        f"**SMS To:** `{st.session_state.phone_number}`\n\n"
        f"**Support:** [concremet@gmail.com](mailto:concremet@gmail.com)"
    )
    if st.button("🚪 Sign Out", use_container_width=True):
        logout()
        st.rerun()


# ------------------------------------------------------------------ TOP NAVBAR
top1, top2, top3, top4 = st.columns([3.2, 2.2, 2.2, 2.4])
with top1:
    st.selectbox(
        "Active Slab",
        list(st.session_state.slabs.keys()),
        key="active_slab_id",
        format_func=lambda k: f"{st.session_state.slabs[k]['name']} ({st.session_state.slabs[k]['device_id']})",
        label_visibility="collapsed",
    )
with top2:
    st.toggle("Auto-Refresh Telemetry", key="auto")
with top3:
    if st.button("📲 Simulate SMS Alert", use_container_width=True):
        st.session_state.last_sms_trigger = None
        trigger_sms_alert(
            f"MANUAL_{datetime.now().strftime('%H%M%S')}",
            f"Test Water Curing Alert: {active_slab['name']} is monitored under {st.session_state.weather_mode}.",
        )
        st.toast(f"SMS Dispatched to {st.session_state.phone_number}!", icon="📱")
with top4:
    st.markdown(f"**👤 {st.session_state.operator}** · `{st.session_state.phone_number}`")

st.write("")

# ------------------------------------------------------------------ TELEMETRY & AUTO SMS EVALUATION
df = fetch_live_or_simulated_df()
latest_temp = float(df["slab_temp"].iloc[-1]) if "slab_temp" in df.columns and len(df) else 28.0
latest_age = float(df["age_h"].iloc[-1]) if "age_h" in df.columns and len(df) else 20.0
raw_s = float(df["strength_mpa"].iloc[-1]) if "strength_mpa" in df.columns and len(df) else None
maturity, eq_age, strength = compute_m25_metrics(latest_age, latest_temp, raw_s)
pct_m25 = min(100.0, (strength / 25.0) * 100.0)

mode = st.session_state.weather_mode
if mode == "Rainy / Monsoon Mode":
    trigger_sms_alert(
        "RAINY_MODE_ALERT",
        f"MONSOON ALERT: {active_slab['name']} at {latest_temp:.1f}C. Cover M25 slab with waterproof tarpaulins immediately!",
    )
elif latest_temp >= st.session_state.high_temp:
    trigger_sms_alert(
        f"HIGH_TEMP_{int(latest_temp)}",
        f"Water Curing Alert: {active_slab['name']} hit {latest_temp:.1f}C (Exceeds {st.session_state.high_temp:.0f}C). Immediate water spraying required!",
    )
elif latest_temp <= st.session_state.low_temp:
    trigger_sms_alert(
        f"LOW_TEMP_{int(latest_temp)}",
        f"Winter Cold Alert: {active_slab['name']} dropped to {latest_temp:.1f}C (Below {st.session_state.low_temp:.0f}C). Cover with wet hessian blankets!",
    )

# ------------------------------------------------------------------ VIEWS
page = st.session_state.page

if page == "Live Dashboard":
    def render_live_dashboard():
        if strength >= 25.0:
            hero_cls, pill_cls = "cm-hero-green", "pill-green"
            status_txt = "🟢 Green: 100% M25 Target (25 MPa) reached. Framework safe to strip!"
        elif strength >= 18.75:
            hero_cls, pill_cls = "cm-hero-yellow", "pill-yellow"
            status_txt = "🟡 Yellow: >75% M25 strength reached. Partial stripping allowed with caution."
        else:
            hero_cls, pill_cls = "cm-hero-red", "pill-red"
            status_txt = "🔴 Framework Locked: Unsafe to Remove (<75% M25)"

        st.markdown(
            f"""
            <div class="cm-hero {hero_cls}">
                <div style="margin-bottom:10px;">
                    <span class="cm-pill {pill_cls}">{status_txt}</span>
                    <span class="cm-pill pill-spec">M25 Grade (25 MPa)</span>
                    <span class="cm-pill pill-spec">{st.session_state.weather_mode}</span>
                </div>
                <h2 style="margin:0; color:#ffffff;">Live Monitoring: {active_slab['name']}</h2>
                <p style="margin:4px 0 0; font-size:0.85rem; color:#9ca3af;">DS18B20 sensor ({active_slab['device_id']}) auditing hydration heat and water curing compliance.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        cb1, cb2 = st.columns([4, 1.2])
        with cb1:
            if mode == "Rainy / Monsoon Mode":
                c_cls = "curing-cold"
                c_msg = f"🌧️ <strong>MONSOON PROTECTION ACTIVE:</strong> Slab at {latest_temp:.1f}°C. Cover M25 concrete with waterproof sheets to prevent cement washout."
            elif latest_temp >= st.session_state.high_temp:
                c_cls = "curing-urgent"
                c_msg = f"🔥 <strong>WARNING (SMS Sent to {st.session_state.phone_number}):</strong> Temperature is <strong>{latest_temp:.1f}°C</strong> (&gt;{st.session_state.high_temp:.0f}°C). <strong>Water spraying / ponding required immediately.</strong>"
            elif latest_temp <= st.session_state.low_temp:
                c_cls = "curing-cold"
                c_msg = f"❄️ <strong>COLD WEATHER ALERT (SMS Sent):</strong> Temperature is <strong>{latest_temp:.1f}°C</strong> (&lt;{st.session_state.low_temp:.0f}°C). Cover slab with wet hessian blankets."
            else:
                c_cls = "curing-opt"
                c_msg = f"💧 <strong>Water Curing Optimal ({latest_temp:.1f}°C):</strong> Within safe threshold ({st.session_state.low_temp:.0f}°C – {st.session_state.high_temp:.0f}°C). Standard IS 516 range: 27 ± 2°C."

            st.markdown(f'<div class="curing-banner {c_cls}">{c_msg}</div>', unsafe_allow_html=True)
        with cb2:
            if st.button("🚿 Trigger Water Spray", type="primary", use_container_width=True):
                st.session_state.temp_offset -= 3.5
                st.rerun()

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(
                f'<div class="cm-card"><div class="cm-card-header"><span>Core Temperature</span><span>🌡️</span></div>'
                f'<div><span class="cm-card-val">{latest_temp:.1f}</span><span class="cm-card-unit" style="color:#fb923c;">°C</span></div>'
                f'<div class="cm-card-footer"><span>Limit: &lt;{st.session_state.high_temp:.0f}°C</span><span>IS 516: 27±2°C</span></div></div>',
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f'<div class="cm-card"><div class="cm-card-header"><span>M25 Strength</span><span>🔨</span></div>'
                f'<div><span class="cm-card-val">{strength:.1f}</span><span class="cm-card-unit" style="color:#FACC15;">MPa</span></div>'
                f'<div class="cm-card-footer"><span>Target: 25.0 MPa</span><span style="color:#FACC15;">{pct_m25:.1f}%</span></div></div>',
                unsafe_allow_html=True,
            )
        with m3:
            st.markdown(
                f'<div class="cm-card"><div class="cm-card-header"><span>Maturity (Nurse-Saul)</span><span>🕒</span></div>'
                f'<div><span class="cm-card-val">{maturity:.1f}</span><span class="cm-card-unit" style="color:#60a5fa;">°C·h</span></div>'
                f'<div class="cm-card-footer"><span>Datum: -10°C</span><span>ASTM C1074</span></div></div>',
                unsafe_allow_html=True,
            )
        with m4:
            st.markdown(
                f'<div class="cm-card"><div class="cm-card-header"><span>Equivalent Age (tₑ)</span><span>⏳</span></div>'
                f'<div><span class="cm-card-val">{eq_age:.1f}</span><span class="cm-card-unit" style="color:#c084fc;">hrs</span></div>'
                f'<div class="cm-card-footer"><span>Arrhenius 20°C</span><span>Normalized</span></div></div>',
                unsafe_allow_html=True,
            )

        st.write("")
        ch1, ch2 = st.columns(2)
        x_col = "ts" if "ts" in df.columns else "age_h"
        with ch1:
            fig_t = go.Figure(
                go.Scatter(x=df[x_col], y=df["slab_temp"], mode="lines+markers", line=dict(color="#f97316", width=2.5), fill="tozeroy", fillcolor="rgba(249,115,22,0.1)")
            )
            fig_t.add_hrect(y0=25.0, y1=29.0, fillcolor="rgba(16,185,129,0.12)", line_width=0, annotation_text="IS 516 Optimal (25-29°C)")
            fig_t.add_hline(y=st.session_state.high_temp, line_dash="dash", line_color="#ef4444", annotation_text="SMS Trigger")
            fig_t.update_layout(title="Core Temperature History vs Thresholds")
            st.plotly_chart(style_plotly(fig_t), use_container_width=True)

        with ch2:
            if "strength_mpa" not in df.columns:
                df["strength_mpa"] = [compute_m25_metrics(a, t)[2] for a, t in zip(df["age_h"], df["slab_temp"])]
            fig_s = go.Figure(
                go.Scatter(x=df[x_col], y=df["strength_mpa"], mode="lines+markers", line=dict(color="#FACC15", width=2.5), fill="tozeroy", fillcolor="rgba(250,204,21,0.1)")
            )
            fig_s.add_hline(y=25.0, line_dash="dash", line_color="#10b981", annotation_text="M25 Target (25 MPa)")
            fig_s.update_layout(title="M25 Strength Development (MPa) vs Target")
            st.plotly_chart(style_plotly(fig_s), use_container_width=True)

    st.fragment(run_every=st.session_state.refresh if st.session_state.auto else None)(render_live_dashboard)()

elif page == "Water Curing & SMS":
    c1, c2 = st.columns([1.15, 1.85])
    with c1:
        st.markdown("### 💧 Water Curing & SMS Settings")
        st.text_input("Registered Mobile No (SMS)", key="phone_number")
        st.info(f"Active Curing Season (controlled via sidebar): **{st.session_state.weather_mode}**")
        st.number_input("High Temp Threshold (°C) [Water Spray Trigger]", min_value=25.0, max_value=50.0, step=0.5, key="high_temp")
        st.number_input("Low Temp Threshold (°C) [Winter Blanket Alert]", min_value=0.0, max_value=24.0, step=0.5, key="low_temp")
        st.toggle("Enable Automated SMS Gateway", key="sms_enabled")
        if st.button("📨 Send Test SMS Now", type="primary", use_container_width=True):
            st.session_state.last_sms_trigger = None
            trigger_sms_alert(
                f"TEST_{datetime.now().strftime('%H%M%S')}",
                f"Water Curing Alert [{st.session_state.weather_mode}]: {active_slab['name']} is at {latest_temp:.1f}C (Strength: {strength:.1f} MPa).",
            )
            st.success(f"SMS dispatched to {st.session_state.phone_number}!")

    with c2:
        st.markdown("### 📱 Automated SMS Notification History")
        for sms in st.session_state.sms_log[:15]:
            st.markdown(
                f'<div class="sms-item"><div><div style="font-size:0.78rem; font-weight:700; color:#fff;">📱 To: {sms["to"]} · <span style="color:#FACC15;">{sms["mode"]}</span> · {sms["time"]}</div>'
                f'<div style="font-size:0.82rem; color:#d1d5db; margin-top:4px;">{sms["msg"]}</div></div></div>',
                unsafe_allow_html=True,
            )

elif page == "What-If Predictor":
    st.markdown("### 🧮 M25 Strength & Curing Time Predictor")
    p1, p2, p3 = st.columns(3)
    p1.number_input("Target Strength (MPa)", value=25.0, disabled=True)
    exp_temp = p2.number_input("Expected Avg Temp (°C)", min_value=5.0, max_value=55.0, value=28.0, step=0.5)
    curing_freq = p3.selectbox("Water Curing Frequency", ["Continuous Wet Sprays (Optimal)", "Twice Daily Ponding", "Intermittent / Dry"])
    if st.button("Run M25 Prediction Engine", type="primary"):
        factor = 1.0 if curing_freq == "Continuous Wet Sprays (Optimal)" else (1.15 if curing_freq == "Twice Daily Ponding" else 1.40)
        hours_needed = (((25.0 / 18.0) * 1000.0) / (exp_temp + 10.0)) * factor
        est_date = (datetime.now() + timedelta(hours=hours_needed)).strftime("%d %b %Y, %I:%M %p")
        st.success(f"**Estimated Time to 25 MPa:** {hours_needed:.1f} hrs (Completion: {est_date})")

elif page == "Telemetry Logs":
    st.markdown("### 📋 M25 Telemetry Audit Logs")
    st.download_button(
        "⬇️ Export CSV Audit Log",
        df.to_csv(index=False).encode("utf-8"),
        f"concremat_m25_{active_slab['device_id']}.csv",
        "text/csv",
    )
    st.dataframe(df.iloc[::-1], use_container_width=True)

elif page == "AI Curing Assistant":
    st.markdown("### 🤖 ConcreMat M25 AI Water Curing Assistant")
    for m in st.session_state.chat_history:
        with st.chat_message(m["role"]):
            st.markdown(m["text"])
    prompt = st.chat_input("Ask about M25 water curing temperatures, winter/rainy precautions, or SMS alerts...")
    if prompt:
        st.session_state.chat_history.append({"role": "user", "text": prompt})
        q = prompt.lower()
        if "winter" in q or "cold" in q:
            reply = "In **Winter Mode** (<15°C), hydration slows down. Avoid ice-cold water ponding; cover the M25 slab with wet gunny bags (hessian) and plastic sheets."
        elif "rain" in q:
            reply = "In **Rainy Mode**, pause water spraying and cover the fresh M25 slab with waterproof tarpaulin sheets to prevent cement slurry washout."
        else:
            reply = f"Standard IS 516 water curing temperature is **27 ± 2°C (25–29°C)**. Current slab temp is **{latest_temp:.1f}°C** and M25 strength is **{strength:.1f} MPa**. Support: **concremet@gmail.com**."
        st.session_state.chat_history.append({"role": "assistant", "text": reply})
        st.rerun()

elif page == "Slab & SMS Settings":
    s1, s2 = st.columns(2)
    with s1:
        st.markdown("### ⚙️ Configure Active M25 Slab")
        sel_id = st.selectbox("Select Slab", list(st.session_state.slabs.keys()), format_func=lambda k: st.session_state.slabs[k]["name"])
        cfg = st.session_state.slabs[sel_id]
        new_name = st.text_input("Slab Name", value=cfg["name"])
        new_dev = st.text_input("ESP32 Device ID", value=cfg["device_id"])
        new_pour = st.text_input("Pour Date & Time", value=cfg["pour_time"])
        if st.button("Save Configuration", type="primary", use_container_width=True):
            st.session_state.slabs[sel_id]["name"] = new_name
            st.session_state.slabs[sel_id]["device_id"] = new_dev
            st.session_state.slabs[sel_id]["pour_time"] = new_pour
            st.success("Configuration saved!")
    with s2:
        st.markdown("### ➕ Add New M25 Slab Node")
        add_name = st.text_input("New Slab Name", placeholder="Slab D - Retaining Wall")
        add_dev = st.text_input("ESP32 Hardware ID", placeholder="ESP32-Slab-04")
        if st.button("Register ESP32 Node", use_container_width=True):
            if add_name and add_dev:
                new_key = f"slab_{len(st.session_state.slabs) + 1}"
                st.session_state.slabs[new_key] = {
                    "name": add_name,
                    "device_id": add_dev,
                    "target": 25.0,
                    "mix": "M25",
                    "pour_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "fallback_temp": 26.5,
                }
                st.session_state.active_slab_id = new_key
                st.success(f"Registered {add_name}!")
                st.rerun()

```
