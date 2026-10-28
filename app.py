"""
IoT Based Concrete Curing & Strength Monitoring System
Professional multi-tab Streamlit dashboard.

Run:  streamlit run app.py
"""
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

try:
    from supabase import create_client
except Exception:  # supabase is optional
    create_client = None

# ============================================================== PAGE CONFIG
st.set_page_config(
    page_title="Concrete Curing & Strength Monitoring",
    page_icon="🧱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================== SUPABASE (optional, keys from environment ONLY)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().strip('"').strip("'")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip().strip('"').strip("'")
supabase = None
if create_client and SUPABASE_URL.startswith("https://") and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        supabase = None

# ============================================================== CONSTANTS / DEFAULTS
GRADES = {"M20": 20.0, "M25": 25.0, "M30": 30.0, "M35": 35.0, "M40": 40.0}
CUBE_AGES = [3, 7, 14, 21, 28]
DEFAULT_CUBE = {3: 18.5, 7: 27.3, 14: 35.8, 21: 42.1, 28: 48.7}

# Sidebar pages and top-tab pages share one "page" state
SIDEBAR = [
    ("Dashboard", "▦"),
    ("Upload Dataset", "⤒"),
    ("Temperature Alerts", "🔔"),
    ("Cube Test Data", "🧪"),
    ("Strength Prediction", "📈"),
    ("Settings", "⚙"),
]
TOP_TABS = ["Dashboard", "Live Monitoring", "Cube Test Comparison", "Strength Prediction (MPa)", "Settings"]
# top-tab label -> internal page name
TAB_TO_PAGE = {
    "Dashboard": "Dashboard",
    "Live Monitoring": "Live Monitoring",
    "Cube Test Comparison": "Cube Test Comparison",
    "Strength Prediction (MPa)": "Strength Prediction",
    "Settings": "Settings",
}
PAGE_TO_TAB = {v: k for k, v in TAB_TO_PAGE.items()}

DEFAULT_STATE = {
    "user": None,
    "auth_mode": "Sign In",
    "page": "Dashboard",
    "raw_df": None,            # uploaded dataset
    "upload_name": None,
    "grade": "M25",
    "alert_temp": 60.0,
    "alert_type": "Above",
    "cube_data": dict(DEFAULT_CUBE),
    "cube_saved": True,
    "calc_result": None,
    "datum_temp": 0.0,         # Nurse-Saul datum temperature (°C)
    "ref_temp": 27.0,          # assumed avg curing temp beyond dataset (°C)
    "auto_refresh": False,
    "refresh_s": 10,
    "operator": "Site Engineer",
    "phone": "",
    "sms_enabled": False,
    "last_alert_key": None,
    "sms_log": [],
    "project": "Slab Curing System",
}
for _k, _v in DEFAULT_STATE.items():
    st.session_state.setdefault(_k, _v)

# ============================================================== THEME / CSS
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.stApp { background: #f4f7fc; color: #0f172a; }
.block-container { padding: 1.2rem 2rem 2rem 2rem; max-width: 1600px; }

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b1b3a 0%, #0a1630 100%);
    border-right: 1px solid #14264d; min-width: 270px !important;
}
section[data-testid="stSidebar"] * { color: #dbe5ff; }
section[data-testid="stSidebar"] .stButton > button {
    justify-content: flex-start; width: 100%; background: transparent; border: none;
    border-radius: 10px; padding: .65rem .9rem; font-weight: 500; font-size: .92rem; color: #dbe5ff;
}
section[data-testid="stSidebar"] .stButton > button:hover { background: rgba(255,255,255,.07); color: #fff; }
section[data-testid="stSidebar"] .stButton > button[kind="primary"],
section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
    background: #1d4ed8; color: #fff; box-shadow: 0 4px 14px rgba(29,78,216,.45);
}
.brand { display:flex; gap:12px; align-items:center; padding:.4rem .3rem 0 .3rem; }
.brand-logo { width:46px; height:46px; border-radius:12px; background:linear-gradient(135deg,#3b82f6,#1e40af);
    display:flex; align-items:center; justify-content:center; font-size:24px; }
.brand-title { font-weight:700; font-size:.95rem; line-height:1.25; color:#fff; }
.brand-sub { font-size:.74rem; color:#8fa6d8; margin:.5rem .3rem 1.1rem .3rem; }
.side-box { border:1px solid #1f3566; background:rgba(255,255,255,.04); border-radius:10px;
    padding:.75rem .9rem; margin-top:1rem; font-size:.82rem; }
.side-box b { color:#fff; font-size:1rem; }

/* ---------- Top tabs (radio styled as tabs) ---------- */
div[role="radiogroup"][aria-label="top-nav"] { gap: 1.6rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0; }
div[role="radiogroup"][aria-label="top-nav"] label > div:first-child { display:none; }
div[role="radiogroup"][aria-label="top-nav"] label {
    padding: .55rem .2rem; margin: 0; border-bottom: 3px solid transparent; cursor: pointer;
}
div[role="radiogroup"][aria-label="top-nav"] label p { font-weight: 500; color:#475569; font-size:.9rem; }
div[role="radiogroup"][aria-label="top-nav"] label:has(input:checked) { border-bottom-color:#2563eb; }
div[role="radiogroup"][aria-label="top-nav"] label:has(input:checked) p { color:#1d4ed8; font-weight:700; }

/* ---------- Cards ---------- */
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div[data-testid="stVerticalBlock"] .card-title) ,
.card { background:#fff; }
div[data-testid="stVerticalBlockBorderWrapper"] {
    background:#ffffff; border:1px solid #e5eaf3 !important; border-radius:14px !important;
    box-shadow:0 2px 8px rgba(15,23,42,.04);
}
.card-title { font-weight:700; font-size:1rem; color:#0f172a; margin:0 0 .6rem 0; }
.card-note { font-size:.78rem; color:#64748b; margin-bottom:.5rem; }
.page-title { font-size:1.75rem; font-weight:800; color:#0b1b3a; margin:0; letter-spacing:-.02em; }
.page-sub { color:#64748b; font-size:.92rem; margin:.15rem 0 0 0; }
.pill-online { display:inline-flex; gap:6px; align-items:center; background:#e8f8ef; color:#15803d;
    border:1px solid #bbebd0; border-radius:999px; padding:.4rem .9rem; font-weight:600; font-size:.82rem; }
.upd { text-align:right; font-size:.72rem; color:#64748b; line-height:1.25; }
.upd b { color:#0f172a; font-size:.85rem; }

/* ---------- KPI cards ---------- */
.kpi { display:flex; gap:16px; align-items:center; border-radius:14px; padding:1.1rem 1.3rem; border:1px solid; height:118px; }
.kpi-ic { width:58px; height:58px; border-radius:50%; background:#fff; display:flex; align-items:center;
    justify-content:center; font-size:26px; box-shadow:0 2px 8px rgba(0,0,0,.08); flex-shrink:0; }
.kpi-label { font-size:.82rem; font-weight:600; }
.kpi-val { font-size:1.9rem; font-weight:800; color:#0b1b3a; line-height:1.15; }
.kpi-val small { font-size:1.05rem; font-weight:700; margin-left:4px; }
.kpi-sub { font-size:.78rem; color:#64748b; }
.kpi-blue   { background:#eef5ff; border-color:#d3e3fb; } .kpi-blue .kpi-label{color:#1d4ed8;}
.kpi-green  { background:#eafaf2; border-color:#c4ecd6; } .kpi-green .kpi-label{color:#15803d;}
.kpi-purple { background:#f3efff; border-color:#ddd3fb; } .kpi-purple .kpi-label{color:#6d28d9;}
.kpi-amber  { background:#fff7e6; border-color:#fde4b0; } .kpi-amber .kpi-label{color:#b45309;}
.kpi-red    { background:#fff0f0; border-color:#fbcaca; } .kpi-red .kpi-label{color:#b91c1c;}
.badge { display:inline-block; padding:.12rem .6rem; border-radius:999px; font-size:.72rem; font-weight:600; }
.badge-ok { background:#d9f5e5; color:#15803d; } .badge-bad { background:#fee2e2; color:#b91c1c; }
.note-ok { background:#eafaf2; border:1px solid #c4ecd6; color:#166534; border-radius:10px; padding:.6rem .8rem; font-size:.8rem; margin-top:.5rem; }
.calc-out { border-radius:12px; padding:.9rem 1rem; border:1px solid; }
.calc-out .l { font-size:.78rem; font-weight:600; } .calc-out .v { font-size:1.6rem; font-weight:800; color:#0b1b3a; }

/* ---------- Inputs / buttons ---------- */
div[data-baseweb="input"], div[data-baseweb="select"] > div { background:#fff !important; border-radius:8px !important; }
.stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"] {
    background:#2563eb; color:#fff; border:none; border-radius:8px; font-weight:600;
}
.stButton > button[kind="primary"]:hover { background:#1d4ed8; }
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================== CORE CALCULATIONS
def fit_curve(cube: dict, datum: float, ref_t: float):
    """Fit S = a + b*log10(M) (logarithmic strength–maturity relation) from cube results."""
    ages = np.array(sorted(cube), dtype=float)
    strengths = np.array([cube[int(a)] for a in ages], dtype=float)
    m = np.maximum((ref_t - datum) * ages * 24.0, 1.0)
    if len(ages) < 2:
        return -83.8, 31.1
    b, a = np.polyfit(np.log10(m), strengths, 1)
    return float(a), float(b)


def predict_strength(maturity, a, b):
    return np.maximum(0.0, a + b * np.log10(np.maximum(maturity, 1.0)))


def maturity_at_age(df: pd.DataFrame, age_h: float, datum: float, ref_t: float) -> float:
    """Maturity at a given age; extrapolates beyond the dataset using the assumed curing temp."""
    last_h = float(df["elapsed"].iloc[-1])
    if age_h <= last_h:
        return float(np.interp(age_h, df["elapsed"], df["maturity"]))
    return float(df["maturity"].iloc[-1]) + (age_h - last_h) * max(ref_t - datum, 0.0)


def simulate_df() -> pd.DataFrame:
    """Demo dataset (48 h, hourly) used until a real CSV is uploaded."""
    n = 49
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    h = np.arange(n)
    core = 30 + 28 * (1 - np.exp(-h / 11.0)) + 1.2 * np.sin(h / 3.0)
    surface = core - 6 - 1.0 * np.cos(h / 4.0)
    ambient = 29 + 12 * (1 - np.exp(-h / 20.0)) + 1.0 * np.sin(h / 5.0)
    return pd.DataFrame(
        {"ts": [now - timedelta(hours=int(n - 1 - i)) for i in h], "core": core, "surface": surface, "ambient": ambient}
    )


def normalize_df(raw: pd.DataFrame) -> pd.DataFrame:
    """Map arbitrary CSV / Supabase column names to ts, core, surface, ambient."""
    cols = {c.lower().strip(): c for c in raw.columns}

    def pick(*names):
        for n in names:
            for lc, orig in cols.items():
                if n in lc:
                    return orig
        return None

    ts_c = pick("timestamp", "datetime", "created_at", "time", "date", "ts")
    core_c = pick("core", "concrete_avg_temp", "slab_temp", "temp")
    surf_c = pick("surface")
    amb_c = pick("ambient", "air")
    if core_c is None:
        raise ValueError("CSV needs a core / concrete temperature column (e.g. 'core_temp').")

    out = pd.DataFrame()
    ts = pd.to_datetime(raw[ts_c], errors="coerce") if ts_c else pd.Series([pd.NaT] * len(raw))
    if ts.isna().all():
        ts = pd.Series([datetime.now() - timedelta(hours=len(raw) - 1 - i) for i in range(len(raw))])
    out["ts"] = ts
    out["core"] = pd.to_numeric(raw[core_c], errors="coerce")
    out["surface"] = pd.to_numeric(raw[surf_c], errors="coerce") if surf_c else np.nan
    out["ambient"] = pd.to_numeric(raw[amb_c], errors="coerce") if amb_c else np.nan
    return out.dropna(subset=["ts", "core"]).sort_values("ts").reset_index(drop=True)


def get_data() -> pd.DataFrame:
    """Uploaded CSV  ->  Supabase  ->  simulated demo data. Adds elapsed, maturity, strength."""
    base = None
    if st.session_state.raw_df is not None:
        base = st.session_state.raw_df
    elif supabase is not None:
        try:
            r = supabase.table("strength_view").select("*").order("created_at", desc=True).limit(2000).execute()
            if r.data:
                base = normalize_df(pd.DataFrame(r.data).iloc[::-1])
        except Exception:
            base = None
    if base is None or base.empty:
        base = simulate_df()

    df = base.copy()
    dt = df["ts"].diff().dt.total_seconds().div(3600.0)
    dt = dt.fillna(dt.median() if dt.notna().any() else 1.0).clip(lower=0)
    datum = st.session_state.datum_temp
    df["elapsed"] = dt.cumsum() - dt.iloc[0]
    df["maturity"] = ((df["core"] - datum).clip(lower=0) * dt).cumsum()
    a, b = fit_curve(st.session_state.cube_data, datum, st.session_state.ref_temp)
    df["strength"] = predict_strength(df["maturity"].values, a, b)
    df.attrs["curve"] = (a, b)
    return df


def alert_state(temp: float):
    thr, typ = st.session_state.alert_temp, st.session_state.alert_type
    triggered = temp > thr if typ == "Above" else temp < thr
    return triggered, thr, typ


def send_sms(phone: str, message: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    key = os.environ.get("FAST2SMS_API_KEY", "").strip()
    if key:
        try:
            r = requests.post(
                "https://www.fast2sms.com/dev/bulkV2",
                headers={"authorization": key},
                data={"route": "q", "message": message, "language": "english", "flash": 0, "numbers": digits[-10:]},
                timeout=8,
            )
            return "Delivered" if r.status_code == 200 else f"Gateway status {r.status_code}"
        except Exception as e:
            return f"Error: {e}"
    return "No SMS gateway configured"


def handle_alert(temp: float):
    triggered, thr, typ = alert_state(temp)
    if not triggered:
        st.session_state.last_alert_key = None
        return
    key = f"{typ}-{int(thr)}-{int(temp)}"
    if st.session_state.sms_enabled and st.session_state.phone and st.session_state.last_alert_key != key:
        st.session_state.last_alert_key = key
        msg = f"Concrete alert: core temp {temp:.1f}C is {typ.lower()} limit {thr:.0f}C."
        status = send_sms(st.session_state.phone, msg)
        st.session_state.sms_log.insert(0, {"Time": datetime.now().strftime("%d %b %H:%M"), "To": st.session_state.phone, "Status": status, "Message": msg})


# ============================================================== PLOTLY HELPERS (light theme)
def style_fig(fig, height=330, xtitle=None, ytitle=None):
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#475569", size=11),
        legend=dict(orientation="h", y=1.12, x=0),
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor="#eef2f7", zeroline=False, title=xtitle)
    fig.update_yaxes(gridcolor="#eef2f7", zeroline=False, title=ytitle)
    return fig


def fig_live(df, height=330):
    fig = go.Figure()
    for col, name, color in [("core", "Core Temp (°C)", "#ef4444"), ("surface", "Surface Temp (°C)", "#3b82f6"), ("ambient", "Ambient Temp (°C)", "#22c55e")]:
        if df[col].notna().any():
            fig.add_trace(go.Scatter(x=df["elapsed"], y=df[col], name=name, mode="lines", line=dict(color=color, width=2.4)))
    fig.add_hline(y=st.session_state.alert_temp, line_dash="dash", line_color="#f59e0b", annotation_text="Alert limit")
    return style_fig(fig, height, "Time (hours)", "Temperature (°C)")


def comparison_df(df):
    a, b = df.attrs["curve"]
    rows = []
    for age in CUBE_AGES:
        cube = st.session_state.cube_data.get(age)
        m = maturity_at_age(df, age * 24.0, st.session_state.datum_temp, st.session_state.ref_temp)
        live = float(predict_strength(m, a, b))
        rows.append({"Age (Days)": age, "Live Strength (MPa)": round(live, 1), "Cube Strength (MPa)": cube, "Difference": round(live - cube, 1) if cube is not None else None})
    return pd.DataFrame(rows)


def fig_compare(cmp, height=330):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cmp["Age (Days)"], y=cmp["Live Strength (MPa)"], name="Live Monitoring (MPa)", mode="lines+markers+text",
                             text=cmp["Live Strength (MPa)"], textposition="bottom right", line=dict(color="#2563eb", width=2.4), marker=dict(size=8)))
    fig.add_trace(go.Scatter(x=cmp["Age (Days)"], y=cmp["Cube Strength (MPa)"], name="Cube Test (MPa)", mode="lines+markers+text",
                             text=cmp["Cube Strength (MPa)"], textposition="top left", line=dict(color="#f97316", width=2.4), marker=dict(size=8, symbol="square")))
    fig.update_xaxes(tickvals=CUBE_AGES)
    return style_fig(fig, height, "Time (Days)", "Strength (MPa)")


# ============================================================== REUSABLE CARDS
def card_upload(ctx):
    with st.container(border=True):
        st.markdown('<div class="card-title">1. Upload Dataset</div>', unsafe_allow_html=True)
        f = st.file_uploader("Choose CSV file", type=["csv"], key=f"{ctx}_upl", label_visibility="collapsed")
        if f is not None and st.session_state.upload_name != f.name:
            try:
                st.session_state.raw_df = normalize_df(pd.read_csv(f))
                st.session_state.upload_name = f.name
            except Exception as e:
                st.error(f"Could not read file: {e}")
        if st.session_state.upload_name:
            st.success(f"Dataset uploaded successfully! ({st.session_state.upload_name})")
        else:
            st.caption("Using demo data. Upload a CSV with core / surface / ambient temperatures.")


def card_grade(ctx):
    with st.container(border=True):
        st.markdown('<div class="card-title">2. Select Concrete Grade</div>', unsafe_allow_html=True)
        g = st.selectbox("Grade", list(GRADES), index=list(GRADES).index(st.session_state.grade), key=f"{ctx}_grade", label_visibility="collapsed")
        st.session_state.grade = g
        st.caption(f"Target 28-day strength: **{GRADES[g]:.0f} MPa**")


def card_alert(ctx):
    with st.container(border=True):
        st.markdown('<div class="card-title">3. Set Temperature Alert</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        st.session_state.alert_temp = c1.number_input("Alert Temperature (°C)", value=float(st.session_state.alert_temp), step=1.0, key=f"{ctx}_at")
        st.session_state.alert_type = c2.selectbox("Alert Type", ["Above", "Below"], index=["Above", "Below"].index(st.session_state.alert_type), key=f"{ctx}_aty")


def card_cube_input(ctx):
    with st.container(border=True):
        st.markdown('<div class="card-title">4. Add Cube Test Data (Compression)</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-note">Enter cube test strength values (MPa) at different days</div>', unsafe_allow_html=True)
        cols = st.columns(len(CUBE_AGES) + 1)
        vals = {}
        for i, age in enumerate(CUBE_AGES):
            vals[age] = cols[i].number_input(f"{age} Days", min_value=0.0, value=float(st.session_state.cube_data.get(age, 0.0)), step=0.1, key=f"{ctx}_cube_{age}")
        cols[-1].markdown("<div style='height:1.65rem'></div>", unsafe_allow_html=True)
        if cols[-1].button("Save", type="primary", key=f"{ctx}_save", use_container_width=True):
            st.session_state.cube_data = {a: v for a, v in vals.items() if v > 0}
            st.session_state.cube_saved = True
            st.rerun()


def card_cube_table():
    with st.container(border=True):
        st.markdown('<div class="card-title">Cube Test Data Entry</div>', unsafe_allow_html=True)
        rows = [{"Age (Days)": a, "Compressive Strength (MPa)": v, "Status": "✔ Added"} for a, v in sorted(st.session_state.cube_data.items())]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        if st.session_state.cube_saved:
            st.markdown('<div class="note-ok">✔ Cube test data saved successfully!</div>', unsafe_allow_html=True)


def kpi(icon, label, value, unit, sub, tone):
    st.markdown(
        f'<div class="kpi kpi-{tone}"><div class="kpi-ic">{icon}</div><div>'
        f'<div class="kpi-label">{label}</div><div class="kpi-val">{value}<small>{unit}</small></div>'
        f'<div class="kpi-sub">{sub}</div></div></div>',
        unsafe_allow_html=True,
    )


def kpi_row(df):
    latest = df.iloc[-1]
    triggered, thr, typ = alert_state(float(latest["core"]))
    handle_alert(float(latest["core"]))
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        badge = '<span class="badge badge-bad">Alert</span>' if triggered else '<span class="badge badge-ok">Normal</span>'
        kpi("🌡️", "Current Core Temperature", f"{latest['core']:.1f}", " °C", badge, "blue")
    with k2:
        kpi("🔗", "Maturity Index", f"{latest['maturity']:.1f}", " °C·hr", "(Degree Celsius Hour)", "green")
    with k3:
        kpi("💪", "Predicted Strength (Live)", f"{latest['strength']:.1f}", " MPa", "(from maturity index)", "purple")
    with k4:
        if triggered:
            kpi("⚠️", "Temperature Alert", "Alert", "", f"Core temp is {typ.lower()} {thr:.0f} °C", "red")
        else:
            kpi("⚠️", "Temperature Alert", "Normal", "", "No temperature alert", "amber")


def card_monitoring_table(df):
    with st.container(border=True):
        st.markdown('<div class="card-title">Latest Monitoring Data</div>', unsafe_allow_html=True)
        step = max(1, int(round(4 / max(df["elapsed"].diff().median() or 1, 0.25))))
        t = df.iloc[::-1].iloc[::step].head(5)
        triggered = [alert_state(v)[0] for v in t["core"]]
        out = pd.DataFrame({
            "Date & Time": t["ts"].dt.strftime("%Y-%m-%d %H:%M"),
            "Core Temp (°C)": t["core"].round(1),
            "Surface Temp (°C)": t["surface"].round(1),
            "Ambient Temp (°C)": t["ambient"].round(1),
            "Maturity (°C·hr)": t["maturity"].round(1),
            "Predicted Strength (MPa)": t["strength"].round(1),
            "Status": ["Alert" if x else "Normal" for x in triggered],
        })
        st.dataframe(out, hide_index=True, use_container_width=True)


def card_calculator(ctx):
    with st.container(border=True):
        st.markdown('<div class="card-title">🧮 Maturity & Strength Calculator</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        temp = c1.number_input("Temperature (°C)", value=60.0, step=1.0, key=f"{ctx}_ct")
        hrs = c2.number_input("Time (hours)", value=24.0, min_value=0.0, step=1.0, key=f"{ctx}_ch")
        if st.button("Calculate", type="primary", use_container_width=True, key=f"{ctx}_calc"):
            a, b = fit_curve(st.session_state.cube_data, st.session_state.datum_temp, st.session_state.ref_temp)
            m = max(temp - st.session_state.datum_temp, 0.0) * hrs
            st.session_state.calc_result = (m, float(predict_strength(m, a, b)))
        res = st.session_state.calc_result
        if res:
            r1, r2 = st.columns(2)
            r1.markdown(f'<div class="calc-out" style="background:#eafaf2;border-color:#c4ecd6"><div class="l" style="color:#15803d">Maturity Index</div><div class="v">{res[0]:,.0f} °C·hr</div></div>', unsafe_allow_html=True)
            r2.markdown(f'<div class="calc-out" style="background:#f3efff;border-color:#ddd3fb"><div class="l" style="color:#6d28d9">Estimated Strength (MPa)</div><div class="v">{res[1]:.1f} MPa</div></div>', unsafe_allow_html=True)


def card_strength_table(cmp):
    with st.container(border=True):
        st.markdown('<div class="card-title">📊 Strength in MPa (Graph Tab)</div>', unsafe_allow_html=True)
        st.dataframe(cmp, hide_index=True, use_container_width=True)
        st.markdown('<div class="note-ok">✔ Live monitoring strength is slightly lower than cube test values, which is normal due to real-time conditions.</div>', unsafe_allow_html=True)


# ============================================================== PAGES
def page_dashboard():
    c1, c2, c3, c4 = st.columns([1.15, 1, 1.15, 2.1])
    with c1: card_upload("d")
    with c2: card_grade("d")
    with c3: card_alert("d")
    with c4: card_cube_input("d")
    df = get_data()
    cmp = comparison_df(df)
    st.write("")
    kpi_row(df)
    st.write("")
    g1, g2, g3 = st.columns([1.25, 1.15, 1])
    with g1:
        with st.container(border=True):
            st.markdown('<div class="card-title">Live Sensor Data (Temperature)</div>', unsafe_allow_html=True)
            st.plotly_chart(fig_live(df), use_container_width=True)
    with g2:
        with st.container(border=True):
            st.markdown('<div class="card-title">Strength Comparison</div>', unsafe_allow_html=True)
            st.plotly_chart(fig_compare(cmp), use_container_width=True)
    with g3:
        card_cube_table()
    st.write("")
    b1, b2, b3 = st.columns([1.6, 1, 1.1])
    with b1: card_monitoring_table(df)
    with b2: card_calculator("d")
    with b3: card_strength_table(cmp)


def page_live():
    def body():
        df = get_data()
        kpi_row(df)
        st.write("")
        with st.container(border=True):
            st.markdown('<div class="card-title">Live Sensor Data (Temperature)</div>', unsafe_allow_html=True)
            st.plotly_chart(fig_live(df, 420), use_container_width=True)
        g1, g2 = st.columns(2)
        with g1:
            with st.container(border=True):
                st.markdown('<div class="card-title">Maturity Index (°C·hr)</div>', unsafe_allow_html=True)
                fig = go.Figure(go.Scatter(x=df["elapsed"], y=df["maturity"], mode="lines", line=dict(color="#16a34a", width=2.4), fill="tozeroy", fillcolor="rgba(22,163,74,.08)"))
                st.plotly_chart(style_fig(fig, 300, "Time (hours)", "°C·hr"), use_container_width=True)
        with g2:
            with st.container(border=True):
                st.markdown('<div class="card-title">Predicted Strength (MPa)</div>', unsafe_allow_html=True)
                fig = go.Figure(go.Scatter(x=df["elapsed"], y=df["strength"], mode="lines", line=dict(color="#7c3aed", width=2.4), fill="tozeroy", fillcolor="rgba(124,58,237,.08)"))
                st.plotly_chart(style_fig(fig, 300, "Time (hours)", "MPa"), use_container_width=True)
        card_monitoring_table(df)
        with st.expander("Export raw data"):
            st.download_button("⬇ Download CSV", df.to_csv(index=False).encode(), "monitoring_data.csv", "text/csv")

    if st.session_state.auto_refresh:
        st.fragment(run_every=st.session_state.refresh_s)(body)()
    else:
        body()


def page_compare():
    df = get_data()
    cmp = comparison_df(df)
    g1, g2 = st.columns([1.5, 1])
    with g1:
        with st.container(border=True):
            st.markdown('<div class="card-title">Strength Comparison – Live vs Cube Test</div>', unsafe_allow_html=True)
            st.plotly_chart(fig_compare(cmp, 420), use_container_width=True)
    with g2:
        card_strength_table(cmp)
    card_cube_input("c")


def page_prediction():
    df = get_data()
    kpi_row(df)
    st.write("")
    p1, p2 = st.columns([1.6, 1])
    with p1:
        with st.container(border=True):
            st.markdown('<div class="card-title">Strength Development Curve (calibrated from cube tests)</div>', unsafe_allow_html=True)
            a, b = df.attrs["curve"]
            m = np.linspace(100, max(30000, df["maturity"].max()), 200)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=m, y=predict_strength(m, a, b), name="Fitted curve", line=dict(color="#2563eb", width=2.4)))
            cm = [(st.session_state.ref_temp - st.session_state.datum_temp) * d * 24 for d in st.session_state.cube_data]
            fig.add_trace(go.Scatter(x=cm, y=list(st.session_state.cube_data.values()), name="Cube tests", mode="markers", marker=dict(color="#f97316", size=10, symbol="square")))
            fig.add_hline(y=GRADES[st.session_state.grade], line_dash="dash", line_color="#16a34a", annotation_text=f"{st.session_state.grade} target")
            st.plotly_chart(style_fig(fig, 400, "Maturity (°C·hr)", "Strength (MPa)"), use_container_width=True)
            st.caption(f"Model: S = {a:.2f} + {b:.2f} · log₁₀(M)")
    with p2:
        card_calculator("p")
        card_strength_table(comparison_df(df))


def page_upload():
    card_upload("u")
    df = get_data()
    with st.container(border=True):
        st.markdown('<div class="card-title">Dataset Preview</div>', unsafe_allow_html=True)
        st.dataframe(df.head(200), hide_index=True, use_container_width=True)
        st.caption(f"{len(df)} rows · expected columns: timestamp, core_temp, surface_temp, ambient_temp")
        if st.session_state.raw_df is not None and st.button("Clear uploaded dataset"):
            st.session_state.raw_df, st.session_state.upload_name = None, None
            st.rerun()


def page_alerts():
    df = get_data()
    c1, c2 = st.columns([1, 1.6])
    with c1:
        card_alert("a")
        with st.container(border=True):
            st.markdown('<div class="card-title">SMS Notifications</div>', unsafe_allow_html=True)
            st.session_state.sms_enabled = st.toggle("Enable SMS alerts", value=st.session_state.sms_enabled, key="a_sms")
            st.session_state.phone = st.text_input("Mobile number", value=st.session_state.phone, placeholder="+91 98765 43210", key="a_phone")
            st.caption("Set FAST2SMS_API_KEY in your environment to send real SMS.")
    with c2:
        kpi_row(df)
        st.write("")
        with st.container(border=True):
            st.markdown('<div class="card-title">Core Temperature vs Alert Limit</div>', unsafe_allow_html=True)
            st.plotly_chart(fig_live(df, 320), use_container_width=True)
        with st.container(border=True):
            st.markdown('<div class="card-title">Alert History</div>', unsafe_allow_html=True)
            if st.session_state.sms_log:
                st.dataframe(pd.DataFrame(st.session_state.sms_log), hide_index=True, use_container_width=True)
            else:
                st.caption("No alerts sent yet.")


def page_cube():
    c1, c2 = st.columns([1.4, 1])
    with c1:
        card_cube_input("t")
        df = get_data()
        with st.container(border=True):
            st.markdown('<div class="card-title">Cube Strength vs Age</div>', unsafe_allow_html=True)
            cd = st.session_state.cube_data
            fig = go.Figure(go.Bar(x=[f"{a} d" for a in cd], y=list(cd.values()), marker_color="#f97316", text=list(cd.values()), textposition="outside"))
            st.plotly_chart(style_fig(fig, 320, "Age", "MPa"), use_container_width=True)
    with c2:
        card_cube_table()


def page_settings():
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown('<div class="card-title">Maturity Settings</div>', unsafe_allow_html=True)
            st.session_state.datum_temp = st.number_input("Datum temperature (°C)", value=float(st.session_state.datum_temp), step=1.0, key="s_datum", help="Nurse-Saul datum. Use 0 to match T × t; -10 is also common.")
            st.session_state.ref_temp = st.number_input("Assumed avg curing temp beyond dataset (°C)", value=float(st.session_state.ref_temp), step=0.5, key="s_ref")
            st.session_state.auto_refresh = st.toggle("Auto-refresh Live Monitoring", value=st.session_state.auto_refresh, key="s_auto")
            st.session_state.refresh_s = st.slider("Refresh interval (seconds)", 5, 60, int(st.session_state.refresh_s), key="s_ref_s")
    with c2:
        with st.container(border=True):
            st.markdown('<div class="card-title">Project & Operator</div>', unsafe_allow_html=True)
            st.session_state.project = st.text_input("Project name", value=st.session_state.project, key="s_proj")
            st.session_state.operator = st.text_input("Operator", value=st.session_state.operator, key="s_op")
            st.session_state.phone = st.text_input("Mobile number (SMS)", value=st.session_state.phone, key="s_ph")
            st.session_state.sms_enabled = st.toggle("Enable SMS alerts", value=st.session_state.sms_enabled, key="s_sms")
        if st.button("Sign out", use_container_width=True):
            try:
                if supabase:
                    supabase.auth.sign_out()
            except Exception:
                pass
            st.session_state.user = None
            st.rerun()


PAGE_FUNCS = {
    "Dashboard": page_dashboard,
    "Live Monitoring": page_live,
    "Cube Test Comparison": page_compare,
    "Strength Prediction": page_prediction,
    "Upload Dataset": page_upload,
    "Temperature Alerts": page_alerts,
    "Cube Test Data": page_cube,
    "Settings": page_settings,
}
PAGE_SUBTITLE = {
    "Dashboard": "Monitor live sensor data, compare with cube test results and track maturity & strength.",
    "Live Monitoring": "Real-time temperature, maturity and predicted strength from the embedded sensors.",
    "Cube Test Comparison": "Compare maturity-based live strength against lab cube compression results.",
    "Strength Prediction": "Estimate strength from maturity and explore the calibrated strength curve.",
    "Upload Dataset": "Load a CSV of sensor readings to drive the dashboard.",
    "Temperature Alerts": "Configure temperature limits and SMS notifications.",
    "Cube Test Data": "Record and review compression test results.",
    "Settings": "Maturity method, refresh behaviour and operator details.",
}


# ============================================================== AUTH SCREEN
def auth_screen():
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        st.write("")
        st.markdown(
            '<div style="text-align:center;margin:1.5rem 0 1rem"><div class="brand-logo" style="margin:auto 0;display:inline-flex;width:64px;height:64px;font-size:32px">🧱</div>'
            '<h1 style="margin:.6rem 0 0;font-weight:800;color:#0b1b3a;font-size:1.7rem">IoT Based Concrete Curing<br>& Strength Monitoring System</h1>'
            '<p style="color:#64748b;margin:.3rem 0 0">Smarter Curing | Stronger Structures</p></div>',
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            t1, t2 = st.columns(2)
            if t1.button("Sign In", use_container_width=True, type="primary" if st.session_state.auth_mode == "Sign In" else "secondary"):
                st.session_state.auth_mode = "Sign In"; st.rerun()
            if t2.button("Create Account", use_container_width=True, type="primary" if st.session_state.auth_mode == "Create Account" else "secondary"):
                st.session_state.auth_mode = "Create Account"; st.rerun()

            if st.session_state.auth_mode == "Sign In":
                email = st.text_input("Email", placeholder="engineer@site.com")
                pw = st.text_input("Password", type="password")
                if st.button("Access Dashboard →", type="primary", use_container_width=True):
                    if not supabase:
                        st.error("Supabase is not configured. Use Demo Sign-In below.")
                    else:
                        try:
                            r = supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": pw})
                            st.session_state.user = r.user
                            st.rerun()
                        except Exception as e:
                            st.error(f"Login failed: {e}")
                if st.button("Quick Demo Sign-In", use_container_width=True):
                    st.session_state.user = {"email": "demo@site.com"}
                    st.rerun()
            else:
                name = st.text_input("Full name")
                email = st.text_input("Email address")
                phone = st.text_input("Mobile number (for SMS alerts)")
                pw = st.text_input("Password", type="password")
                if st.button("Create Account", type="primary", use_container_width=True, key="create_btn"):
                    if not supabase:
                        st.error("Supabase is not configured, so accounts can't be created.")
                    else:
                        try:
                            supabase.auth.sign_up({"email": email.strip().lower(), "password": pw})
                            st.session_state.operator, st.session_state.phone = name or "Site Engineer", phone
                            st.success("Account created. Check your email to confirm, then sign in.")
                            st.session_state.auth_mode = "Sign In"
                        except Exception as e:
                            st.error(f"Registration failed: {e}")


if st.session_state.user is None:
    auth_screen()
    st.stop()


# ============================================================== SIDEBAR
def goto(p):
    st.session_state.page = p


with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="brand-logo">🧱</div><div class="brand-title">IoT Based Concrete<br>Curing & Strength<br>Monitoring System</div></div>'
        '<div class="brand-sub">Smarter Curing &nbsp;|&nbsp; Stronger Structures</div>',
        unsafe_allow_html=True,
    )
    current = st.session_state.page
    for name, icon in SIDEBAR:
        active = current == name or (name == "Dashboard" and current in ("Live Monitoring", "Cube Test Comparison") and False)
        st.button(f"{icon}   {name}", key=f"nav_{name}", use_container_width=True,
                  type="primary" if active else "secondary", on_click=goto, args=(name,))
    st.markdown("<div style='height:2.5rem'></div>", unsafe_allow_html=True)
    st.markdown(
        f'<div class="side-box">Concrete Grade<br><b>{st.session_state.grade}</b></div>'
        f'<div class="side-box" style="font-size:.78rem">Project: <b style="font-size:.82rem">{st.session_state.project}</b><br>'
        f'Created by: <b style="font-size:.82rem">{st.session_state.operator}</b></div>',
        unsafe_allow_html=True,
    )

# ============================================================== HEADER + TOP TABS
page = st.session_state.page


def on_top_nav(key):
    st.session_state.page = TAB_TO_PAGE[st.session_state[key]]


tab_key = f"topnav_{page}"
top_left, top_right = st.columns([5, 1.2])
with top_left:
    st.radio(
        "top-nav", TOP_TABS, horizontal=True, label_visibility="collapsed",
        index=TOP_TABS.index(PAGE_TO_TAB[page]) if page in PAGE_TO_TAB else None,
        key=tab_key, on_change=on_top_nav, args=(tab_key,),
    )
with top_right:
    st.markdown(f"<div style='text-align:right;color:#475569;font-size:.85rem;padding-top:.5rem'>👤 {st.session_state.operator}</div>", unsafe_allow_html=True)

_df_hdr = get_data()
h1, h2, h3 = st.columns([5, 1.3, 1.2])
with h1:
    title = "Concrete Curing & Strength Monitoring Dashboard" if page == "Dashboard" else page
    st.markdown(f'<h1 class="page-title">{title}</h1><p class="page-sub">{PAGE_SUBTITLE[page]}</p>', unsafe_allow_html=True)
with h2:
    st.markdown(f'<div class="upd">Last Updated<br><b>{_df_hdr["ts"].iloc[-1].strftime("%Y-%m-%d %H:%M")}</b></div>', unsafe_allow_html=True)
with h3:
    st.markdown('<div style="text-align:right"><span class="pill-online">✔ System Online</span></div>', unsafe_allow_html=True)
st.write("")

# ============================================================== ROUTER
PAGE_FUNCS[page]()
