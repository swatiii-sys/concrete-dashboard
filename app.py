import os
from datetime import datetime

import joblib
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from supabase import create_client

# ------------------------------------------------------------------ PAGE CONFIG
st.set_page_config(
    page_title="CureSense M25 | Concrete Curing Analytics",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": "mailto:concremet@gmail.com",
        "Report a bug": "mailto:concremet@gmail.com",
        "About": "CureSense M25: IoT concrete curing, seasonal water curing & ML strength prediction.",
    },
)

# ------------------------------------------------------------------ SUPABASE CONNECTION
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
DEFAULTS = {
    "user": None,
    "awaiting_otp": False,
    "signup_email": "",
    "page": "Live dashboard",
    "auto": True,
    "refresh": 10,
    "rows": 2000,
    "caution": 15.0,
    "safe": 25.0,  # Calibrated for M25 Grade (25 MPa Target)
    "operator": "Swati Chhanikar",
    "dept": "IIoT Engineering",
    "concrete_grade": "M25 (25 MPa Target)",
    "weather_mode": "Summer Mode",  # Summer Mode, Winter Mode, Rainy / Monsoon Mode
    "curing_opt_min": 25.0,  # IS 516 Standard 27 ± 2°C
    "curing_opt_max": 29.0,
    "summer_max_temp": 32.0,
    "winter_min_temp": 15.0,
    "phone_number": "+91 98765 43210",
    "sms_enabled": True,
    "sms_log": [
        {
            "time": datetime.now().strftime("%d %b %H:%M"),
            "to": "+91 98765 43210",
            "mode": "System Init",
            "msg": "CureSense M25 SMS Gateway active. Monitoring slab temperature for IS 516 water curing.",
        }
    ],
    "last_sms_trigger": None,
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

PAGES = {
    "Live dashboard": "📡",
    "Water curing & SMS": "💧",
    "CSV analytics": "📂",
    "Strength predictor": "🧠",
    "Settings": "⚙️",
    "Help & about": "💡",
}

# ------------------------------------------------------------------ DARK WARM-BLACK ("FILKO") CSS
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
#MainMenu {visibility:visible;} footer {visibility:hidden;}

/* Dark Warm-Black Base */
.stApp {
    background-color: #0e0d0c;
    color: #f4f4f0;
}
.block-container { padding-top: 1.4rem; max-width: 1420px; }

/* Filko Warm-Black Hero with Amber/Yellow Accent */
.hero {
    background: linear-gradient(120deg, #181614 0%, #211d18 60%, #2e2415 100%);
    border: 1px solid rgba(245, 158, 11, 0.28);
    border-left: 6px solid #f59e0b;
    border-radius: 18px;
    padding: 1.35rem 1.6rem;
    color: #f4f7f6;
    box-shadow: 0 10px 28px rgba(0,0,0,0.45);
}
.hero h2 { margin:0; font-weight:700; letter-spacing:-.01em; color:#ffffff; }
.hero p { margin:.35rem 0 0; opacity:.85; font-size:.92rem; color:#d6d3cd; }

.pill {
    display:inline-block;
    padding:.18rem .68rem;
    border-radius:999px;
    font-size:.75rem;
    font-weight:600;
    background:rgba(245, 158, 11, 0.16);
    color:#fbbf24;
    border:1px solid rgba(245, 158, 11, 0.35);
    margin-right:.45rem;
}
.live-dot {
    display:inline-block; width:9px; height:9px; border-radius:50%; background:#10b981;
    margin-right:6px; box-shadow:0 0 0 0 rgba(16,185,129,.7); animation:pulse 1.8s infinite;
}
@keyframes pulse { 70% { box-shadow:0 0 0 9px rgba(16,185,129,0);} 100% {box-shadow:0 0 0 0 rgba(16,185,129,0);} }

/* KPI Cards */
.kpi {
    border:1px solid #282522;
    border-left:5px solid var(--c, #f59e0b);
    border-radius:14px;
    padding:1rem 1.15rem;
    background:#161513;
    box-shadow: 0 4px 14px rgba(0,0,0,0.3);
}
.kpi .l { font-size:.82rem; color:#a8a29e; font-weight:500; }
.kpi .v { font-size:1.85rem; font-weight:700; line-height:1.25; color:#ffffff; margin-top:2px; }
.kpi .s { font-size:.76rem; color:#78716c; margin-top:2px; }

/* Status & Curing Banners */
.status { border-radius:14px; padding:1rem 1.25rem; font-weight:500; border:1px solid; margin-bottom:0.6rem; }
.s-red { background:rgba(239,68,68,.12); border-color:#ef4444; color:#fecaca; }
.s-amber { background:rgba(245,158,11,.14); border-color:#f59e0b; color:#fde68a; }
.s-green { background:rgba(16,185,129,.13); border-color:#10b981; color:#a7f3d0; }
.s-blue { background:rgba(59,130,246,.14); border-color:#3b82f6; color:#bfdbfe; }

/* Sidebar Styling */
div[data-testid="stSidebar"] {
    background-color: #141311;
    border-right: 1px solid #262320;
}
div[data-testid="stSidebar"] label[data-baseweb="radio"] {
    padding:.48rem .65rem; border-radius:10px; width:100%;
}
div[data-testid="stSidebar"] label[data-baseweb="radio"]:hover {
    background:rgba(245, 158, 11, 0.14);
}
button[kind="primary"] {
    background:#f59e0b !important;
    color:#121110 !important;
    font-weight:700 !important;
    border:none !important;
}
button[kind="primary"]:hover {
    background:#d97706 !important;
}
</style>
""",
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ HELPERS
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


def chart_frame(df: pd.DataFrame, max_points: int = 4000) -> pd.DataFrame:
    if len(df) > max_points:
        return df.iloc[:: len(df) // max_points + 1]
    return df


def kpi(label, value, sub="", icon="", color="#f59e0b"):
    st.markdown(
        f'<div class="kpi" style="--c:{color}"><div class="l">{icon} {label}</div>'
        f'<div class="v">{value}</div><div class="s">{sub}</div></div>',
        unsafe_allow_html=True,
    )


def trigger_sms_alert(reason_key: str, message: str):
    """Logs an automated SMS notification to the registered phone number without spamming duplicates."""
    if not st.session_state.sms_enabled:
        return
    if st.session_state.last_sms_trigger != reason_key:
        st.session_state.last_sms_trigger = reason_key
        st.session_state.sms_log.insert(
            0,
            {
                "time": datetime.now().strftime("%d %b %H:%M:%S"),
                "to": st.session_state.phone_number,
                "mode": st.session_state.weather_mode,
                "msg": message,
            },
        )


def evaluate_curing_and_sms(temp: float):
    """Evaluates slab temperature against IS 516 M25 Water Curing & active Weather Mode."""
    mode = st.session_state.weather_mode
    opt_min = st.session_state.curing_opt_min
    opt_max = st.session_state.curing_opt_max
    s_max = st.session_state.summer_max_temp
    w_min = st.session_state.winter_min_temp
    phone = st.session_state.phone_number

    if mode == "Rainy / Monsoon Mode":
        msg = (
            f"🌧️ MONSOON ALERT: Slab temp is {temp:.1f}°C. Heavy rain/washout risk active! "
            f"Pause water ponding and cover M25 slab with waterproof tarpaulin immediately."
        )
        trigger_sms_alert("RAINY_ACTIVE", msg)
        return (
            "s-blue",
            "🌧️ <b>Monsoon Protection Active:</b> Pause water curing. Cover fresh M25 concrete with waterproof sheets to prevent cement slurry washout.",
            "Tarpaulin Cover Needed",
        )

    if mode == "Summer Mode":
        if temp > s_max:
            msg = (
                f"☀️ HIGH HEAT ALERT: M25 Slab temp reached {temp:.1f}°C (Limit: {s_max:.0f}°C). "
                f"Rapid evaporation risk! Water curing needed immediately."
            )
            trigger_sms_alert(f"SUMMER_HIGH_{int(temp)}", msg)
            return (
                "s-red",
                f"🔥 <b>Water Curing Needed Immediately (SMS Sent to {phone}):</b> Slab temperature is <b>{temp:.1f}°C</b> (exceeds {s_max:.0f}°C Summer threshold). Flood slab or spray water to prevent plastic shrinkage cracks.",
                "URGENT: Apply Water",
            )
        elif opt_min <= temp <= opt_max:
            return (
                "s-green",
                f"💧 <b>Optimal Water Curing Zone ({temp:.1f}°C):</b> Within IS 516 standard (27 ± 2°C). Maintain normal wet ponding.",
                "Optimal (25–29°C)",
            )
        elif temp > opt_max:
            return (
                "s-amber",
                f"☀️ <b>Warm Slab ({temp:.1f}°C):</b> Slightly above 29°C ideal curing range. Keep surface damp.",
                "Keep Surface Damp",
            )
        else:
            return (
                "s-amber",
                f"🌤️ <b>Moderate Temp ({temp:.1f}°C):</b> Below 25°C standard water curing temp. Light curing recommended.",
                "Moderate Curing",
            )

    # Winter Mode
    if temp < w_min:
        msg = (
            f"❄️ WINTER COLD ALERT: M25 Slab temp dropped to {temp:.1f}°C (Below {w_min:.0f}°C). "
            f"Hydration slowing down! Avoid cold water ponding; cover with wet gunny bags & plastic sheet."
        )
        trigger_sms_alert(f"WINTER_LOW_{int(temp)}", msg)
        return (
            "s-amber",
            f"❄️ <b>Low Temperature Alert (SMS Sent to {phone}):</b> Slab is at <b>{temp:.1f}°C</b> (below {w_min:.0f}°C Winter limit). Cement hydration slows down in cold weather. Avoid ice-cold water; use insulated wet gunny (hessian) blankets.",
            "Insulate Slab (Hessian)",
        )
    else:
        return (
            "s-green",
            f"❄️ <b>Winter Curing Stable ({temp:.1f}°C):</b> Safe hydration rate. Retain heat with damp hessian cloth.",
            "Winter Safe",
        )


def status_banner(strength: float, temp: float):
    c, s = st.session_state.caution, st.session_state.safe
    # 1. Framework / Strength Status Banner
    if strength < c:
        st.markdown(
            f'<div class="status s-red">🔴 <b>Framework Decision — DO NOT REMOVE:</b> Current M25 strength is <b>{strength:.1f} MPa</b> (Minimum caution: {c:.0f} MPa, Target: {s:.0f} MPa).</div>',
            unsafe_allow_html=True,
        )
    elif strength < s:
        st.markdown(
            f'<div class="status s-amber">🟡 <b>Framework Decision — WAIT (Curing in Progress):</b> Current strength is <b>{strength:.1f} MPa</b>. Wait until M25 target of <b>{s:.0f} MPa</b> is reached.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="status s-green">🟢 <b>Framework Decision — SAFE TO REMOVE:</b> Target M25 strength of <b>{strength:.1f} MPa</b> reached! Framework can be safely stripped.</div>',
            unsafe_allow_html=True,
        )

    # 2. Water Curing & Seasonal SMS Status Banner
    css_class, html_text, _ = evaluate_curing_and_sms(temp)
    st.markdown(f'<div class="status {css_class}">{html_text}</div>', unsafe_allow_html=True)


def style_fig(fig, height=320):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans", color="#e7e5e4"),
        legend=dict(orientation="h", y=-0.2),
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,.08)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,.08)")
    return fig


def line_fig(df, x, y, title, color, thresholds=False, temp_bands=False):
    fill_rgba = "rgba(245,158,11,.12)" if color == "#f59e0b" else "rgba(16,185,129,.12)"
    fig = go.Figure(
        go.Scatter(
            x=df[x],
            y=df[y],
            mode="lines",
            line=dict(color=color, width=2.5),
            fill="tozeroy",
            fillcolor=fill_rgba,
        )
    )
    if thresholds:
        fig.add_hline(
            y=st.session_state.caution,
            line_dash="dot",
            line_color="#ef4444",
            annotation_text="Caution (15 MPa)",
        )
        fig.add_hline(
            y=st.session_state.safe,
            line_dash="dot",
            line_color="#10b981",
            annotation_text="M25 Target (25 MPa)",
        )
    if temp_bands:
        fig.add_hrect(
            y0=st.session_state.curing_opt_min,
            y1=st.session_state.curing_opt_max,
            fillcolor="rgba(16,185,129,0.12)",
            line_width=0,
            annotation_text="IS 516 Optimal Water Curing (25-29°C)",
        )
        fig.add_hline(
            y=st.session_state.summer_max_temp,
            line_dash="dash",
            line_color="#ef4444",
            annotation_text="Summer SMS Alert (>32°C)",
        )
        fig.add_hline(
            y=st.session_state.winter_min_temp,
            line_dash="dash",
            line_color="#3b82f6",
            annotation_text="Winter SMS Alert (<15°C)",
        )
    fig.update_layout(title=title, xaxis_title=x, yaxis_title=y)
    return style_fig(fig)


def gauge(value):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": " MPa"},
            gauge={
                "axis": {"range": [0, max(35, value * 1.2)]},
                "bar": {"color": "#f59e0b"},
                "steps": [
                    {"range": [0, st.session_state.caution], "color": "rgba(239,68,68,.30)"},
                    {
                        "range": [st.session_state.caution, st.session_state.safe],
                        "color": "rgba(245,158,11,.30)",
                    },
                    {"range": [st.session_state.safe, 100], "color": "rgba(16,185,129,.30)"},
                ],
            },
            title={"text": "M25 Strength Progress"},
        )
    )
    return style_fig(fig, 320)


def display_dashboard(df, key_prefix, live=False):
    df = normalize_columns(df)
    plot_df = chart_frame(df)
    need = {"age_h", "slab_temp", "strength_mpa"}

    if need.issubset(df.columns):
        t = float(df["slab_temp"].iloc[-1])
        s = float(df["strength_mpa"].iloc[-1])
        peak = float(df["strength_mpa"].max())
        age = float(df["age_h"].iloc[-1])
        _, _, curing_short = evaluate_curing_and_sms(t)

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            kpi("Slab Temperature", f"{t:.1f} °C", f"avg {df['slab_temp'].mean():.1f} °C · {curing_short}", "🌡️", "#f59e0b")
        with k2:
            kpi("M25 Strength", f"{s:.1f} MPa", f"Target: {st.session_state.safe:.0f} MPa", "💪", "#10b981")
        with k3:
            kpi("Peak Strength", f"{peak:.1f} MPa", "highest recorded", "📈", "#3b82f6")
        with k4:
            kpi("Concrete Age", f"{age:.1f} h", f"{len(df):,} sensor logs", "⏱️", "#a855f7")

        st.write("")
        status_banner(s, t)
        st.write("")

        g, c = st.columns([1, 2])
        with g:
            st.plotly_chart(gauge(s), use_container_width=True, key=f"{key_prefix}_g")
        with c:
            st.plotly_chart(
                line_fig(plot_df, "age_h", "strength_mpa", "M25 Strength Development Curve", "#10b981", thresholds=True),
                use_container_width=True,
                key=f"{key_prefix}_s",
            )

        a, b = st.columns(2)
        with a:
            st.plotly_chart(
                line_fig(plot_df, "age_h", "slab_temp", "Slab Temperature & Water Curing Limits", "#f59e0b", temp_bands=True),
                use_container_width=True,
                key=f"{key_prefix}_t",
            )
        with b:
            fig = go.Figure(
                go.Scatter(
                    x=plot_df["slab_temp"],
                    y=plot_df["strength_mpa"],
                    mode="markers",
                    marker=dict(
                        color=plot_df["age_h"],
                        colorscale="YlOrBr",
                        showscale=True,
                        colorbar=dict(title="Age (h)"),
                    ),
                )
            )
            fig.update_layout(
                title="Strength vs. Slab Temperature",
                xaxis_title="Slab Temperature (°C)",
                yaxis_title="Strength (MPa)",
            )
            st.plotly_chart(style_fig(fig), use_container_width=True, key=f"{key_prefix}_sc")
    else:
        st.warning(
            "Columns 'age_h', 'slab_temp' and 'strength_mpa' are missing, so the automatic "
            "status is switched off. You can still use the graph builder below."
        )

    with st.expander("🎨 Custom graph builder"):
        cx, cy, ct = st.columns(3)
        x = cx.selectbox("X axis", df.columns, key=f"{key_prefix}_x")
        y = cy.selectbox("Y axis", df.columns, index=min(1, len(df.columns) - 1), key=f"{key_prefix}_y")
        kind = ct.selectbox("Chart type", ["Line", "Scatter", "Bar"], key=f"{key_prefix}_k")
        trace = {
            "Line": go.Scatter(x=plot_df[x], y=plot_df[y], mode="lines", line=dict(color="#f59e0b")),
            "Scatter": go.Scatter(x=plot_df[x], y=plot_df[y], mode="markers", marker=dict(color="#f59e0b")),
            "Bar": go.Bar(x=plot_df[x], y=plot_df[y], marker_color="#f59e0b"),
        }[kind]
        st.plotly_chart(style_fig(go.Figure(trace)), use_container_width=True, key=f"{key_prefix}_cg")

    with st.expander("📋 Sensor data log", expanded=False):
        st.dataframe(df.tail(st.session_state.rows), use_container_width=True)
        st.caption(f"Showing last {min(len(df), st.session_state.rows):,} of {len(df):,} rows.")

    st.download_button(
        "⬇️ Export full log (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        "curesense_m25_sensor_log.csv",
        "text/csv",
        key=f"{key_prefix}_dl",
    )


def go_to(page):
    st.session_state.page = page


def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.user = None


# ------------------------------------------------------------------ AUTHENTICATION
if st.session_state.user is None:
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid:
        st.markdown(
            '<div class="hero" style="text-align:center"><h2>🏗️ CureSense M25</h2>'
            "<p>IoT Concrete Water Curing & ML Strength Prediction System</p>"
            '<p style="font-size:0.8rem; margin-top:6px;">Support: <a href="mailto:concremet@gmail.com" style="color:#fbbf24;">concremet@gmail.com</a></p></div>',
            unsafe_allow_html=True,
        )
        st.write("")
        t_login, t_sign, t_reset = st.tabs(["🔒 Login", "📝 Create account", "🔑 Reset password"])

        with t_login:
            email = st.text_input("Email", key="log_email", placeholder="you@company.com")
            pw = st.text_input("Password", type="password", key="log_pass")
            if st.button("Log in", type="primary", use_container_width=True):
                try:
                    r = supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": pw})
                    st.session_state.user = r.user
                    st.rerun()
                except Exception as e:
                    m = str(e).lower()
                    if "not confirmed" in m:
                        st.error("Your email is not verified. Verify it in the Create account tab.")
                    elif "invalid login" in m:
                        st.error("Wrong email or password.")
                    else:
                        st.error(f"Login failed: {e}")

        with t_sign:
            if not st.session_state.awaiting_otp:
                st.caption("We will email you a one-time code to verify your address.")
                e2 = st.text_input("Email", key="sign_email")
                p2 = st.text_input("Password (min 6 characters)", type="password", key="sign_pass")
                if st.button("Send code", type="primary", use_container_width=True):
                    try:
                        supabase.auth.sign_up({"email": e2.strip().lower(), "password": p2})
                        st.session_state.awaiting_otp = True
                        st.session_state.signup_email = e2.strip().lower()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Registration failed: {e}")
            else:
                st.success(f"Code sent to **{st.session_state.signup_email}**.")
                code = st.text_input("Enter the code", key="otp_input")
                if st.button("Verify and create account", type="primary", use_container_width=True):
                    try:
                        supabase.auth.verify_otp(
                            {"email": st.session_state.signup_email, "token": code.strip(), "type": "signup"}
                        )
                        try:
                            supabase.auth.sign_out()
                        except Exception:
                            pass
                        st.session_state.awaiting_otp = False
                        st.success("Account verified. Open the Login tab to sign in.")
                    except Exception as e:
                        st.error(f"Invalid or expired code: {e}")
                c1, c2 = st.columns(2)
                if c1.button("Resend code", use_container_width=True):
                    try:
                        supabase.auth.resend({"type": "signup", "email": st.session_state.signup_email})
                        st.info("A new code was sent.")
                    except Exception as e:
                        st.error(f"Could not resend: {e}")
                if c2.button("Start over", use_container_width=True):
                    st.session_state.awaiting_otp = False
                    st.rerun()

        with t_reset:
            st.caption("Enter your email to receive a password reset link.")
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
with st.sidebar:
    st.markdown("## 🏗️ CureSense M25")
    st.caption("IoT Water Curing & Maturity System")
    st.radio(
        "Navigation",
        list(PAGES),
        key="page",
        label_visibility="collapsed",
        format_func=lambda p: f"{PAGES[p]}  {p}",
    )
    st.divider()

    # Quick Season Mode Switcher in Sidebar
    st.markdown("**🌦️ Active Curing Season**")
    st.selectbox(
        "Select Weather Mode",
        ["Summer Mode", "Winter Mode", "Rainy / Monsoon Mode"],
        key="weather_mode",
        label_visibility="collapsed",
    )
    st.caption(f"📱 SMS Alert To: `{st.session_state.phone_number}`")

    st.divider()
    st.markdown("**System status**")
    st.success("Supabase Connected", icon="🟢")
    (st.success if model else st.warning)("ML Engine Online" if model else "ML Engine Offline", icon="🧠")
    st.divider()
    st.caption(
        f"👤 {st.session_state.operator}\n\n"
        f"✉️ {user.email}\n\n"
        f"🆘 Help: [concremet@gmail.com](mailto:concremet@gmail.com)"
    )

# ------------------------------------------------------------------ HEADER + ⋮ MENU
h1, h2 = st.columns([12, 1])
with h1:
    st.markdown(
        f'<div class="hero"><h2>{PAGES[st.session_state.page]} {st.session_state.page}</h2>'
        f'<p><span class="pill"><span class="live-dot"></span>Live IoT</span>'
        f'<span class="pill">M25 Grade (25 MPa)</span>'
        f'<span class="pill">{st.session_state.weather_mode}</span>'
        f'<span class="pill">{st.session_state.dept}</span>'
        f"{datetime.now():%d %b %Y}</p></div>",
        unsafe_allow_html=True,
    )
with h2:
    with st.popover("⋮", use_container_width=True):
        st.markdown(f"**{st.session_state.operator}**")
        st.caption(user.email)
        st.divider()
        st.toggle("Auto-refresh live data", key="auto")
        st.select_slider("Refresh every (s)", [5, 10, 30, 60], key="refresh")
        st.divider()
        for p in ["Water curing & SMS", "Settings", "Help & about"]:
            st.button(f"{PAGES[p]} {p}", key=f"menu_{p}", on_click=go_to, args=(p,), use_container_width=True)
        st.button(
            "📡 Live dashboard",
            key="menu_live",
            on_click=go_to,
            args=("Live dashboard",),
            use_container_width=True,
        )
        st.button("🚪 Log out", key="menu_logout", on_click=logout, use_container_width=True)
st.write("")

# ------------------------------------------------------------------ PAGES
page = st.session_state.page

if page == "Live dashboard":
    def live_view():
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
                st.caption(
                    f"Last updated {datetime.now():%H:%M:%S}"
                    + (
                        f" · refreshes every {st.session_state.refresh}s"
                        if st.session_state.auto
                        else " · auto-refresh off"
                    )
                    + f" · Support: concremet@gmail.com"
                )
                display_dashboard(df, "live", live=True)
            else:
                st.info(
                    "No records yet. Check that your ESP32 sensor is sending data and that row-level "
                    "security allows this user to read `strength_view`."
                )
        except Exception as e:
            st.error(f"Database connection error: {e}")

    st.fragment(run_every=st.session_state.refresh if st.session_state.auto else None)(live_view)()

elif page == "Water curing & SMS":
    st.subheader("💧 M25 Water Curing & Seasonal SMS Alert Center")
    st.caption(
        "Standard water curing temperature per IS 516 / IS 456 is **27 ± 2°C (25°C to 29°C)**. "
        "Configure seasonal rules and registered mobile numbers below."
    )

    c1, c2 = st.columns([1.2, 1.8])
    with c1:
        st.markdown("#### ⚙️ Seasonal Thresholds & SMS Setup")
        st.text_input("Registered Site Engineer Phone Number", key="phone_number")
        st.toggle("Enable Automated SMS Alerts", key="sms_enabled")

        st.selectbox(
            "Active Weather / Curing Mode",
            ["Summer Mode", "Winter Mode", "Rainy / Monsoon Mode"],
            key="weather_mode",
        )

        st.number_input(
            "☀️ Summer High-Temp SMS Trigger (°C)",
            min_value=28.0,
            max_value=50.0,
            step=0.5,
            key="summer_max_temp",
            help="Sends an SMS to apply water curing immediately when slab temperature exceeds this limit.",
        )
        st.number_input(
            "❄️ Winter Low-Temp SMS Trigger (°C)",
            min_value=5.0,
            max_value=22.0,
            step=0.5,
            key="winter_min_temp",
            help="Sends an SMS warning that hydration is slowing down and insulation (hessian blankets) is required.",
        )

        if st.button("📲 Send Test SMS Alert Now", type="primary", use_container_width=True):
            st.session_state.sms_log.insert(
                0,
                {
                    "time": datetime.now().strftime("%d %b %H:%M:%S"),
                    "to": st.session_state.phone_number,
                    "mode": st.session_state.weather_mode,
                    "msg": f"TEST ALERT [{st.session_state.weather_mode}]: Water curing monitor active for M25 slab. Support: concremet@gmail.com",
                },
            )
            st.success(f"Test SMS logged for {st.session_state.phone_number}!")

    with c2:
        st.markdown("#### 📩 Sent SMS Alert History (Site Engineer Inbox)")
        for item in st.session_state.sms_log[:10]:
            st.markdown(
                f'<div class="kpi" style="--c:#f59e0b; margin-bottom:10px;">'
                f'<div class="l">📱 <b>To: {item["to"]}</b> · <span style="color:#fbbf24">{item["mode"]}</span> · {item["time"]}</div>'
                f'<div style="font-size:0.92rem; color:#f4f4f0; margin-top:6px;">{item["msg"]}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

elif page == "CSV analytics":
    st.write("Upload a historical sensor log to analyse M25 strength and water curing offline.")
    f = st.file_uploader("Upload CSV", type="csv")
    if f is not None:
        try:
            display_dashboard(pd.read_csv(f), "csv")
        except Exception as e:
            st.error(f"Could not read the file: {e}")

elif page == "Strength predictor":
    st.subheader("🧠 M25 Concrete Strength & Water Curing Predictor")
    c1, c2 = st.columns(2)
    age = c1.number_input("Concrete age (hours)", min_value=0.0, value=24.0, step=0.5)
    temp = c2.number_input("Slab temperature (°C)", min_value=-10.0, max_value=60.0, value=28.0, step=0.5)
    if st.button("Predict strength & curing need", type="primary"):
        if not model:
            st.error("Model offline. Put 'ann_concrete_strength_model.pkl' next to app.py.")
        else:
            try:
                pred = float(model.predict(pd.DataFrame([[age, temp]], columns=["age_h", "slab_temp"]))[0])
                a, b = st.columns([1, 2])
                with a:
                    kpi("Predicted M25 Strength", f"{pred:.2f} MPa", f"at {age:g} h, {temp:g} °C", "🧠", "#f59e0b")
                    st.write("")
                    status_banner(pred, temp)
                with b:
                    ages = pd.DataFrame({"age_h": [i for i in range(0, 169, 2)], "slab_temp": temp})
                    curve = model.predict(ages)
                    fig = go.Figure(
                        go.Scatter(
                            x=ages["age_h"],
                            y=curve,
                            mode="lines",
                            line=dict(color="#10b981", width=3),
                            name="Projected MPa",
                        )
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=[age],
                            y=[pred],
                            mode="markers",
                            marker=dict(size=12, color="#f59e0b"),
                            name="Your Input",
                        )
                    )
                    fig.add_hline(y=st.session_state.safe, line_dash="dot", line_color="#f59e0b", annotation_text="M25 Target (25 MPa)")
                    fig.update_layout(
                        title=f"Projected M25 Strength Curve at {temp:g} °C (7 Days)",
                        xaxis_title="Age (h)",
                        yaxis_title="Strength (MPa)",
                    )
                    st.plotly_chart(style_fig(fig), use_container_width=True)
            except Exception as e:
                st.error(f"Model error: {e}. The model must be trained on 'age_h' and 'slab_temp'.")

elif page == "Settings":
    t1, t2, t3 = st.tabs(["👤 Profile", "🚦 M25 & Curing Limits", "📡 Data"])
    with t1:
        st.text_input("Operator name", key="operator")
        st.text_input("Department", key="dept")
        st.text_input("Registered Phone (for SMS)", key="phone_number")
        st.text_input("Email", value=user.email, disabled=True)
    with t2:
        st.number_input("Minimum strength to avoid critical alert (MPa)", 1.0, 100.0, key="caution")
        st.number_input("Target strength for M25 framework removal (MPa)", 1.0, 100.0, key="safe")
        st.divider()
        st.number_input("Optimal Water Curing Min Temp (°C - IS 516)", 15.0, 35.0, key="curing_opt_min")
        st.number_input("Optimal Water Curing Max Temp (°C - IS 516)", 20.0, 40.0, key="curing_opt_max")
        if st.session_state.safe <= st.session_state.caution:
            st.warning("The target strength should be higher than the minimum caution strength.")
    with t3:
        st.toggle("Auto-refresh live data", key="auto")
        st.select_slider("Refresh interval (seconds)", [5, 10, 30, 60], key="refresh")
        st.select_slider("Rows to load", [500, 1000, 2000, 5000, 10000], key="rows")
    st.success("Changes are applied immediately for this session.")

else:
    st.markdown(
        """
### 🏗️ CureSense M25 — Seasonal Water Curing & Strength Guide

#### 1. Standard Water Curing Temperature (IS 516 / IS 456)
* **Optimal Range:** **27 ± 2°C (25°C to 29°C)**.
* **☀️ Summer Mode (>32°C):** High heat causes rapid evaporation and shrinkage cracks. Automated SMS alerts the site engineer to apply water curing immediately.
* **❄️ Winter Mode (<15°C):** Cold weather slows down cement hydration. Avoid ponding with ice-cold water; cover the slab with wet gunny bags (hessian cloth) and plastic sheeting to trap internal heat of hydration.
* **🌧️ Rainy / Monsoon Mode:** Heavy rain risks washing out cement slurry from fresh concrete. Pause water ponding and cover the slab with waterproof tarpaulin sheets.

#### 2. Framework Removal Decision (M25 Grade)
* 🔴 **Red (<15 MPa):** Critical — Do not remove framework.
* 🟡 **Amber (15–25 MPa):** Caution — Curing in progress; wait for 25 MPa target.
* 🟢 **Green (≥25 MPa):** Safe — M25 target strength achieved; framework can be stripped.

#### 3. Support & Contact
For technical help, calibration, or reporting issues, email **[concremet@gmail.com](mailto:concremet@gmail.com)**.
"""
    )
