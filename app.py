import os
from datetime import datetime

import joblib
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from supabase import create_client

# ------------------------------------------------------------------ PAGE
st.set_page_config(
    page_title="CureSense | Concrete Curing Analytics",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": "mailto:support@example.com",
        "Report a bug": "mailto:support@example.com",
        "About": "CureSense: IoT concrete curing and strength prediction.",
    },
)

# Put these in Render > Environment (recommended). Defaults = your publishable key.
SUPABASE_URL = "https://icneaaqjtrlujhwqtnrs.supabase.co"
SUPABASE_KEY = "sb_publishable_SW2ROPWfLIpC4TdnAXV_Mg_oqc0STTq"
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

# ------------------------------------------------------------------ STATE
DEFAULTS = {
    "user": None, "awaiting_otp": False, "signup_email": "",
    "page": "Live dashboard", "auto": True, "refresh": 10, "rows": 2000,
    "caution": 15.0, "safe": 20.0, "operator": "Swati Chhanikar", "dept": "IIoT Engineering",
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

PAGES = {
    "Live dashboard": "📡",
    "CSV analytics": "📂",
    "Strength predictor": "🧠",
    "Settings": "⚙️",
    "Help & about": "💡",
}

# ------------------------------------------------------------------ STYLE
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
#MainMenu {visibility:visible;} footer {visibility:hidden;}
.block-container { padding-top: 1.4rem; max-width: 1400px; }

.hero { background: linear-gradient(115deg,#12232e 0%,#0f4c5c 55%,#1b7f79 100%);
  border-radius: 18px; padding: 1.3rem 1.6rem; color:#f4f7f6; }
.hero h2 { margin:0; font-weight:700; letter-spacing:-.01em; color:#fff; }
.hero p { margin:.25rem 0 0; opacity:.8; font-size:.95rem; }
.pill { display:inline-block; padding:.15rem .6rem; border-radius:999px; font-size:.75rem;
  font-weight:600; background:rgba(255,255,255,.16); margin-right:.4rem; }
.live-dot { display:inline-block; width:9px; height:9px; border-radius:50%; background:#34d399;
  margin-right:6px; box-shadow:0 0 0 0 rgba(52,211,153,.7); animation:pulse 1.8s infinite; }
@keyframes pulse { 70% { box-shadow:0 0 0 9px rgba(52,211,153,0);} 100% {box-shadow:0 0 0 0 rgba(52,211,153,0);} }

.kpi { border:1px solid rgba(128,128,128,.25); border-left:5px solid var(--c,#1b7f79);
  border-radius:12px; padding:.9rem 1.1rem; background:rgba(128,128,128,.06); }
.kpi .l { font-size:.82rem; opacity:.7; }
.kpi .v { font-size:1.9rem; font-weight:700; line-height:1.2; }
.kpi .s { font-size:.78rem; opacity:.6; }

.status { border-radius:12px; padding:1rem 1.2rem; font-weight:500; border:1px solid; }
.s-red { background:rgba(239,68,68,.12); border-color:#ef4444; }
.s-amber { background:rgba(245,158,11,.14); border-color:#f59e0b; }
.s-green { background:rgba(16,185,129,.13); border-color:#10b981; }

div[data-testid="stSidebar"] { border-right:1px solid rgba(128,128,128,.2); }
div[data-testid="stSidebar"] label[data-baseweb="radio"] { padding:.45rem .6rem; border-radius:10px; width:100%; }
div[data-testid="stSidebar"] label[data-baseweb="radio"]:hover { background:rgba(27,127,121,.15); }
button[kind="primary"] { background:#1b7f79; border:none; }
.stTabs [data-baseweb="tab"] { font-weight:600; }
</style>
""",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ HELPERS
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {"elapsed_hours": "age_h", "concrete_avg_temp_C": "slab_temp",
               "strength_MPa": "strength_mpa", "created_at": "ts"}
    for old, new in mapping.items():
        if old in df.columns and new not in df.columns:
            df = df.rename(columns={old: new})
    return df


def chart_frame(df: pd.DataFrame, max_points: int = 4000) -> pd.DataFrame:
    if len(df) > max_points:
        return df.iloc[:: len(df) // max_points + 1]
    return df


def kpi(label, value, sub="", icon="", color="#1b7f79"):
    st.markdown(
        f'<div class="kpi" style="--c:{color}"><div class="l">{icon} {label}</div>'
        f'<div class="v">{value}</div><div class="s">{sub}</div></div>',
        unsafe_allow_html=True,
    )


def status_banner(strength):
    c, s = st.session_state.caution, st.session_state.safe
    if strength < c:
        st.markdown(f'<div class="status s-red">🔴 <b>Critical:</b> strength is {strength:.1f} MPa. '
                    f'Do not remove the framework.</div>', unsafe_allow_html=True)
    elif strength < s:
        st.markdown(f'<div class="status s-amber">🟡 <b>Caution:</b> strength is {strength:.1f} MPa. '
                    f'Curing is progressing; wait for {s:.0f} MPa.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="status s-green">🟢 <b>Safe to proceed:</b> {strength:.1f} MPa reached. '
                    f'The framework can be removed.</div>', unsafe_allow_html=True)


def style_fig(fig, height=320):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="IBM Plex Sans"), legend=dict(orientation="h", y=-0.2))
    fig.update_xaxes(gridcolor="rgba(128,128,128,.2)")
    fig.update_yaxes(gridcolor="rgba(128,128,128,.2)")
    return fig


def line_fig(df, x, y, title, color, thresholds=False):
    fig = go.Figure(go.Scatter(x=df[x], y=df[y], mode="lines", line=dict(color=color, width=2.5),
                               fill="tozeroy", fillcolor=color.replace(")", ",.10)").replace("rgb", "rgba")
                               if color.startswith("rgb") else "rgba(27,127,121,.10)"))
    if thresholds:
        fig.add_hline(y=st.session_state.caution, line_dash="dot", line_color="#ef4444",
                      annotation_text="Minimum")
        fig.add_hline(y=st.session_state.safe, line_dash="dot", line_color="#10b981",
                      annotation_text="Target")
    fig.update_layout(title=title, xaxis_title=x, yaxis_title=y)
    return style_fig(fig)


def gauge(value):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value, number={"suffix": " MPa"},
        gauge={"axis": {"range": [0, max(40, value * 1.2)]}, "bar": {"color": "#1b7f79"},
               "steps": [{"range": [0, st.session_state.caution], "color": "rgba(239,68,68,.35)"},
                         {"range": [st.session_state.caution, st.session_state.safe], "color": "rgba(245,158,11,.35)"},
                         {"range": [st.session_state.safe, 100], "color": "rgba(16,185,129,.35)"}]},
        title={"text": "Current strength"}))
    return style_fig(fig, 320)


def display_dashboard(df, key_prefix, live=False):
    df = normalize_columns(df)
    plot_df = chart_frame(df)
    need = {"age_h", "slab_temp", "strength_mpa"}

    if need.issubset(df.columns):
        t, s, peak = df["slab_temp"].iloc[-1], df["strength_mpa"].iloc[-1], df["strength_mpa"].max()
        k1, k2, k3, k4 = st.columns(4)
        with k1: kpi("Slab temperature", f"{t:.1f} °C", f"avg {df['slab_temp'].mean():.1f} °C", "🌡️", "#ef4444")
        with k2: kpi("Current strength", f"{s:.1f} MPa", "latest estimate", "💪", "#1b7f79")
        with k3: kpi("Peak strength", f"{peak:.1f} MPa", "highest recorded", "📈", "#3b82f6")
        with k4: kpi("Concrete age", f"{df['age_h'].iloc[-1]:.1f} h", f"{len(df):,} readings", "⏱️", "#f59e0b")
        st.write("")
        status_banner(s)
        st.write("")

        g, c = st.columns([1, 2])
        with g: st.plotly_chart(gauge(s), use_container_width=True, key=f"{key_prefix}_g")
        with c: st.plotly_chart(line_fig(plot_df, "age_h", "strength_mpa", "Strength development", "#1b7f79", True),
                                use_container_width=True, key=f"{key_prefix}_s")
        a, b = st.columns(2)
        with a: st.plotly_chart(line_fig(plot_df, "age_h", "slab_temp", "Temperature profile", "#ef4444"),
                                use_container_width=True, key=f"{key_prefix}_t")
        with b:
            fig = go.Figure(go.Scatter(x=plot_df["slab_temp"], y=plot_df["strength_mpa"], mode="markers",
                                       marker=dict(color=plot_df["age_h"], colorscale="Tealgrn",
                                                   showscale=True, colorbar=dict(title="Age (h)"))))
            fig.update_layout(title="Strength vs temperature", xaxis_title="slab_temp", yaxis_title="strength_mpa")
            st.plotly_chart(style_fig(fig), use_container_width=True, key=f"{key_prefix}_sc")
    else:
        st.warning("Columns 'age_h', 'slab_temp' and 'strength_mpa' are missing, so the automatic "
                   "status is switched off. You can still use the graph builder below.")

    with st.expander("🎨 Custom graph builder"):
        cx, cy, ct = st.columns(3)
        x = cx.selectbox("X axis", df.columns, key=f"{key_prefix}_x")
        y = cy.selectbox("Y axis", df.columns, index=min(1, len(df.columns) - 1), key=f"{key_prefix}_y")
        kind = ct.selectbox("Chart type", ["Line", "Scatter", "Bar"], key=f"{key_prefix}_k")
        trace = {"Line": go.Scatter(x=plot_df[x], y=plot_df[y], mode="lines"),
                 "Scatter": go.Scatter(x=plot_df[x], y=plot_df[y], mode="markers"),
                 "Bar": go.Bar(x=plot_df[x], y=plot_df[y])}[kind]
        st.plotly_chart(style_fig(go.Figure(trace)), use_container_width=True, key=f"{key_prefix}_cg")

    with st.expander("📋 Sensor data log", expanded=False):
        st.dataframe(df.tail(st.session_state.rows), use_container_width=True)
        st.caption(f"Showing last {min(len(df), st.session_state.rows):,} of {len(df):,} rows.")
    st.download_button("⬇️ Export full log (CSV)", df.to_csv(index=False).encode("utf-8"),
                       "concrete_sensor_log.csv", "text/csv", key=f"{key_prefix}_dl")


def go_to(page):
    st.session_state.page = page


def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.user = None


# ------------------------------------------------------------------ AUTH
if st.session_state.user is None:
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid:
        st.markdown('<div class="hero" style="text-align:center"><h2>🏗️ CureSense</h2>'
                    '<p>IoT concrete curing monitor and strength prediction</p></div>', unsafe_allow_html=True)
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
                        supabase.auth.verify_otp({"email": st.session_state.signup_email,
                                                  "token": code.strip(), "type": "signup"})
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
    st.markdown("## 🏗️ CureSense")
    st.caption("Concrete curing analytics")
    st.radio("Navigation", list(PAGES), key="page", label_visibility="collapsed",
             format_func=lambda p: f"{PAGES[p]}  {p}")
    st.divider()
    st.markdown("**System status**")
    st.success("Database connected", icon="🟢")
    (st.success if model else st.warning)("ML engine online" if model else "ML engine offline", icon="🧠")
    st.divider()
    st.caption(f"👤 {st.session_state.operator}\n\n✉️ {user.email}")

# ------------------------------------------------------------------ HEADER + ⋮ MENU
h1, h2 = st.columns([12, 1])
with h1:
    st.markdown(
        f'<div class="hero"><h2>{PAGES[st.session_state.page]} {st.session_state.page}</h2>'
        f'<p><span class="pill"><span class="live-dot"></span>Live</span>'
        f'<span class="pill">{st.session_state.dept}</span>'
        f'{datetime.now():%d %b %Y}</p></div>', unsafe_allow_html=True)
with h2:
    with st.popover("⋮", use_container_width=True):
        st.markdown(f"**{st.session_state.operator}**")
        st.caption(user.email)
        st.divider()
        st.toggle("Auto-refresh live data", key="auto")
        st.select_slider("Refresh every (s)", [5, 10, 30, 60], key="refresh")
        st.divider()
        for p in ["Settings", "Help & about"]:
            st.button(f"{PAGES[p]} {p}", key=f"menu_{p}", on_click=go_to, args=(p,), use_container_width=True)
        st.button("📡 Live dashboard", key="menu_live", on_click=go_to, args=("Live dashboard",),
                  use_container_width=True)
        st.button("🚪 Log out", key="menu_logout", on_click=logout, use_container_width=True)
st.write("")

# ------------------------------------------------------------------ PAGES
page = st.session_state.page

if page == "Live dashboard":
    def live_view():
        try:
            r = (supabase.table("strength_view").select("*").order("ts", desc=True)
                 .limit(st.session_state.rows).execute())
            if r.data:
                df = pd.DataFrame(r.data).iloc[::-1].reset_index(drop=True)
                st.caption(f"Last updated {datetime.now():%H:%M:%S}"
                           + (f" · refreshes every {st.session_state.refresh}s" if st.session_state.auto
                              else " · auto-refresh off"))
                display_dashboard(df, "live", live=True)
            else:
                st.info("No records yet. Check that your sensor is sending data and that row-level "
                        "security allows this user to read `strength_view`.")
        except Exception as e:
            st.error(f"Database connection error: {e}")

    # This is what makes the dashboard LIVE: only this block reruns every N seconds.
    st.fragment(run_every=st.session_state.refresh if st.session_state.auto else None)(live_view)()

elif page == "CSV analytics":
    st.write("Upload a historical sensor log to analyse it offline.")
    f = st.file_uploader("Upload CSV", type="csv")
    if f is not None:
        try:
            display_dashboard(pd.read_csv(f), "csv")
        except Exception as e:
            st.error(f"Could not read the file: {e}")

elif page == "Strength predictor":
    c1, c2 = st.columns(2)
    age = c1.number_input("Concrete age (hours)", min_value=0.0, value=24.0, step=0.5)
    temp = c2.number_input("Slab temperature (°C)", min_value=-10.0, max_value=60.0, value=25.0, step=0.5)
    if st.button("Predict strength", type="primary"):
        if not model:
            st.error("Model offline. Put 'ann_concrete_strength_model.pkl' next to app.py.")
        else:
            try:
                pred = float(model.predict(pd.DataFrame([[age, temp]], columns=["age_h", "slab_temp"]))[0])
                a, b = st.columns([1, 2])
                with a:
                    kpi("Predicted strength", f"{pred:.2f} MPa", f"at {age:g} h, {temp:g} °C", "🧠")
                    st.write("")
                    status_banner(pred)
                with b:
                    ages = pd.DataFrame({"age_h": [i for i in range(0, 169, 2)], "slab_temp": temp})
                    curve = model.predict(ages)
                    fig = go.Figure(go.Scatter(x=ages["age_h"], y=curve, mode="lines",
                                               line=dict(color="#1b7f79", width=3)))
                    fig.add_trace(go.Scatter(x=[age], y=[pred], mode="markers",
                                             marker=dict(size=12, color="#f59e0b"), name="Your input"))
                    fig.update_layout(title=f"Projected strength at {temp:g} °C (7 days)",
                                      xaxis_title="Age (h)", yaxis_title="MPa")
                    st.plotly_chart(style_fig(fig), use_container_width=True)
            except Exception as e:
                st.error(f"Model error: {e}. The model must be trained on 'age_h' and 'slab_temp'.")

elif page == "Settings":
    t1, t2, t3 = st.tabs(["👤 Profile", "🚦 Safety limits", "📡 Data"])
    with t1:
        st.text_input("Operator name", key="operator")
        st.text_input("Department", key="dept")
        st.text_input("Email", value=user.email, disabled=True)
    with t2:
        st.number_input("Minimum strength to avoid critical alert (MPa)", 1.0, 100.0, key="caution")
        st.number_input("Target strength for framework removal (MPa)", 1.0, 100.0, key="safe")
        if st.session_state.safe <= st.session_state.caution:
            st.warning("The target should be higher than the minimum.")
    with t3:
        st.toggle("Auto-refresh live data", key="auto")
        st.select_slider("Refresh interval (seconds)", [5, 10, 30, 60], key="refresh")
        st.select_slider("Rows to load", [500, 1000, 2000, 5000, 10000], key="rows")
    st.success("Changes are applied immediately for this session.")

else:
    st.markdown("""
### How live data works
1. Your sensor writes rows to Supabase.
2. The **Live dashboard** reads `strength_view` and reloads itself on the interval you set.
3. Use **⋮ menu → Auto-refresh** to pause or change the speed.

### Status colours
🔴 below the minimum strength · 🟡 curing in progress · 🟢 target reached.
Limits can be changed under **Settings → Safety limits**.

### Required columns
`age_h`, `slab_temp`, `strength_mpa`, `ts` (older names are converted automatically).
""")
