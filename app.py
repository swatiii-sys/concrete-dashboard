"""
IoT Based Concrete Curing & Strength Monitoring System.
Professional multi-tab Streamlit dashboard (Home, Dashboard, Upload, Alerts, Cube Tests, Reports, Settings).

Run:  streamlit run app.py
"""
import os
import io
import time
import hashlib
import html as _html
import json
import sqlite3
from pathlib import Path
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
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================== SUPABASE (optional, keys from environment ONLY)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().strip('"').strip("'")
SUPABASE_KEY = (os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_KEY", "")).strip().strip('"').strip("'")
try:
    SUPABASE_URL = SUPABASE_URL or str(st.secrets.get("SUPABASE_URL", "")).strip()
    SUPABASE_KEY = SUPABASE_KEY or str(st.secrets.get("SUPABASE_SECRET_KEY", st.secrets.get("SUPABASE_KEY", ""))).strip()
except Exception:
    pass
supabase = None
if create_client and SUPABASE_URL.startswith("https://") and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        supabase = None

def secret_or_env(name, default=""):
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value).strip()
    except Exception:
        pass
    return os.environ.get(name, default).strip()


DISPLAY_TZ = secret_or_env("DISPLAY_TZ", "Asia/Kolkata")


def get_alert_key():
    return secret_or_env("THINGSPEAK_ALERT_KEY")


def send_email_alert(subject, message):
    key = get_alert_key()
    if not key:
        return "Missing THINGSPEAK_ALERT_KEY"
    try:
        response = requests.post(
            "https://api.thingspeak.com/alerts/send",
            headers={"ThingSpeak-Alerts-API-Key": key},
            json={"subject": subject, "body": message}, timeout=12,
        )
        return "Sent" if response.ok else f"HTTP {response.status_code}: {response.text[:160]}"
    except requests.RequestException as exc:
        return f"Request failed: {exc}"


@st.cache_data(ttl=60, show_spinner=False)
def fetch_thingspeak_alert_history(api_key, count=100):
    """Fetch ThingSpeak Alerts API history (ThingSpeak retains 7 days)."""
    if not api_key:
        return [], "Missing THINGSPEAK_ALERT_KEY"

    try:
        response = requests.get(
            "https://api.thingspeak.com/alerts/history",
            headers={"ThingSpeak-Alerts-API-Key": api_key},
            params={"count": min(max(int(count), 1), 100)},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, list):
            return payload, None
        if isinstance(payload, dict):
            # Be tolerant of wrapped responses if the API format changes.
            for key in ("alerts", "history", "data", "results"):
                if isinstance(payload.get(key), list):
                    return payload[key], None
            return [], "Unexpected ThingSpeak alert-history response format"
        return [], "Unexpected ThingSpeak alert-history response format"

    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        detail = ""
        if exc.response is not None:
            detail = exc.response.text[:250]
        return [], f"ThingSpeak alert-history HTTP {status}: {detail}"
    except (requests.RequestException, ValueError) as exc:
        return [], f"Could not retrieve ThingSpeak alert history: {exc}"


def normalize_alert_history(records):
    """Normalize ThingSpeak camelCase response fields into dashboard columns."""
    rows = []
    for item in records or []:
        if not isinstance(item, dict):
            continue
        requested_at = item.get("requestedAt", item.get("requested_at", ""))
        sent_at = item.get("sentAt", item.get("sent_at", ""))
        subject = item.get("subject", "")
        status = item.get("status", "")
        identity_source = {
            "requested_at": requested_at,
            "sent_at": sent_at,
            "subject": subject,
            "status": status,
        }
        alert_id = hashlib.sha256(
            json.dumps(identity_source, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        rows.append({
            "alert_id": alert_id,
            "requested_at": str(requested_at) if requested_at is not None else None,
            "sent_at": str(sent_at) if sent_at is not None else None,
            "subject": str(subject) if subject is not None else "",
            "status": str(status) if status is not None else "",
            "raw_payload": item,
        })
    return rows


def archive_alert_history_in_supabase(rows):
    """Idempotently archive API records; requires the SQL table supplied with this app."""
    if supabase is None or not rows:
        return False, "Supabase archive is not configured or there are no alerts to save."
    try:
        supabase.table("thingspeak_alert_history").upsert(
            rows, on_conflict="alert_id"
        ).execute()
        return True, f"Archived {len(rows)} ThingSpeak alert record(s) in Supabase."
    except Exception as exc:
        return False, f"Supabase alert archive unavailable: {exc}"


def get_dashboard_alert_history():
    """Return archived records where available, otherwise the live 7-day API history."""
    api_records, api_error = fetch_thingspeak_alert_history(get_alert_key(), 100)
    normalized = normalize_alert_history(api_records)

    archive_message = ""
    if normalized and supabase is not None:
        _, archive_message = archive_alert_history_in_supabase(normalized)

    if supabase is not None:
        try:
            result = (
                supabase.table("thingspeak_alert_history")
                .select("alert_id,requested_at,sent_at,subject,status")
                .order("requested_at", desc=True)
                .limit(500)
                .execute()
            )
            archived = result.data or []
            if archived:
                return pd.DataFrame(archived), api_error, archive_message
        except Exception as exc:
            archive_message = (
                "Could not read Supabase alert archive. Run the supplied "
                f"supabase_alert_history.sql file. Details: {exc}"
            )

    if normalized:
        return pd.DataFrame([
            {k: row.get(k) for k in
             ("requested_at", "sent_at", "subject", "status")}
            for row in normalized
        ]), api_error, archive_message

    return pd.DataFrame(columns=["requested_at", "sent_at", "subject", "status"]), api_error, archive_message


@st.cache_data(ttl=15, show_spinner=False)
def fetch_thingspeak(channel, read_key, field_map, count):
    if not str(channel).isdigit():
        raise ValueError("Enter a numeric ThingSpeak Channel ID")
    params = {"results": int(count)}
    if read_key:
        params["api_key"] = read_key
    response = requests.get(
        f"https://api.thingspeak.com/channels/{channel}/feeds.json",
        params=params, timeout=12,
    )
    if response.status_code in (400, 401, 403):
        raise ValueError(f"ThingSpeak HTTP {response.status_code}: check private channel Read API Key in .streamlit/secrets.toml or Settings.")
    response.raise_for_status()
    payload = response.json()
    feeds = payload.get("feeds", [])
    if not feeds:
        raise ValueError("No channel readings returned; check the channel ID and Read API Key")
    frame = pd.DataFrame(feeds)
    timestamps = pd.to_datetime(frame["created_at"], utc=True, errors="coerce")
    timestamps = timestamps.dt.tz_convert(DISPLAY_TZ).dt.tz_localize(None)
    output = pd.DataFrame({"ts": timestamps})
    for label, field_number in zip(("core", "surface", "ambient"), field_map):
        col = f"field{field_number}"
        output[label] = (pd.to_numeric(frame[col], errors="coerce")
                         if field_number and col in frame.columns else np.nan)
    output = output.dropna(subset=["ts", "core"]).sort_values("ts").drop_duplicates("ts")
    if output.empty:
        raise ValueError("No valid numeric readings in the selected core temperature field")
    return output.reset_index(drop=True)


def load_thingspeak():
    ss = st.session_state
    try:
        df = fetch_thingspeak(str(ss.ts_channel).strip(), str(ss.ts_read_key).strip(),
                              (int(ss.ts_core_field), int(ss.ts_surface_field), int(ss.ts_ambient_field)),
                              int(ss.ts_results))
        if ss.ts_start.strip():
            start = pd.to_datetime(ss.ts_start.strip(), errors="raise")
            df = df[df["ts"] >= start].reset_index(drop=True)
            if df.empty:
                raise ValueError("No readings since the configured pour start; increase the history range")
        ss.ts_error = ""
        return df
    except Exception as exc:
        ss.ts_error = str(exc)
        return None


# ============================================================== CONSTANTS / DEFAULTS
GRADES = {"M20": 20.0, "M25": 25.0, "M30": 30.0, "M35": 35.0, "M40": 40.0}
CUBE_AGES = [3, 7, 14, 21, 28]
DEFAULT_CUBE = {3: 18.5, 7: 27.3, 14: 35.8, 21: 42.1, 28: 48.7}

# Sidebar pages and top-tab pages share one "page" state
SIDEBAR = [
    "Home",
    "Dashboard",
    "Live Monitoring",
    "Upload Dataset",
    "Temperature Alerts",
    "Cube Test Data",
    "Cube Test Comparison",
    "Download Report",
    "Settings",
]

DEFAULT_STATE = {
    "user": None,
    "auth_mode": "Sign In",
    "page": "Home",
    "raw_df": None,
    "upload_raw": None,         # original uploaded table (all columns)
    "report_files": None,      # last generated report downloads
    "source_choice": "ThingSpeak live",            # selected data source
    "upload_name": None,
    "grade": "M25",
    "alert_temp": 60.0,
    "alert_type": "Above",
    "cube_data": {},
    "cube_maturity": {},
    "cube_saved": False,
    "calc_result": None,
    "datum_temp": -10.0,        # User-confirmed Nurse-Saul datum temperature (°C)
    "ref_temp": 27.0,          # retained as a reference setting
    "auto_refresh": True,
    "refresh_s": 15,
    "operator": "Site Engineer",
    "alert_log": [],
    "email_enabled": False,    # ThingSpeak email alerts
    "email_gap_min": 10,       # min minutes between alert emails
    "last_email_ts": 0.0,
    "project": "Slab Curing System",
    "ts_enabled": True,
    "ts_channel": secret_or_env("THINGSPEAK_CHANNEL_ID", "3559934"),
    "ts_read_key": secret_or_env("THINGSPEAK_READ_KEY"),
    "ts_core_field": 1,
    "ts_surface_field": 0,
    "ts_ambient_field": 0,
    "ts_results": 500,
    "ts_start": "",
    "ts_error": "",
    "data_source": "Demo data",
    "ts_stale_minutes": 10,
}
for _k, _v in DEFAULT_STATE.items():
    st.session_state.setdefault(_k, _v)
# Keep the visible source selector separate from the application data value.
st.session_state.setdefault("source_choice_widget", st.session_state.get("source_choice", "ThingSpeak live"))


# Local SQLite persists across browser refresh and application restarts on a persistent disk.
# For cloud deployments with ephemeral disks, configure Supabase for durable storage.
DB_PATH = Path(os.environ.get("CONCRETE_DB_PATH", str(Path(__file__).with_name("concrete_saved.sqlite3"))))

def local_cube_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    conn.execute("""CREATE TABLE IF NOT EXISTS cube_calibration (
        age_days INTEGER PRIMARY KEY,
        compressive_strength_mpa REAL NOT NULL,
        maturity_celsius_hours REAL)""")
    conn.commit()
    return conn

def load_cube_calibration():
    if st.session_state.get("_cube_calibration_loaded"):
        return
    records = []
    try:
        if supabase is not None:
            response = supabase.table("cube_calibration").select("*").execute()
            records = response.data or []
            st.session_state.cube_storage_backend = "Supabase"
        else:
            with local_cube_connection() as conn:
                records = [dict(zip(("age_days", "compressive_strength_mpa", "maturity_celsius_hours"), r)) for r in conn.execute("SELECT age_days, compressive_strength_mpa, maturity_celsius_hours FROM cube_calibration")]
            st.session_state.cube_storage_backend = "Local SQLite (requires persistent disk for cloud hosting)"
        st.session_state.cube_data = {int(r["age_days"]): float(r["compressive_strength_mpa"]) for r in records}
        st.session_state.cube_maturity = {int(r["age_days"]): float(r["maturity_celsius_hours"]) for r in records if r.get("maturity_celsius_hours") is not None and float(r["maturity_celsius_hours"]) > 0}
        st.session_state.cube_saved = bool(records)
        st.session_state._cube_calibration_loaded = True
    except Exception as exc:
        st.session_state.cube_storage_error = str(exc)
        # Do not silently substitute temporary storage for a failed configured cloud database.

def save_cube_calibration():
    rows = [{"age_days": int(age), "compressive_strength_mpa": float(strength),
             "maturity_celsius_hours": float(st.session_state.cube_maturity[age]) if age in st.session_state.cube_maturity else None}
            for age, strength in st.session_state.cube_data.items()]
    try:
        if supabase is not None:
            # Upsert first: never delete previous records if the write fails.
            if rows:
                supabase.table("cube_calibration").upsert(rows, on_conflict="age_days").execute()
            existing = supabase.table("cube_calibration").select("age_days").execute().data or []
            keep = {r["age_days"] for r in rows}
            for r in existing:
                if r["age_days"] not in keep:
                    supabase.table("cube_calibration").delete().eq("age_days", r["age_days"]).execute()
            return True, "Saved permanently to Supabase."
        with local_cube_connection() as conn:
            conn.execute("DELETE FROM cube_calibration")
            conn.executemany("INSERT INTO cube_calibration (age_days, compressive_strength_mpa, maturity_celsius_hours) VALUES (:age_days, :compressive_strength_mpa, :maturity_celsius_hours)", rows)
        return True, "Saved to local SQLite. For cloud hosting, connect Supabase or mount a persistent disk."
    except Exception as exc:
        return False, f"Save failed; records are not confirmed persistent: {exc}"

load_cube_calibration()

# ============================================================== THEME / CSS
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');
:root {
    --ink:#0a2230; --petrol:#0d3b4a; --teal:#0e7c86; --teal-d:#0a5f68; --teal-l:#e3f3f4;
    --heat:#ea580c; --indigo:#4f46e5; --amber:#d97706; --red:#dc2626; --green:#15803d;
    --bg:#edf1f5; --card:#ffffff; --line:#dbe3ea; --text:#12202b; --muted:#5a6b7b;
    color-scheme: light;
}
html, body, [class*="css"] { font-family: 'Manrope', 'Segoe UI', sans-serif; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: var(--bg) !important; color: var(--text) !important;
}
.block-container { padding: 1.4rem 2.2rem 2.5rem 2.2rem; max-width: 1600px; }

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(185deg, #0a2230 0%, #0d3b4a 100%);
    border-right: 1px solid #12495a; min-width: 285px !important;
}
section[data-testid="stSidebar"] * { color: #d5e6ec; }
section[data-testid="stSidebar"] .stButton > button {
    justify-content: flex-start; width: 100%; background: transparent; border: none;
    border-radius: 10px; padding: .62rem .9rem; font-weight: 600; font-size: .9rem;
    color: #cfe3ea; transition: background .15s ease;
}
section[data-testid="stSidebar"] .stButton > button:hover { background: rgba(255,255,255,.09); color: #fff; }
section[data-testid="stSidebar"] .stButton > button[kind="primary"],
section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
    background: linear-gradient(90deg, #0e7c86, #14a3ab); color: #fff;
    box-shadow: 0 6px 16px rgba(14,124,134,.45);
}
.brand { display:flex; gap:12px; align-items:center; padding:.5rem .2rem 0 .2rem; }
.brand-logo { width:46px; height:46px; border-radius:13px; flex-shrink:0;
    background:linear-gradient(135deg,#14a3ab,#0a5f68); display:flex; align-items:center;
    justify-content:center; box-shadow:0 6px 16px rgba(0,0,0,.3); }
.brand-title { font-weight:800; font-size:.92rem; line-height:1.28; color:#fff !important; }
.brand-sub { font-size:.74rem; color:#8fc3cc !important; margin:.7rem .2rem 1.2rem .2rem; }
.side-box { border:1px solid rgba(255,255,255,.14); background:rgba(255,255,255,.05);
    border-radius:12px; padding:.75rem .95rem; margin-top:.8rem; font-size:.8rem; color:#a9c9d1 !important; }
.side-box b { color:#fff !important; font-size:1rem; }

/* ---------- Cards ---------- */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background:#ffffff; border:1px solid var(--line) !important; border-radius:16px !important;
    box-shadow: 0 1px 2px rgba(10,34,48,.05), 0 8px 24px rgba(10,34,48,.05);
}
.card-title { font-weight:800; font-size:1rem; color:var(--ink); margin:0 0 .65rem 0;
    padding-left:.7rem; border-left:4px solid var(--teal); line-height:1.2; }
.card-note { font-size:.78rem; color:var(--muted); margin-bottom:.5rem; }
.page-title { font-size:1.75rem; font-weight:800; color:var(--ink); margin:0; padding:0 !important; letter-spacing:-.02em; }
.page-sub { color:var(--muted); font-size:.92rem; margin:.2rem 0 0 0; }
.pill-online { display:inline-flex; gap:6px; align-items:center; background:var(--teal-l); color:var(--teal-d);
    border:1px solid #b6dfe2; border-radius:999px; padding:.4rem .9rem; font-weight:700; font-size:.8rem; }
.upd { text-align:right; font-size:.72rem; color:var(--muted); line-height:1.3; }
.upd b { color:var(--ink); font-size:.85rem; }

/* ---------- KPI cards ---------- */
.kpi { position:relative; overflow:hidden; display:flex; gap:16px; align-items:center;
    background:#fff; border:1px solid var(--line); border-radius:16px; padding:1.1rem 1.3rem 1.1rem 1.55rem;
    min-height:118px; box-shadow: 0 1px 2px rgba(10,34,48,.05), 0 8px 24px rgba(10,34,48,.06); }
.kpi::before { content:""; position:absolute; left:0; top:0; bottom:0; width:6px; background:var(--accent); }
.kpi-heat   { --accent:#ea580c; }
.kpi-teal   { --accent:#0e7c86; }
.kpi-indigo { --accent:#4f46e5; }
.kpi-amber  { --accent:#d97706; }
.kpi-red    { --accent:#dc2626; }
.kpi-label { font-size:.8rem; font-weight:700; color:var(--accent); }
.kpi-val { font-size:2rem; font-weight:800; color:var(--ink); line-height:1.15; }
.kpi-val small { font-size:1rem; font-weight:700; margin-left:4px; }
.kpi-sub { font-size:.78rem; color:var(--muted); margin-top:.15rem; }
.badge { display:inline-block; padding:.12rem .65rem; border-radius:999px; font-size:.72rem; font-weight:700; }
[data-testid="stMain"] .badge-ok  { background:#d7f3e3; color:#15803d !important; }
[data-testid="stMain"] .badge-bad { background:#fee2e2; color:#b91c1c !important; }
.note-ok { background:#e8f6f7; border:1px solid #b6dfe2; color:#0a5f68; border-radius:10px; padding:.6rem .8rem; font-size:.8rem; margin-top:.5rem; }

/* ---------- Home page ---------- */
.hero { position:relative; overflow:hidden; border-radius:22px; padding:2.3rem 2.6rem; margin-bottom:1.3rem;
    background:
      linear-gradient(rgba(255,255,255,.06) 1px, transparent 1px) 0 0 / 34px 34px,
      linear-gradient(90deg, rgba(255,255,255,.06) 1px, transparent 1px) 0 0 / 34px 34px,
      linear-gradient(120deg, #0a2230 0%, #0d4a58 55%, #0e7c86 100%);
    box-shadow: 0 18px 40px rgba(10,34,48,.28); }
.hero::after { content:""; position:absolute; right:-90px; top:-90px; width:340px; height:340px; border-radius:50%;
    background: radial-gradient(circle, rgba(249,115,22,.55), rgba(249,115,22,0) 65%); pointer-events:none; }
.hero-grid { position:relative; z-index:1; display:flex; justify-content:space-between; align-items:center; gap:2rem; flex-wrap:wrap; }
.hero-main { flex:1 1 440px; }
.hero-title { font-size:2.5rem; font-weight:800; letter-spacing:-.025em; line-height:1.1; margin:0 0 .5rem 0; }
.hero-sub { font-size:1.08rem; font-weight:600; margin:0 0 .8rem 0; }
.hero-text { font-size:.95rem; line-height:1.6; max-width:640px; margin:0 0 1.1rem 0; }
.hero-chips { display:flex; flex-wrap:wrap; gap:.55rem; }
.chip { display:inline-block; padding:.35rem .85rem; border-radius:999px; font-size:.78rem; font-weight:600;
    background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.25); }
.hero-read { flex:0 0 auto; min-width:250px; border-radius:18px; padding:1.2rem 1.5rem;
    background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.25); backdrop-filter: blur(4px); }
.hr-label { font-size:.82rem; font-weight:600; }
.hr-val { font-size:3.1rem; font-weight:800; line-height:1.1; letter-spacing:-.02em; }
.hr-val small { font-size:1.2rem; font-weight:700; margin-left:5px; }
.hr-sub { font-size:.78rem; margin-top:.25rem; }
.hr-list { margin-top:.5rem; }
.hr-list div { font-size:.9rem; font-weight:600; padding:.5rem 0; border-top:1px solid rgba(255,255,255,.22); }
[data-testid="stMain"] .hero, [data-testid="stMain"] .hero * { color:#ffffff !important; }
[data-testid="stMain"] .hero .hero-sub { color:#bfeff2 !important; }
[data-testid="stMain"] .hero .hero-text, [data-testid="stMain"] .hero .hr-label,
[data-testid="stMain"] .hero .hr-sub { color:rgba(255,255,255,.85) !important; }

.section-head { font-size:1.25rem; font-weight:800; color:var(--ink); margin:1.6rem 0 .2rem 0; letter-spacing:-.01em; }
.section-sub { color:var(--muted); font-size:.88rem; margin:0 0 .9rem 0; }
.feat { background:#fff; border:1px solid var(--line); border-radius:16px; padding:1.2rem 1.25rem; height:100%;
    border-top:4px solid var(--accent); box-shadow: 0 1px 2px rgba(10,34,48,.05), 0 8px 24px rgba(10,34,48,.05); }
.feat svg { width:30px; height:30px; stroke:var(--accent); fill:none; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; margin-bottom:.55rem; }
.feat-title { font-weight:800; font-size:.98rem; color:var(--ink); margin-bottom:.3rem; }
.feat-text { font-size:.84rem; color:var(--muted); line-height:1.5; }
.f-heat { --accent:#ea580c; } .f-teal { --accent:#0e7c86; } .f-indigo { --accent:#4f46e5; } .f-amber { --accent:#d97706; }
.flow { display:flex; flex-direction:column; gap:.7rem; }
.flow-step { display:flex; gap:.9rem; align-items:flex-start; background:#f6f9fb; border:1px solid var(--line);
    border-radius:12px; padding:.8rem 1rem; }
.flow-no { flex:0 0 auto; width:30px; height:30px; border-radius:50%; background:var(--teal); color:#fff !important;
    font-weight:800; font-size:.85rem; display:flex; align-items:center; justify-content:center; }
[data-testid="stMain"] .flow-no { color:#ffffff !important; }
.flow-title { font-weight:800; font-size:.92rem; color:var(--ink); }
.flow-text { font-size:.82rem; color:var(--muted); line-height:1.45; }

/* ---------- Inputs / buttons ---------- */
div[data-baseweb="input"], div[data-baseweb="select"] > div { background:#fff !important; border-radius:10px !important; }
.stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"] {
    background: linear-gradient(90deg, #0e7c86, #14a3ab); color:#fff; border:none; border-radius:10px; font-weight:700;
    box-shadow: 0 4px 12px rgba(14,124,134,.3);
}
.stButton > button[kind="primary"]:hover { filter:brightness(1.06); }
[data-testid="stMain"] button[kind="primary"] p, [data-testid="stMain"] button[data-testid="stBaseButton-primary"] p { color:#ffffff !important; }
[data-testid="stMain"] .stDownloadButton button { border-radius:10px; font-weight:700; border:1.5px solid var(--teal) !important; color:var(--teal-d) !important; background:#fff !important; }
[data-testid="stMain"] .stDownloadButton button:hover { background:var(--teal-l) !important; }
[data-testid="stMain"] .stDownloadButton button p { color:var(--teal-d) !important; }
[data-testid="stMain"] [data-testid="stMetric"] { background:#fff; border:1px solid var(--line); border-left:5px solid var(--teal);
    border-radius:14px; padding:.8rem 1rem; box-shadow:0 1px 2px rgba(10,34,48,.05); }
[data-baseweb="tab-highlight"] { background-color: var(--teal) !important; }
[data-testid="stMain"] button[data-baseweb="tab"] p { font-weight:700; }

/* ---------- Readable text everywhere (high contrast) ---------- */
[data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3, [data-testid="stMain"] h4,
[data-testid="stMain"] strong, [data-testid="stMain"] b, [data-testid="stMain"] p,
[data-testid="stMain"] label, [data-testid="stMain"] .stMarkdown, [data-testid="stMain"] .stCaption,
[data-testid="stMain"] [data-testid="stWidgetLabel"] p { color: var(--text) !important; }
[data-testid="stMain"] [data-testid="stCaptionContainer"] *, [data-testid="stMain"] small { color: var(--muted) !important; }
[data-testid="stMain"] .kpi-label { color: var(--accent) !important; }
[data-testid="stMain"] .kpi-val, [data-testid="stMain"] .kpi-val small { color: var(--ink) !important; }
[data-testid="stMain"] .kpi-sub { color: var(--muted) !important; }
[data-testid="stMain"] .card-title, [data-testid="stMain"] .section-head, [data-testid="stMain"] .feat-title,
[data-testid="stMain"] .flow-title, [data-testid="stMain"] .page-title { color: var(--ink) !important; }
[data-testid="stMain"] .section-sub, [data-testid="stMain"] .feat-text, [data-testid="stMain"] .flow-text,
[data-testid="stMain"] .page-sub, [data-testid="stMain"] .upd { color: var(--muted) !important; }
[data-testid="stMain"] input, [data-testid="stMain"] textarea, [data-testid="stMain"] [role="combobox"],
[data-testid="stMain"] [data-baseweb="select"] *, [data-testid="stMain"] [data-baseweb="input"] * {
    color: var(--text) !important; -webkit-text-fill-color: var(--text) !important; background-color:#ffffff !important;
}
[data-testid="stMain"] input::placeholder, [data-testid="stMain"] textarea::placeholder {
    color:#69778e !important; -webkit-text-fill-color:#69778e !important; opacity:1 !important;
}
[data-baseweb="popover"] li, [data-baseweb="popover"] [role="option"], [data-baseweb="popover"] ul {
    background:#ffffff !important; color: var(--text) !important;
}
[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"], [data-testid="stMain"] [data-testid="stExpander"] {
    background:#ffffff !important; border-color: var(--line) !important;
}
[data-testid="stMain"] [data-testid="stFileUploaderDropzone"] { background:#f6fafb !important; border:2px dashed #7fb9bf !important; border-radius:12px; }
[data-testid="stMain"] [data-testid="stFileUploaderDropzone"] * { color:#26344a !important; }
[data-testid="stMain"] [data-testid="stCheckbox"] label, [data-testid="stMain"] [data-testid="stRadio"] label,
[data-testid="stMain"] [data-testid="stSelectbox"] label, [data-testid="stMain"] [data-testid="stNumberInput"] label,
[data-testid="stMain"] [data-testid="stTextInput"] label { color:#26344a !important; }
[data-testid="stMain"] button[kind="secondary"], [data-testid="stMain"] button[data-testid="stBaseButton-secondary"] {
    background:#ffffff !important; color:#1e293b !important; border:1px solid #cbd5e1 !important; border-radius:10px;
}
[data-testid="stMain"] [data-testid="stMetricLabel"] *, [data-testid="stMain"] [data-testid="stMetricValue"] * { color: var(--ink) !important; }
[data-testid="stMain"] hr { border-color: var(--line) !important; }
[data-testid="stMain"] [data-testid="stAlert"] {
    background:#f8fafc !important; border:1px solid #cbd5e1 !important; border-left:4px solid var(--teal) !important; border-radius:12px !important;
}
[data-testid="stMain"] [data-testid="stAlert"] p, [data-testid="stMain"] [data-testid="stAlert"] span,
[data-testid="stMain"] [data-testid="stAlert"] div { color:#263449 !important; }
[data-testid="stMain"] [data-testid="stDataFrame"] *, [data-testid="stMain"] [data-testid="stTable"] * { color:#263449 !important; }
[data-testid="stMain"] [data-testid="stExpander"] summary p { color: var(--text) !important; font-weight:700; }

@media (max-width: 900px) {
    .block-container { padding: 1rem 1rem 2rem 1rem; }
    .kpi { min-height:105px; padding:.9rem .9rem .9rem 1.2rem; }
    .hero { padding:1.5rem 1.3rem; } .hero-title { font-size:1.8rem; }
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================== CORE CALCULATIONS
def fit_curve(cube: dict, cube_maturity: dict):
    """Return actual measured maturity/strength pairs; never synthesize maturity from age."""
    points = []
    for age, strength in cube.items():
        maturity = cube_maturity.get(age)
        if maturity is not None and np.isfinite(maturity) and maturity > 0 and strength > 0:
            points.append((float(maturity), float(strength)))
    points.sort(key=lambda item: item[0])
    if len(points) < 2 or len({p[0] for p in points}) != len(points):
        return np.array([]), np.array([])
    return np.array([p[0] for p in points]), np.array([p[1] for p in points])


def predict_strength(maturity, calibration_m, calibration_s):
    """Piecewise-linear interpolation, restricted to the measured calibration range."""
    values = np.asarray(maturity, dtype=float)
    result = np.full(values.shape, np.nan, dtype=float)
    if len(calibration_m) >= 2:
        valid = np.isfinite(values) & (values >= calibration_m[0]) & (values <= calibration_m[-1])
        result[valid] = np.interp(values[valid], calibration_m, calibration_s)
    return float(result) if result.ndim == 0 else result


# ---- Standard strength-maturity curve (used when cube data is missing) ----------
def standard_curve(maturity, grade_mpa, datum):
    """Typical OPC concrete: S = Su*k*(M-M0)/(1+k*(M-M0)).
    Scaled so that 28 days at 30 C gives about (grade + 6.5) MPa, for any datum temperature."""
    M0 = 100.0
    su = (grade_mpa + 6.5) / 0.89
    k = (0.89 / 0.11) / ((30.0 - datum) * 28 * 24 - M0)
    x = k * np.maximum(np.asarray(maturity, dtype=float) - M0, 0.0)
    return su * x / (1.0 + x)


def cube_scale_factor(cube, cube_maturity, grade_mpa, datum):
    """Even ONE real cube result can adjust the standard curve. Ignores obviously wrong entries."""
    ratios = []
    for age, strength in cube.items():
        m = cube_maturity.get(age)
        if m is not None and np.isfinite(m) and m > 150 and strength > 0:
            base = float(standard_curve(m, grade_mpa, datum))
            if base > 1.0 and 0.5 <= strength / base <= 2.0:
                ratios.append(strength / base)
    return (float(np.median(ratios)) if ratios else 1.0), len(ratios)


def estimate_strength(maturity, cube, cube_maturity, grade_mpa, datum):
    factor, _ = cube_scale_factor(cube, cube_maturity, grade_mpa, datum)
    return standard_curve(maturity, grade_mpa, datum) * factor


def maturity_at_age(df: pd.DataFrame, age_h: float, datum: float, ref_t: float) -> float:
    """Return observed cumulative maturity at an elapsed age; no future extrapolation."""
    if df.empty or age_h < 0 or age_h > float(df["elapsed"].iloc[-1]):
        return np.nan
    return float(np.interp(age_h, df["elapsed"], df["maturity"]))



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
    """Recognize common timestamp/temperature names, including ThingSpeak CSV exports."""
    if raw.empty:
        raise ValueError("The uploaded file is empty.")
    cols = {str(c).strip().lower(): c for c in raw.columns}
    def pick(*names):
        for n in names:
            if n in cols:
                return cols[n]
        for n in names:
            for lc, orig in cols.items():
                if n in lc:
                    return orig
        return None
    ts_c = pick("created_at", "timestamp", "datetime", "date_time", "time", "date", "ts")
    core_c = pick("core_temp", "core_temperature", "concrete_temp_c", "concrete_avg_temp",
                  "slab_temp", "field1", "temperature", "temp", "core")
    surf_c = pick("surface_temp", "field2", "surface")
    amb_c = pick("ambient_temp", "field3", "ambient", "air")
    if core_c is None or ts_c is None:
        raise ValueError(f"The file needs a timestamp column and a core-temperature column. Found: {list(raw.columns)}")
    # Timestamps WITHOUT a timezone (typical Excel / local CSV) are used exactly as written.
    # Timestamps WITH a timezone (e.g. ThingSpeak exports, "+00:00 UTC") are converted to DISPLAY_TZ.
    try:
        parsed = pd.to_datetime(raw[ts_c], errors="coerce")
        naive = getattr(parsed.dt, "tz", None) is None
    except Exception:
        parsed, naive = None, False
    if naive:
        ts = parsed
    else:
        ts = pd.to_datetime(raw[ts_c], errors="coerce", utc=True)
        ts = ts.dt.tz_convert(DISPLAY_TZ).dt.tz_localize(None)
    out = pd.DataFrame({"ts": ts, "core": pd.to_numeric(raw[core_c], errors="coerce")})
    out["surface"] = pd.to_numeric(raw[surf_c], errors="coerce") if surf_c else np.nan
    out["ambient"] = pd.to_numeric(raw[amb_c], errors="coerce") if amb_c else np.nan
    out = out.dropna(subset=["ts", "core"]).sort_values("ts").reset_index(drop=True)
    if out.empty:
        raise ValueError("The file has no rows with both a valid timestamp and a numeric core temperature.")
    return out


def get_data(source=None) -> pd.DataFrame:
    """Explicit source selection prevents live ThingSpeak from masking uploaded CSV."""
    ss = st.session_state
    base = None
    ss.ts_error = ""
    source = source or ss.source_choice
    if source == "Uploaded File":
        if ss.raw_df is not None and not ss.raw_df.empty:
            base = ss.raw_df
            ss.data_source = "File upload"
        else:
            ss.data_source = "No file uploaded"
    elif source == "ThingSpeak live":
        if ss.ts_enabled and str(ss.ts_channel).strip():
            base = load_thingspeak()
            ss.data_source = "ThingSpeak" if base is not None else "ThingSpeak unavailable"
        else:
            ss.ts_error = "Enable ThingSpeak and enter the Channel ID in Settings."
            ss.data_source = "ThingSpeak unavailable"
    elif source == "Supabase" and supabase is not None:
        try:
            r = supabase.table("strength_view").select("*").order("created_at", desc=True).limit(2000).execute()
            if r.data:
                base = normalize_df(pd.DataFrame(r.data).iloc[::-1])
        except Exception as exc:
            ss.ts_error = f"Supabase: {exc}"
        ss.data_source = "Supabase" if base is not None else "Supabase unavailable"
    elif source == "Demo (sample data)":
        base = simulate_df()
        ss.data_source = "Demo data"
    else:
        ss.data_source = "No data"
    if base is None or base.empty:
        return pd.DataFrame(columns=["ts","core","surface","ambient","elapsed","maturity","strength"])
    df = base.copy().sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    dt = df["ts"].diff().dt.total_seconds().div(3600).fillna(0).clip(lower=0)
    df["elapsed"] = (df["ts"] - df["ts"].iloc[0]).dt.total_seconds() / 3600
    datum = ss.datum_temp
    average_temp = (df["core"] + df["core"].shift(1)) / 2
    df["maturity"] = ((average_temp - datum).clip(lower=0).fillna(0) * dt).cumsum()
    calibration_m, calibration_s = fit_curve(ss.cube_data, ss.cube_maturity)
    cal = predict_strength(df["maturity"].values, calibration_m, calibration_s)
    est = estimate_strength(df["maturity"].values, ss.cube_data, ss.cube_maturity, GRADES[ss.grade], datum)
    df["strength"] = np.where(np.isfinite(cal), cal, est)
    df["strength_basis"] = np.where(np.isfinite(cal), "Cube-calibrated", "Standard curve")
    df.attrs["curve"] = (calibration_m, calibration_s)
    return df

def data_ready(df):
    if df.empty:
        ss = st.session_state
        if ss.ts_error:
            st.error(f"Connection issue: {ss.ts_error}")
        if ss.source_choice == "ThingSpeak live":
            st.info("No live readings available. Check the Read API Key in Settings and confirm the ESP32 has published data. No demo readings are substituted.")
        elif ss.source_choice == "Uploaded File":
            st.info("Upload a CSV or Excel file on the Upload Dataset page to display its graphs and readings.")
        else:
            st.info("No readings available for this source.")
        return False
    return True


def source_banner(df):
    ss = st.session_state
    if ss.source_choice == "ThingSpeak live" and ss.ts_enabled and ss.ts_error:
        st.warning(f"ThingSpeak connection issue: {ss.ts_error}. Displaying {ss.data_source} instead; this is NOT a live ThingSpeak feed.")
    if ss.data_source == "ThingSpeak":
        latest = df["ts"].iloc[-1]
        age = (pd.Timestamp.now(tz=DISPLAY_TZ).tz_localize(None) - latest).total_seconds() / 60
        if age > ss.ts_stale_minutes:
            st.warning(f"ThingSpeak connected, but the latest sensor reading is {age:.1f} minutes old (STALE). Last sample: {latest:%d %b %Y %H:%M:%S} {DISPLAY_TZ}.")
        else:
            st.success(f"LIVE ThingSpeak | Channel {ss.ts_channel} | {len(df)} readings | Last sensor sample: {latest:%d %b %Y %H:%M:%S} {DISPLAY_TZ} | Age: {max(age,0):.1f} min")
    elif not (ss.ts_enabled and ss.ts_error):
        st.info(f"Data source: {ss.data_source} — not live ThingSpeak data.")


def alert_state(temp: float):
    thr, typ = st.session_state.alert_temp, st.session_state.alert_type
    triggered = temp > thr if typ == "Above" else temp < thr
    return triggered, thr, typ


def handle_alert(temp: float):
    triggered, thr, typ = alert_state(temp)
    if not triggered:
        return

    # Email via ThingSpeak, throttled so a hot slab doesn't flood the inbox
    if st.session_state.email_enabled:
        gap_s = float(st.session_state.email_gap_min) * 60
        if time.time() - float(st.session_state.last_email_ts) >= gap_s:
            subject = f"Concrete Temperature Alert: {temp:.1f} C"
            msg = (f"{st.session_state.project}: core temperature {temp:.1f} C is {typ.lower()} "
                   f"the limit of {thr:.0f} C at {datetime.now().strftime('%d %b %Y %H:%M:%S')}.")
            status = send_email_alert(subject, msg)
            if status == "Sent":
                st.session_state.last_email_ts = time.time()
            st.session_state.alert_log.insert(0, {"Time": datetime.now().strftime("%d %b %H:%M"), "To": "Email (ThingSpeak)", "Status": status, "Message": msg})


# ============================================================== PLOTLY HELPERS (high-contrast professional light theme)
def style_fig(fig, height=330, xtitle=None, ytitle=None):
    # Explicitly set every text and axis colour: Streamlit's theme does not
    # reliably override Plotly's default pale axis/legend colours.
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=18, r=16, t=34, b=18),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="Manrope, Arial, sans-serif", color="#334155", size=12),
        title_font=dict(color="#172033", size=15),
        legend=dict(
            orientation="h", y=1.13, x=0,
            font=dict(color="#334155", size=11),
            bgcolor="rgba(255,255,255,0)",
        ),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#0a2230", bordercolor="#0a2230", font=dict(color="#ffffff", size=12)),
    )
    axis_common = dict(
        showgrid=True, gridcolor="#e2e8f0", gridwidth=1,
        zeroline=False, showline=True, linecolor="#cbd5e1", linewidth=1,
        ticks="outside", tickcolor="#94a3b8", tickfont=dict(color="#475569", size=11),
        title_font=dict(color="#334155", size=12),
    )
    fig.update_xaxes(**axis_common, title=xtitle)
    fig.update_yaxes(**axis_common, title=ytitle)
    return fig


def fig_live(df, height=330):
    fig = go.Figure()
    for col, name, color in [("core", "Core Temp (°C)", "#ea580c"), ("surface", "Surface Temp (°C)", "#0e7c86"), ("ambient", "Ambient Temp (°C)", "#4f46e5")]:
        if df[col].notna().any():
            fig.add_trace(go.Scatter(x=df["elapsed"], y=df[col], name=name, mode="lines", line=dict(color=color, width=2.4)))
    fig.add_hline(y=st.session_state.alert_temp, line_dash="dash", line_color="#dc2626", annotation_text="Alert limit")
    return style_fig(fig, height, "Time (hours)", "Temperature (°C)")


def comparison_df(df):
    calibration_m, calibration_s = df.attrs["curve"]
    rows = []
    for age in CUBE_AGES:
        cube = st.session_state.cube_data.get(age)
        measured_maturity = st.session_state.cube_maturity.get(age)
        live = float(predict_strength(measured_maturity, calibration_m, calibration_s)) if measured_maturity is not None else np.nan
        rows.append({
            "Age (Days)": age,
            "Recorded Maturity (°C·hr)": round(measured_maturity, 1) if measured_maturity is not None else None,
            "Calibrated Strength (MPa)": round(live, 1) if np.isfinite(live) else None,
            "Cube Strength (MPa)": cube,
            "Difference (MPa)": round(live - cube, 1) if cube is not None and np.isfinite(live) else None,
        })
    return pd.DataFrame(rows)


def fig_compare(cmp, height=330):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cmp["Age (Days)"], y=cmp["Calibrated Strength (MPa)"], name="Cube-calibrated estimate", mode="lines+markers", line=dict(color="#4f46e5", width=2.6)))
    fig.add_trace(go.Scatter(x=cmp["Age (Days)"], y=cmp["Cube Strength (MPa)"], name="Measured cube test", mode="lines+markers", line=dict(color="#0e7c86", width=2.6)))
    fig.update_xaxes(tickvals=CUBE_AGES)
    return style_fig(fig, height, "Cube Age (Days)", "Strength (MPa)")


# ============================================================== REUSABLE CARDS
EXCEL_EXTS = (".xlsx", ".xlsm", ".xls")
UPLOAD_TYPES = ["csv", "tsv", "xlsx", "xls", "xlsm"]


def read_uploaded_table(f, sheet=None) -> pd.DataFrame:
    """Read a CSV / TSV / Excel upload into a raw DataFrame (no column renaming)."""
    name = f.name.lower()
    data = f.getvalue()
    if name.endswith(EXCEL_EXTS):
        try:
            return pd.read_excel(io.BytesIO(data), sheet_name=sheet if sheet is not None else 0)
        except ImportError as exc:
            raise ValueError("Excel support needs extra packages. Install with: pip install openpyxl xlrd") from exc
    sep = "\t" if name.endswith(".tsv") else ","
    last_exc = None
    for enc in ("utf-8-sig", "latin-1"):
        try:
            frame = pd.read_csv(io.BytesIO(data), sep=sep, encoding=enc)
            if frame.shape[1] == 1 and sep == ",":
                # Semicolon-separated exports (common from Excel in some regions)
                frame = pd.read_csv(io.BytesIO(data), sep=None, engine="python", encoding=enc)
            return frame
        except UnicodeDecodeError as exc:
            last_exc = exc
    raise ValueError(f"Could not decode the file: {last_exc}")


def card_upload(ctx, title="1. Upload Dataset", hint=True):
    ss = st.session_state
    with st.container(border=True):
        st.markdown(f'<div class="card-title">{title}</div>', unsafe_allow_html=True)
        f = st.file_uploader("Choose a CSV or Excel file", type=UPLOAD_TYPES, key=f"{ctx}_upl",
                             label_visibility="collapsed",
                             help="Supported: .csv, .tsv, .xlsx, .xls, .xlsm")
        sheet = None
        if f is not None and f.name.lower().endswith(EXCEL_EXTS):
            try:
                names = pd.ExcelFile(io.BytesIO(f.getvalue())).sheet_names
            except Exception as exc:
                names = []
                st.error(f"Could not open the Excel file: {exc}")
            if len(names) > 1:
                sheet = st.selectbox("Worksheet to load", names, key=f"{ctx}_sheet")
            elif names:
                sheet = names[0]
        if f is not None:
            signature = (f.name, f.size, hashlib.md5(f.getvalue()).hexdigest(), sheet)
            if ss.get("upload_signature") != signature:
                try:
                    raw = read_uploaded_table(f, sheet)
                    ss.raw_df = normalize_df(raw)
                    ss.upload_raw = raw
                    ss.upload_name = f.name + (f"  [sheet: {sheet}]" if sheet and f.name.lower().endswith(EXCEL_EXTS) else "")
                    ss.upload_signature = signature
                    ss.source_choice = "Uploaded File"
                    # Synchronize the selectbox key at the start of the next run,
                    # before Streamlit instantiates that widget.
                    ss["_sync_source_choice_widget"] = True
                    ss.report_files = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not read file: {e}")
        if ss.upload_name:
            st.success(f"Dataset uploaded successfully! ({ss.upload_name})")
        elif hint:
            st.caption("Upload a CSV or Excel file (.csv, .xlsx, .xls). It needs a timestamp column and a core-temperature column.")


def fig_maturity(df, height=300):
    fig = go.Figure(go.Scatter(x=df["elapsed"], y=df["maturity"], mode="lines", name="Maturity",
                               line=dict(color="#0e7c86", width=2.6), fill="tozeroy", fillcolor="rgba(14,124,134,.10)"))
    return style_fig(fig, height, "Time (hours)", "°C·hr")


def fig_strength(df, height=300):
    fig = go.Figure(go.Scatter(x=df["elapsed"], y=df["strength"], mode="lines", name="Strength",
                               line=dict(color="#4f46e5", width=2.6), fill="tozeroy", fillcolor="rgba(79,70,229,.09)"))
    return style_fig(fig, height, "Time (hours)", "MPa")



def card_grade(ctx):
    with st.container(border=True):
        st.markdown('<div class="card-title">2. Select Concrete Grade</div>', unsafe_allow_html=True)
        g = st.selectbox("Grade", list(GRADES), index=list(GRADES).index(st.session_state.grade), key=f"{ctx}_grade", label_visibility="collapsed")
        st.session_state.grade = g
        st.caption(f"Target 28-day strength: **{GRADES[g]:.0f} MPa**")


def card_alert(ctx, title="3. Set Temperature Alert"):
    with st.container(border=True):
        st.markdown(f'<div class="card-title">{title}</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        st.session_state.alert_temp = c1.number_input("Alert Temperature (°C)", value=float(st.session_state.alert_temp), step=1.0, key=f"{ctx}_at")
        st.session_state.alert_type = c2.selectbox("Alert Type", ["Above", "Below"], index=["Above", "Below"].index(st.session_state.alert_type), key=f"{ctx}_aty")


def card_cube_input(ctx):
    with st.container(border=True):
        st.markdown('<div class="card-title">Add Cube Test Data (Compression)</div>', unsafe_allow_html=True)
        st.caption("Enter actual measured cube strength (MPa). Maturity is automatically taken from the selected temperature history when it covers the cube testing age. If not, you may enter the actual recorded maturity manually. No maturity is invented.")
        df = get_data()
        vals, maturities = {}, {}
        for age in CUBE_AGES:
            observed = maturity_at_age(df, age * 24, st.session_state.datum_temp, st.session_state.ref_temp) if not df.empty else np.nan
            stored = st.session_state.cube_maturity.get(age)
            # Existing saved maturity takes precedence so later live-data changes do not silently rewrite a laboratory record.
            auto = float(stored) if stored is not None else (float(observed) if np.isfinite(observed) else None)
            vals[age] = st.number_input(f"{age}-day measured strength (MPa)", min_value=0.0,
                value=float(st.session_state.cube_data.get(age, 0.0)), step=0.1, key=f"{ctx}_cube_{age}")
            if auto is not None and auto > 0:
                maturities[age] = auto
                st.caption(f"{age}-day maturity: {auto:,.1f} °C·hr ({'saved calibration' if stored is not None else 'calculated from available temperature readings'})")
            else:
                with st.expander(f"{age}-day maturity unavailable from recorded data — enter actual value if known"):
                    manual = st.number_input(f"Recorded {age}-day maturity (°C·hr)", min_value=0.0,
                        value=0.0, step=10.0, key=f"{ctx}_maturity_{age}")
                    if manual > 0:
                        maturities[age] = manual
        if st.button("Save Cube Test Data", type="primary", key=f"{ctx}_save", use_container_width=True):
            old_data, old_maturity = dict(st.session_state.cube_data), dict(st.session_state.cube_maturity)
            st.session_state.cube_data = {a: v for a, v in vals.items() if v > 0}
            st.session_state.cube_maturity = {a: maturities[a] for a, v in vals.items() if v > 0 and a in maturities and maturities[a] > 0}
            ok, message = save_cube_calibration()
            if not ok:
                st.session_state.cube_data, st.session_state.cube_maturity = old_data, old_maturity
                st.error(message)
            else:
                st.session_state.cube_saved = True
                st.session_state.cube_storage_message = message
                st.rerun()
        if st.session_state.get("cube_storage_error"):
            st.error("Could not load saved calibration: " + st.session_state.cube_storage_error)
        st.caption("Storage: " + st.session_state.get("cube_storage_backend", "Not yet verified"))

def card_cube_table():
    with st.container(border=True):
        st.markdown('<div class="card-title">Cube Test Calibration Records</div>', unsafe_allow_html=True)
        rows = [{
            "Age (Days)": a,
            "Measured Strength (MPa)": v,
            "Maturity (°C·hr)": st.session_state.cube_maturity.get(a),
            "Status": "Complete" if st.session_state.cube_maturity.get(a, 0) > 0 else "Awaiting actual maturity reading",
        } for a, v in sorted(st.session_state.cube_data.items())]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        if st.session_state.get("cube_storage_message"):
            st.caption(st.session_state.cube_storage_message)
        if not st.session_state.cube_saved:
            st.info("Enter actual laboratory cube strengths and corresponding recorded maturity values.")
        elif len(fit_curve(st.session_state.cube_data, st.session_state.cube_maturity)[0]) < 2:
            st.warning("At least two complete cube records with distinct maturity values are required.")
        else:
            st.success("Cube test calibration records saved.")


def kpi(label, value, unit, sub, tone):
    st.markdown(
        f'<div class="kpi kpi-{tone}"><div>'
        f'<div class="kpi-label">{label}</div><div class="kpi-val">{value}<small>{unit}</small></div>'
        f'<div class="kpi-sub">{sub}</div></div></div>',
        unsafe_allow_html=True,
    )


def check_live_alert(df):
    """Send an alert email when the latest LIVE reading breaches the limit (throttled in handle_alert)."""
    if df.empty or st.session_state.data_source != "ThingSpeak":
        return
    latest = df.iloc[-1]
    age_min = (pd.Timestamp.now(tz=DISPLAY_TZ).tz_localize(None) - latest["ts"]).total_seconds() / 60
    if 0 <= age_min <= st.session_state.ts_stale_minutes:
        handle_alert(float(latest["core"]))


def kpi_row(df):
    latest = df.iloc[-1]
    triggered, thr, typ = alert_state(float(latest["core"]))
    check_live_alert(df)
    k1, k2, k3 = st.columns(3)
    with k1:
        badge = '<span class="badge badge-bad">Alert</span>' if triggered else '<span class="badge badge-ok">Normal</span>'
        kpi("Current Core Temperature", f"{latest['core']:.1f}", " °C", badge, "heat")
    with k2:
        kpi("Nurse–Saul Maturity", f"{latest['maturity']:.1f}", " °C·hr", f"Datum temperature: {st.session_state.datum_temp:g} °C", "teal")
    with k3:
        strength = f"{latest['strength']:.1f}" if pd.notna(latest["strength"]) else "N/A"
        basis = latest.get("strength_basis", "Standard curve")
        sub = ("Measured cube data used" if basis == "Cube-calibrated"
               else f"Estimate: standard {st.session_state.grade} curve (not a cube result)")
        kpi("Estimated Strength", strength, " MPa", sub, "indigo")
        _, n_used = cube_scale_factor(st.session_state.cube_data, st.session_state.cube_maturity,
                                      GRADES[st.session_state.grade], st.session_state.datum_temp)
        if n_used:
            st.caption(f"Standard curve adjusted using {n_used} measured cube result(s).")
        else:
            st.caption("No usable cube result yet. Enter a cube strength with its maturity to improve accuracy.")


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
            "Cube-Calibrated Strength (MPa)": t["strength"].round(1),
            "Status": ["Alert" if x else "Normal" for x in triggered],
        })
        st.dataframe(out, hide_index=True, use_container_width=True)


def card_calculator(ctx):
    with st.container(border=True):
        st.markdown('<div class="card-title">Nurse–Saul Maturity & Strength Calculator</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        temp = c1.number_input("Average concrete temperature (°C)", value=27.0, step=1.0, key=f"{ctx}_ct")
        hrs = c2.number_input("Time interval (hours)", value=24.0, min_value=0.0, step=1.0, key=f"{ctx}_ch")
        if st.button("Calculate", type="primary", use_container_width=True, key=f"{ctx}_calc"):
            maturity = max(temp - st.session_state.datum_temp, 0.0) * hrs
            cm, cs = fit_curve(st.session_state.cube_data, st.session_state.cube_maturity)
            strength = predict_strength(maturity, cm, cs)
            if not np.isfinite(strength):
                strength = float(estimate_strength(maturity, st.session_state.cube_data, st.session_state.cube_maturity,
                                                   GRADES[st.session_state.grade], st.session_state.datum_temp))
            st.session_state.calc_result = (maturity, strength)
        res = st.session_state.calc_result
        if res:
            r1, r2 = st.columns(2)
            r1.metric("Nurse–Saul maturity", f"{res[0]:,.1f} °C·hr")
            if np.isfinite(res[1]):
                r2.metric("Estimated strength", f"{res[1]:.2f} MPa")
            else:
                r2.info("Strength unavailable: maturity is outside the measured calibration range or calibration data is insufficient.")


def card_strength_table(cmp):
    with st.container(border=True):
        st.markdown('<div class="card-title">Strength in MPa</div>', unsafe_allow_html=True)
        st.dataframe(cmp, hide_index=True, use_container_width=True)
        st.caption("Cube-calibrated estimates use recorded maturity/strength pairs and are shown only within the measured calibration range. They are not measured compression-test results.")


# ============================================================== PAGES
def page_dashboard():
    c1, c2, c3, c4 = st.columns([1.15, 1, 1.15, 2.1])
    with c1: card_upload("d")
    with c2: card_grade("d")
    with c3: card_alert("d")
    with c4: card_cube_input("d")
    df = get_data()
    if not data_ready(df):
        return
    cmp = comparison_df(df)
    source_banner(df)
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
        if not data_ready(df):
            return
        source_banner(df)
        kpi_row(df)
        st.write("")
        with st.container(border=True):
            st.markdown('<div class="card-title">Live Sensor Data (Temperature)</div>', unsafe_allow_html=True)
            st.plotly_chart(fig_live(df, 420), use_container_width=True)
        g1, g2 = st.columns(2)
        with g1:
            with st.container(border=True):
                st.markdown('<div class="card-title">Maturity Index (°C·hr)</div>', unsafe_allow_html=True)
                fig = go.Figure(go.Scatter(x=df["elapsed"], y=df["maturity"], mode="lines", line=dict(color="#0e7c86", width=2.6), fill="tozeroy", fillcolor="rgba(14,124,134,.10)"))
                st.plotly_chart(style_fig(fig, 300, "Time (hours)", "°C·hr"), use_container_width=True)
        with g2:
            with st.container(border=True):
                st.markdown('<div class="card-title">Predicted Strength (MPa)</div>', unsafe_allow_html=True)
                fig = go.Figure(go.Scatter(x=df["elapsed"], y=df["strength"], mode="lines", line=dict(color="#4f46e5", width=2.6), fill="tozeroy", fillcolor="rgba(79,70,229,.09)"))
                st.plotly_chart(style_fig(fig, 300, "Time (hours)", "MPa"), use_container_width=True)
        card_monitoring_table(df)
        with st.expander("Export raw data"):
            st.download_button("Download CSV", df.to_csv(index=False).encode(), "monitoring_data.csv", "text/csv")

    if st.session_state.auto_refresh:
        st.fragment(run_every=st.session_state.refresh_s)(body)()
    else:
        body()


def page_compare():
    df = get_data()
    if not data_ready(df):
        return
    cmp = comparison_df(df)
    g1, g2 = st.columns([1.5, 1])
    with g1:
        with st.container(border=True):
            st.markdown('<div class="card-title">Strength Comparison – Live vs Cube Test</div>', unsafe_allow_html=True)
            st.plotly_chart(fig_compare(cmp, 420), use_container_width=True)
    with g2:
        card_strength_table(cmp)
    card_cube_input("c")


def page_upload():
    ss = st.session_state
    card_upload("u", title="Upload your file (CSV or Excel)", hint=False)
    if ss.raw_df is None or ss.raw_df.empty:
        return                                   # nothing else is shown until a file is uploaded
    df = get_data("Uploaded File")               # always the uploaded file, whatever source is selected elsewhere
    if df.empty:
        return
    raw = ss.get("upload_raw")
    st.write("")

    interval = df["ts"].diff().dt.total_seconds().median()
    interval_txt = "-" if not np.isfinite(interval) else (f"{interval / 60:.1f} min" if interval < 3600 else f"{interval / 3600:.1f} h")
    last_strength = df["strength"].iloc[-1]
    m1, m2, m3 = st.columns(3)
    m1.metric("Rows used / rows in file", f"{len(df):,} / {len(raw) if raw is not None else len(df):,}")
    m2.metric("Columns in file", f"{raw.shape[1]}" if raw is not None else "-")
    m3.metric("Duration", f"{df['elapsed'].iloc[-1]:.1f} h ({df['elapsed'].iloc[-1] / 24:.1f} days)")
    m4, m5, m6 = st.columns(3)
    m4.metric("Period", f"{df['ts'].iloc[0]:%d %b %Y} to {df['ts'].iloc[-1]:%d %b %Y}")
    m5.metric("Reading interval", interval_txt)
    m6.metric("Core temp range", f"{df['core'].min():.1f} – {df['core'].max():.1f} °C")
    m7, m8, m9 = st.columns(3)
    m7.metric("Peak core temperature", f"{df['core'].max():.1f} °C")
    m8.metric("Latest maturity", f"{df['maturity'].iloc[-1]:,.0f} °C·hr")
    m9.metric("Latest est. strength", f"{last_strength:.1f} MPa" if pd.notna(last_strength) else "N/A")
    st.write("")

    with st.container(border=True):
        st.markdown('<div class="card-title">Dataset Details</div>', unsafe_allow_html=True)
        t_charts, t_stats, t_cols, t_proc, t_raw = st.tabs(["Charts", "Statistics", "Columns", "Processed data", "Original file"])
        with t_charts:
            st.plotly_chart(fig_live(df, 340), use_container_width=True)
            g1, g2 = st.columns(2)
            with g1:
                st.markdown("**Maturity index (°C·hr)**")
                st.plotly_chart(fig_maturity(df), use_container_width=True)
            with g2:
                st.markdown("**Estimated strength (MPa)**")
                st.plotly_chart(fig_strength(df), use_container_width=True)
        with t_stats:
            stats = df[["core", "surface", "ambient", "maturity", "strength"]].dropna(axis=1, how="all").describe().T.round(2)
            stats.index = [{"core": "Core temp (°C)", "surface": "Surface temp (°C)", "ambient": "Ambient temp (°C)",
                            "maturity": "Maturity (°C·hr)", "strength": "Strength (MPa)"}[i] for i in stats.index]
            st.dataframe(stats.rename(columns={"count": "Count", "mean": "Mean", "std": "Std dev", "min": "Min", "max": "Max"}),
                         use_container_width=True)
        with t_cols:
            if raw is not None:
                info = pd.DataFrame({
                    "Column": [str(c) for c in raw.columns],
                    "Type": [str(t) for t in raw.dtypes],
                    "Missing values": raw.isna().sum().values,
                    "First value": [str(raw[c].dropna().iloc[0]) if raw[c].notna().any() else "-" for c in raw.columns],
                })
                st.dataframe(info, hide_index=True, use_container_width=True)
        with t_proc:
            st.caption("Cleaned data used by every dashboard tab.")
            st.dataframe(df.head(500), hide_index=True, use_container_width=True)
        with t_raw:
            if raw is not None:
                st.caption("Your file exactly as uploaded.")
                st.dataframe(raw.head(500), hide_index=True, use_container_width=True)

    b1, b2, b3, _ = st.columns([1, 1, 1, 2])
    b1.button("Open Dashboard", type="primary", use_container_width=True, key="u_go_dash", on_click=goto, args=("Dashboard",))
    b2.button("Download Report", use_container_width=True, key="u_go_rep", on_click=goto, args=("Download Report",))
    if b3.button("Clear dataset", use_container_width=True, key="u_clear"):
        ss.raw_df, ss.upload_name, ss.upload_raw = None, None, None
        ss.upload_signature = None
        ss.report_files = None
        ss.source_choice = "ThingSpeak live"
        ss["_sync_source_choice_widget"] = True
        st.rerun()


def page_alerts():
    ss = st.session_state
    df = get_data()
    if not df.empty:
        check_live_alert(df)      # keep email alerts working even if only this page is open

    history_df, history_error, archive_message = get_dashboard_alert_history()

    # ---------- graph + alert settings
    left, right = st.columns([1.7, 1])
    with left:
        with st.container(border=True):
            st.markdown('<div class="card-title">Core Temperature vs Alert Limit</div>', unsafe_allow_html=True)
            if data_ready(df):
                fig = fig_live(df, 380)
                breach = df[df["core"] > ss.alert_temp] if ss.alert_type == "Above" else df[df["core"] < ss.alert_temp]
                if not breach.empty:
                    fig.add_trace(go.Scatter(x=breach["elapsed"], y=breach["core"], mode="markers", name="Alert readings",
                                             marker=dict(color="#dc2626", size=7)))
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"{len(breach)} of {len(df)} readings are outside the limit ({ss.alert_type.lower()} {ss.alert_temp:.0f} °C).")
    with right:
        card_alert("a", "Set Temperature Alert")
        with st.container(border=True):
            st.markdown('<div class="card-title">Email Notifications</div>', unsafe_allow_html=True)
            ss.email_enabled = st.toggle("Enable email alerts", value=ss.email_enabled, key="a_email")
            ss.email_gap_min = st.number_input("Minimum minutes between emails", min_value=1, max_value=1440,
                                               value=int(ss.email_gap_min), step=1, key="a_email_gap")
            if not get_alert_key():
                st.warning("Set THINGSPEAK_ALERT_KEY in the environment or Streamlit secrets to send emails and read alert history.")
            if st.button("Send Test Email", key="a_test_email", use_container_width=True):
                msg = "Concrete curing monitoring test alert: email is working."
                status = send_email_alert("Concrete Monitor Test", msg)
                ss.alert_log.insert(0, {"Time": datetime.now().strftime("%d %b %H:%M"), "To": "Email (ThingSpeak)",
                                        "Status": status, "Message": msg})
                if status == "Sent":
                    st.success("Test email accepted by ThingSpeak.")
                    fetch_thingspeak_alert_history.clear()
                else:
                    st.error(f"Email status: {status}")

    # ---------- messages that were sent
    st.write("")
    with st.container(border=True):
        st.markdown('<div class="card-title">Alert Messages Sent</div>', unsafe_allow_html=True)
        if history_error:
            st.warning(history_error)
        if archive_message and archive_message.startswith("Could not"):
            st.warning(archive_message)
        if not history_df.empty:
            sent_count = int(history_df["status"].astype(str).str.lower().eq("sent").sum()) if "status" in history_df else 0
            h1, h2, h3 = st.columns(3)
            h1.metric("Messages", len(history_df))
            h2.metric("Reported as sent", sent_count)
            h3.metric("Other statuses", len(history_df) - sent_count)
            display_history = history_df.rename(columns={"requested_at": "Requested At", "sent_at": "Sent At",
                                                         "subject": "Message Subject", "status": "Delivery Status"})
            st.dataframe(display_history, hide_index=True, use_container_width=True)
            st.download_button("Download message history (CSV)", display_history.to_csv(index=False).encode("utf-8"),
                               file_name="thingspeak_alert_history.csv", mime="text/csv")
        elif not history_error:
            st.info("No alert messages have been sent yet.")

    with st.container(border=True):
        st.markdown('<div class="card-title">Alerts Triggered by This Dashboard</div>', unsafe_allow_html=True)
        if ss.alert_log:
            st.dataframe(pd.DataFrame(ss.alert_log), hide_index=True, use_container_width=True)
        else:
            st.caption("No alerts have been triggered by this dashboard during the current session.")


def page_cube():
    c1, c2 = st.columns([1.4, 1])
    with c1:
        card_cube_input("t")
    with c2:
        card_cube_table()
        cd = st.session_state.cube_data
        if cd:
            with st.container(border=True):
                st.markdown('<div class="card-title">Cube Strength vs Age</div>', unsafe_allow_html=True)
                fig = go.Figure(go.Bar(x=[f"{a} d" for a in sorted(cd)], y=[cd[a] for a in sorted(cd)],
                                       marker_color="#0e7c86", text=[cd[a] for a in sorted(cd)], textposition="outside"))
                st.plotly_chart(style_fig(fig, 300, "Age", "MPa"), use_container_width=True)


# ============================================================== HOME (welcome) PAGE
# Edit this block to describe your own device.
DEVICE_INFO = {
    "name": "ESP32 Concrete Curing Sensor Node",
    "steps": [
        ("Sensor node", "An ESP32 microcontroller reads the temperature probes embedded in the concrete."),
        ("ThingSpeak cloud", "Readings are published over Wi-Fi to your ThingSpeak channel every few minutes."),
        ("This dashboard", "Data is pulled in, converted to maturity and strength, and checked against your alert limit."),
    ],
    "sensors": [
        ("Core temperature", "Probe at the centre of the pour. Drives maturity and strength.", "ts_core_field"),
        ("Surface temperature", "Probe near the exposed surface. Shows the core-to-surface gradient.", "ts_surface_field"),
        ("Ambient temperature", "Site air temperature around the element.", "ts_ambient_field"),
    ],
}

FEATURES = [
    ("f-heat", '<path d="M10 14.5V5a2 2 0 1 1 4 0v9.5a4 4 0 1 1-4 0z"/>',
     "Live temperature monitoring",
     "Core, surface and ambient readings streamed from the sensor node and refreshed automatically."),
    ("f-teal", '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
     "Maturity and strength",
     "Nurse–Saul maturity converted into estimated compressive strength, calibrated with your cube tests."),
    ("f-indigo", '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12L4 7.5M12 12v9"/>',
     "Cube test comparison",
     "Record 3, 7, 14, 21 and 28-day cube results and compare them with the live estimate."),
    ("f-amber", '<path d="M6 16V11a6 6 0 1 1 12 0v5l2 2H4z"/><path d="M10 21h4"/>',
     "Alerts and reports",
     "Set a temperature limit, receive email alerts and download a PDF or Excel report at any time."),
]


def page_home():
    ss = st.session_state
    esc = _html.escape

    # ---- Hero (information only: no live readings on this page) ----
    reading = ('<div class="hero-read"><div class="hr-label">What it does</div><div class="hr-list">'
               '<div>Tracks core, surface and ambient temperature</div>'
               '<div>Calculates maturity with the Nurse–Saul method</div>'
               '<div>Estimates strength, calibrated by cube tests</div></div></div>')
    st.markdown(
        f"""
<div class="hero"><div class="hero-grid">
  <div class="hero-main">
    <div class="hero-title">Welcome, {esc(str(ss.operator))}</div>
    <div class="hero-sub">IoT Based Concrete Curing &amp; Strength Monitoring System</div>
    <p class="hero-text">Follow the temperature inside your concrete in real time, turn it into maturity with the
    Nurse–Saul method, and see when the slab has reached the strength you need.</p>
    <div class="hero-chips">
      <span class="chip">Project: {esc(str(ss.project))}</span>
      <span class="chip">Grade {esc(str(ss.grade))}</span>
      <span class="chip">Alert: {esc(str(ss.alert_type))} {ss.alert_temp:.0f} °C</span>
    </div>
  </div>
  {reading}
</div></div>
""",
        unsafe_allow_html=True,
    )
    b1, b2, b3, _ = st.columns([1, 1, 1, 2.4])
    b1.button("Open Dashboard", type="primary", use_container_width=True, key="h_go_dash", on_click=goto, args=("Dashboard",))
    b2.button("Upload Dataset", use_container_width=True, key="h_go_up", on_click=goto, args=("Upload Dataset",))
    b3.button("Download Report", use_container_width=True, key="h_go_rep", on_click=goto, args=("Download Report",))

    # ---- About ----
    st.markdown('<div class="section-head">About this dashboard</div>'
                '<div class="section-sub">Everything you need to decide when formwork can come off, in one place.</div>',
                unsafe_allow_html=True)
    cols = st.columns(4)
    for col, (tone, icon, title, text) in zip(cols, FEATURES):
        col.markdown(
            f'<div class="feat {tone}"><svg viewBox="0 0 24 24">{icon}</svg>'
            f'<div class="feat-title">{title}</div><div class="feat-text">{text}</div></div>',
            unsafe_allow_html=True)

    # ---- Device ----
    st.markdown(f'<div class="section-head">Your monitoring device</div>'
                f'<div class="section-sub">{esc(DEVICE_INFO["name"])}: how readings get from the concrete to this screen.</div>',
                unsafe_allow_html=True)
    d1, d2 = st.columns([1.1, 1])
    with d1:
        with st.container(border=True):
            st.markdown('<div class="card-title">How it works</div>', unsafe_allow_html=True)
            steps = "".join(
                f'<div class="flow-step"><div class="flow-no">{i}</div><div>'
                f'<div class="flow-title">{esc(t)}</div><div class="flow-text">{esc(d)}</div></div></div>'
                for i, (t, d) in enumerate(DEVICE_INFO["steps"], 1))
            st.markdown(f'<div class="flow">{steps}</div>', unsafe_allow_html=True)
    with d2:
        with st.container(border=True):
            st.markdown('<div class="card-title">Sensor channels</div>', unsafe_allow_html=True)
            rows = []
            for name, purpose, key in DEVICE_INFO["sensors"]:
                n = int(ss.get(key, 0) or 0)
                rows.append({"Sensor": name, "ThingSpeak field": f"Field {n}" if n else "Not connected", "Purpose": purpose})
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            st.caption(f"ThingSpeak channel: {ss.ts_channel or 'not set'}. Change fields in Settings.")

    # ---- Basic settings ----
    st.markdown('<div class="section-head">Basic settings</div>'
                '<div class="section-sub">Set these once to get started. You can change them at any time.</div>',
                unsafe_allow_html=True)
    with st.container(border=True):
        r1 = st.columns(4)
        ss.project = r1[0].text_input("Project name", value=ss.project, key="h_proj")
        ss.operator = r1[1].text_input("Your name", value=ss.operator, key="h_op")
        ss.grade = r1[2].selectbox("Concrete grade", list(GRADES), index=list(GRADES).index(ss.grade), key="h_grade")
        with r1[3]:
            render_source_selector()
        r2 = st.columns(4)
        ss.alert_temp = r2[0].number_input("Alert temperature (°C)", value=float(ss.alert_temp), step=1.0, key="h_at")
        ss.alert_type = r2[1].selectbox("Alert type", ["Above", "Below"], index=["Above", "Below"].index(ss.alert_type), key="h_aty")
        ss.datum_temp = r2[2].number_input("Datum temperature (°C)", value=float(ss.datum_temp), step=1.0, key="h_datum",
                                           help="Nurse–Saul datum temperature used for maturity.")
        ss.auto_refresh = r2[3].toggle("Auto-refresh live data", value=ss.auto_refresh, key="h_auto")
        st.caption(f"Target 28-day strength for {ss.grade}: {GRADES[ss.grade]:.0f} MPa. "
                   "More options (ThingSpeak connection, refresh interval, email alerts) are in Settings.")


def page_settings():
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown('<div class="card-title">Maturity Settings</div>', unsafe_allow_html=True)
            st.session_state.datum_temp = st.number_input("Datum temperature (°C)", value=float(st.session_state.datum_temp), step=1.0, key="s_datum", help="Your confirmed Nurse–Saul datum temperature is −10°C.")
            st.session_state.ref_temp = st.number_input("Assumed avg curing temp beyond dataset (°C)", value=float(st.session_state.ref_temp), step=0.5, key="s_ref")
            st.session_state.auto_refresh = st.toggle("Auto-refresh Live Monitoring", value=st.session_state.auto_refresh, key="s_auto")
            st.session_state.refresh_s = st.slider("Refresh interval (seconds)", 5, 60, int(st.session_state.refresh_s), key="s_ref_s")
        with st.container(border=True):
            st.markdown('<div class="card-title">ThingSpeak Live Sensor Connection</div>', unsafe_allow_html=True)
            ss = st.session_state
            ss.ts_enabled = st.toggle("Use ThingSpeak live feed", value=ss.ts_enabled, key="s_ts_enabled")
            ss.ts_channel = st.text_input("Channel ID", value=ss.ts_channel, key="s_ts_channel")
            ss.ts_read_key = st.text_input("Read API Key (leave blank for public channels)", value=ss.ts_read_key, type="password", key="s_ts_key")
            f1, f2, f3 = st.columns(3)
            ss.ts_core_field = f1.number_input("Core field", 1, 8, int(ss.ts_core_field), key="s_ts_core")
            ss.ts_surface_field = f2.number_input("Surface field (0 = none)", 0, 8, int(ss.ts_surface_field), key="s_ts_surface")
            ss.ts_ambient_field = f3.number_input("Ambient field (0 = none)", 0, 8, int(ss.ts_ambient_field), key="s_ts_ambient")
            ss.ts_results = st.number_input("Recent readings to fetch", 10, 8000, int(ss.ts_results), step=50, key="s_ts_results")
            ss.ts_start = st.text_input("Pour start (optional, YYYY-MM-DD HH:MM in display timezone)", value=ss.ts_start, key="s_ts_start")
            ss.ts_stale_minutes = st.number_input("Stale reading after (minutes)", 1, 1440, int(ss.ts_stale_minutes), key="s_ts_stale")
            if st.button("Test ThingSpeak Connection", key="s_ts_test", use_container_width=True):
                fetch_thingspeak.clear()
                test_df = load_thingspeak()
                if test_df is None:
                    st.error(f"Connection failed: {ss.ts_error}")
                else:
                    st.success(f"Connected: {len(test_df)} readings; core = {test_df['core'].iloc[-1]:.2f} °C at {test_df['ts'].iloc[-1]:%Y-%m-%d %H:%M:%S} {DISPLAY_TZ}")
            st.caption("The dashboard polls ThingSpeak while its browser page is open. Refresh does not force a new ESP32 upload.")
    with c2:
        with st.container(border=True):
            st.markdown('<div class="card-title">Project & Operator</div>', unsafe_allow_html=True)
            st.session_state.project = st.text_input("Project name", value=st.session_state.project, key="s_proj")
            st.session_state.operator = st.text_input("Operator", value=st.session_state.operator, key="s_op")
            st.session_state.email_enabled = st.toggle("Enable email alerts (ThingSpeak)", value=st.session_state.email_enabled, key="s_email")


# ============================================================== REPORT BUILDERS
def report_summary(df):
    """Ordered (label, value) rows describing the monitoring period."""
    ss = st.session_state
    latest = df.iloc[-1]
    _, thr, typ = alert_state(float(latest["core"]))
    breach = (df["core"] > thr) if typ == "Above" else (df["core"] < thr)
    peak = df.loc[df["core"].idxmax()]
    target = GRADES[ss.grade]
    strength = float(latest["strength"]) if pd.notna(latest["strength"]) else np.nan
    rows = [
        ("Project", str(ss.project)),
        ("Prepared by", str(ss.operator)),
        ("Concrete grade", f"{ss.grade} (target {target:.0f} MPa at 28 days)"),
        ("Data source", str(ss.data_source)),
        ("Monitoring period", f"{df['ts'].iloc[0]:%d %b %Y %H:%M} to {df['ts'].iloc[-1]:%d %b %Y %H:%M}"),
        ("Duration", f"{df['elapsed'].iloc[-1]:.1f} hours ({df['elapsed'].iloc[-1] / 24:.1f} days)"),
        ("Number of readings", f"{len(df):,}"),
        ("Latest core temperature", f"{latest['core']:.1f} °C"),
        ("Peak core temperature", f"{peak['core']:.1f} °C at {peak['ts']:%d %b %H:%M}"),
        ("Average core temperature", f"{df['core'].mean():.1f} °C"),
        ("Minimum core temperature", f"{df['core'].min():.1f} °C"),
    ]
    if df["surface"].notna().any():
        rows.append(("Average surface temperature", f"{df['surface'].mean():.1f} °C"))
        rows.append(("Max core-surface difference", f"{(df['core'] - df['surface']).abs().max():.1f} °C"))
    if df["ambient"].notna().any():
        rows.append(("Average ambient temperature", f"{df['ambient'].mean():.1f} °C"))
    rows += [
        ("Alert limit", f"{typ} {thr:.0f} °C"),
        ("Readings breaching the limit", f"{int(breach.sum())} of {len(df)} ({breach.mean() * 100:.1f}%)"),
        ("Maturity (latest)", f"{latest['maturity']:,.1f} °C·hr (datum {ss.datum_temp:g} °C)"),
        ("Estimated strength (latest)", f"{strength:.1f} MPa" if np.isfinite(strength) else "N/A"),
        ("Strength basis", str(latest.get("strength_basis", "Standard curve"))),
    ]
    if np.isfinite(strength):
        rows.append(("Share of 28-day target", f"{strength / target * 100:.0f}%"))
    return rows


def _fig_png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170, bbox_inches="tight")
    buf.seek(0)
    return buf


def _style_ax(ax, xl, yl):
    ax.set_xlabel(xl, fontsize=8, color="#334155")
    ax.set_ylabel(yl, fontsize=8, color="#334155")
    ax.grid(True, color="#e2e8f0", linewidth=.8)
    ax.tick_params(labelsize=7, colors="#475569")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#cbd5e1")


def report_chart_images(df, cmp):
    """Return PNG buffers for the PDF report (pyplot-free, so it is thread safe)."""
    from matplotlib.figure import Figure
    images = {}

    fig = Figure(figsize=(8, 3.1))
    ax = fig.subplots()
    for col, label, color in (("core", "Core", "#ea580c"), ("surface", "Surface", "#0e7c86"), ("ambient", "Ambient", "#4f46e5")):
        if df[col].notna().any():
            ax.plot(df["elapsed"], df[col], label=label, color=color, linewidth=1.8)
    ax.axhline(st.session_state.alert_temp, color="#dc2626", linestyle="--", linewidth=1.1, label="Alert limit")
    ax.legend(fontsize=7, frameon=False, ncol=4, loc="lower left", bbox_to_anchor=(0, 1.0))
    _style_ax(ax, "Time (hours)", "Temperature (°C)")
    images["temp"] = _fig_png(fig)

    fig = Figure(figsize=(8, 2.8))
    a1, a2 = fig.subplots(1, 2)
    a1.plot(df["elapsed"], df["maturity"], color="#0e7c86", linewidth=1.8)
    a1.fill_between(df["elapsed"], df["maturity"], color="#0e7c86", alpha=.12)
    a1.set_title("Maturity index", fontsize=9, color="#12202b")
    _style_ax(a1, "Time (hours)", "°C·hr")
    a2.plot(df["elapsed"], df["strength"], color="#4f46e5", linewidth=1.8)
    a2.fill_between(df["elapsed"], df["strength"].fillna(0), color="#4f46e5", alpha=.10)
    a2.set_title("Estimated strength", fontsize=9, color="#12202b")
    _style_ax(a2, "Time (hours)", "MPa")
    fig.tight_layout()
    images["maturity"] = _fig_png(fig)

    if cmp["Cube Strength (MPa)"].notna().any():
        fig = Figure(figsize=(8, 2.8))
        ax = fig.subplots()
        ax.plot(cmp["Age (Days)"], cmp["Calibrated Strength (MPa)"], marker="o", color="#4f46e5", label="Cube-calibrated estimate")
        ax.plot(cmp["Age (Days)"], cmp["Cube Strength (MPa)"], marker="s", color="#0e7c86", label="Measured cube test")
        ax.set_xticks(CUBE_AGES)
        ax.legend(fontsize=7, frameon=False)
        _style_ax(ax, "Cube age (days)", "Strength (MPa)")
        images["cube"] = _fig_png(fig)
    return images


def _fmt(v, nd=1):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "-"
    if isinstance(v, (int, float, np.integer, np.floating)):
        return f"{v:,.{nd}f}"
    return str(v)


def build_pdf_report(df, cmp, opts):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ss = st.session_state
    petrol, teal, line = colors.HexColor("#0d3b4a"), colors.HexColor("#0e7c86"), colors.HexColor("#dbe3ea")
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12.5, textColor=petrol, spaceBefore=12, spaceAfter=6)
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=9, leading=12.5, textColor=colors.HexColor("#26344a"))
    small = ParagraphStyle("small", parent=body, fontSize=7.5, leading=10, textColor=colors.HexColor("#64748b"))
    cell = ParagraphStyle("cell", parent=body, fontSize=8, leading=10)
    esc = _html.escape
    width = A4[0] - 32 * mm

    def table(rows, widths, header=True):
        t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
        style = [("FONT", (0, 0), (-1, -1), "Helvetica", 8), ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#26344a")),
                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), .4, line),
                 ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, colors.HexColor("#f4f8fa")]),
                 ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
        if header:
            style += [("BACKGROUND", (0, 0), (-1, 0), petrol), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                      ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8)]
        t.setStyle(TableStyle(style))
        return t

    story = []
    banner = Table([[Paragraph(f'<font color="white" size="17"><b>{esc(opts["title"])}</b></font><br/>'
                               f'<font color="#bfeff2" size="9">{esc(str(ss.project))}  |  Generated {datetime.now():%d %b %Y, %H:%M}</font>', body)]],
                   colWidths=[width])
    banner.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), petrol), ("LEFTPADDING", (0, 0), (-1, -1), 14),
                                ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                                ("LINEBELOW", (0, 0), (-1, -1), 3, teal)]))
    story += [banner, Spacer(1, 6)]

    story.append(Paragraph("Summary", h2))
    story.append(table([[Paragraph(f"<b>{esc(k)}</b>", cell), Paragraph(esc(v), cell)] for k, v in opts["summary"]],
                       [58 * mm, width - 58 * mm], header=False))

    if opts["charts"]:
        imgs = report_chart_images(df, cmp)
        story.append(KeepTogether([Paragraph("Temperature history", h2), Image(imgs["temp"], width=width, height=width * 0.39)]))
        story.append(KeepTogether([Paragraph("Maturity and estimated strength", h2), Image(imgs["maturity"], width=width, height=width * 0.35)]))
        if "cube" in imgs:
            story.append(KeepTogether([Paragraph("Strength comparison: live estimate vs cube test", h2),
                                       Image(imgs["cube"], width=width, height=width * 0.35)]))

    if opts["cube"]:
        story.append(Paragraph("Cube test records", h2))
        rows = [["Age (days)", "Maturity (C-hr)", "Calibrated (MPa)", "Cube test (MPa)", "Difference (MPa)"]]
        for _, r in cmp.iterrows():
            rows.append([_fmt(int(r["Age (Days)"]), 0), _fmt(r["Recorded Maturity (°C·hr)"]), _fmt(r["Calibrated Strength (MPa)"]),
                         _fmt(r["Cube Strength (MPa)"]), _fmt(r["Difference (MPa)"])])
        story.append(table(rows, [width / 5] * 5))
        if not cmp["Cube Strength (MPa)"].notna().any():
            story += [Spacer(1, 3), Paragraph("No cube test results have been recorded yet.", small)]

    if opts["data"]:
        story.append(Paragraph("Latest 15 readings", h2))
        t = df.iloc[::-1].head(15)
        rows = [["Date & time", "Core (C)", "Surface (C)", "Ambient (C)", "Maturity (C-hr)", "Strength (MPa)", "Status"]]
        for _, r in t.iterrows():
            rows.append([f"{r['ts']:%Y-%m-%d %H:%M}", _fmt(r["core"]), _fmt(r["surface"]), _fmt(r["ambient"]),
                         _fmt(r["maturity"]), _fmt(r["strength"]), "Alert" if alert_state(float(r["core"]))[0] else "Normal"])
        story.append(table(rows, [34 * mm] + [(width - 34 * mm) / 6] * 6))

    if opts["alerts"]:
        story.append(Paragraph("Alerts triggered during this session", h2))
        log = ss.alert_log
        if log:
            rows = [["Time", "To", "Status", "Message"]] + [
                [Paragraph(esc(str(a.get("Time", ""))), cell), Paragraph(esc(str(a.get("To", ""))), cell),
                 Paragraph(esc(str(a.get("Status", ""))), cell), Paragraph(esc(str(a.get("Message", ""))), cell)] for a in log[:25]]
            story.append(table(rows, [22 * mm, 32 * mm, 22 * mm, width - 76 * mm]))
        else:
            story.append(Paragraph("No alerts were triggered by this dashboard during the current session.", body))

    story += [Spacer(1, 10), Paragraph(
        "Notes: strength values are maturity-based estimates (Nurse-Saul method). They are not laboratory compression-test "
        "results. Confirm critical decisions, such as formwork removal or loading, with measured cube tests and the engineer in charge.", small)]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(16 * mm, 9 * mm, "IoT Based Concrete Curing & Strength Monitoring System")
        canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=16 * mm,
                      title=opts["title"], author=str(ss.operator)).build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def readings_export_frame(df):
    out = df[["ts", "elapsed", "core", "surface", "ambient", "maturity", "strength", "strength_basis"]].copy()
    out.columns = ["Date & Time", "Elapsed (h)", "Core Temp (°C)", "Surface Temp (°C)", "Ambient Temp (°C)",
                   "Maturity (°C·hr)", "Estimated Strength (MPa)", "Strength Basis"]
    return out


def build_excel_report(df, cmp, summary):
    from openpyxl.styles import Alignment, Font, PatternFill
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame(summary, columns=["Parameter", "Value"]).to_excel(xw, sheet_name="Summary", index=False)
        readings = readings_export_frame(df)
        num_cols = readings.select_dtypes("number").columns
        readings[num_cols] = readings[num_cols].round(2)
        readings.to_excel(xw, sheet_name="Readings", index=False)
        cmp.to_excel(xw, sheet_name="Cube Comparison", index=False)
        if st.session_state.alert_log:
            pd.DataFrame(st.session_state.alert_log).to_excel(xw, sheet_name="Session Alerts", index=False)
        for ws in xw.book.worksheets:
            for c in ws[1]:
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = PatternFill("solid", fgColor="0D3B4A")
                c.alignment = Alignment(vertical="center")
            for col in ws.columns:
                longest = max(len(str(c.value)) if c.value is not None else 0 for c in col[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(12, longest + 3), 60)
            ws.freeze_panes = "A2"
    return buf.getvalue()


def page_report():
    ss = st.session_state
    df = get_data()
    if not data_ready(df):
        return
    source_banner(df)
    cmp = comparison_df(df)
    summary = report_summary(df)
    signature = (ss.source_choice, len(df), str(df["ts"].iloc[-1]), ss.grade, ss.alert_temp, ss.datum_temp)

    left, right = st.columns([1, 1.25])
    with left:
        with st.container(border=True):
            st.markdown('<div class="card-title">Report Settings</div>', unsafe_allow_html=True)
            title = st.text_input("Report title", value="Concrete Curing & Strength Monitoring Report", key="r_title")
            st.markdown("**Include in the PDF report**")
            o_charts = st.checkbox("Charts (temperature, maturity, strength)", value=True, key="r_charts")
            o_cube = st.checkbox("Cube test records", value=True, key="r_cube")
            o_data = st.checkbox("Latest 15 readings", value=True, key="r_data")
            o_alerts = st.checkbox("Alerts triggered this session", value=True, key="r_alerts")
            generate = st.button("Generate report", type="primary", use_container_width=True, key="r_gen", icon=":material/description:")
    with right:
        with st.container(border=True):
            st.markdown('<div class="card-title">Report Preview</div>', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(summary, columns=["Parameter", "Value"]), hide_index=True, use_container_width=True, height=360)

    if generate:
        files, errors = {}, []
        with st.spinner("Building your report..."):
            files["csv"] = readings_export_frame(df).to_csv(index=False).encode("utf-8")
            try:
                files["xlsx"] = build_excel_report(df, cmp, summary)
            except Exception as exc:
                errors.append(f"Excel report unavailable ({exc}). Install it with: pip install openpyxl")
            try:
                files["pdf"] = build_pdf_report(df, cmp, {"title": title, "summary": summary, "charts": o_charts,
                                                          "cube": o_cube, "data": o_data, "alerts": o_alerts})
            except ImportError as exc:
                errors.append(f"PDF report unavailable ({exc}). Install it with: pip install reportlab matplotlib")
            except Exception as exc:
                errors.append(f"PDF report failed: {exc}")
        files["stamp"] = datetime.now().strftime("%Y%m%d_%H%M")
        files["signature"] = signature
        files["errors"] = errors
        ss.report_files = files

    rf = ss.get("report_files")
    st.write("")
    with st.container(border=True):
        st.markdown('<div class="card-title">Download</div>', unsafe_allow_html=True)
        if not rf:
            st.caption("Choose what to include, then press Generate report. PDF, Excel and CSV downloads will appear here.")
        else:
            if rf.get("signature") != signature:
                st.warning("The data or settings have changed since this report was generated. Press Generate report to refresh it.")
            for message in rf.get("errors", []):
                st.warning(message)
            d1, d2, d3 = st.columns(3)
            stamp = rf["stamp"]
            if "pdf" in rf:
                d1.download_button("Download PDF report", rf["pdf"], f"concrete_curing_report_{stamp}.pdf",
                                   "application/pdf", use_container_width=True, key="r_dl_pdf", icon=":material/picture_as_pdf:")
            if "xlsx" in rf:
                d2.download_button("Download Excel workbook", rf["xlsx"], f"concrete_curing_report_{stamp}.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True, key="r_dl_xlsx", icon=":material/table_view:")
            d3.download_button("Download readings (CSV)", rf["csv"], f"monitoring_data_{stamp}.csv", "text/csv",
                               use_container_width=True, key="r_dl_csv", icon=":material/csv:")
            st.caption(f"Generated {stamp[:4]}-{stamp[4:6]}-{stamp[6:8]} {stamp[9:11]}:{stamp[11:]} from {ss.data_source}.")


PAGE_FUNCS = {
    "Home": page_home,
    "Dashboard": page_dashboard,
    "Live Monitoring": page_live,
    "Cube Test Comparison": page_compare,
    "Upload Dataset": page_upload,
    "Temperature Alerts": page_alerts,
    "Cube Test Data": page_cube,
    "Download Report": page_report,
    "Settings": page_settings,
}
PAGE_SUBTITLE = {
    "Home": "Welcome to the concrete curing monitoring system.",
    "Dashboard": "Monitor live sensor data, compare with cube test results and track maturity & strength.",
    "Live Monitoring": "Real-time temperature, maturity and predicted strength from the embedded sensors.",
    "Cube Test Comparison": "Compare maturity-based live strength against lab cube compression results.",
    "Upload Dataset": "Load a CSV or Excel file of sensor readings to drive the whole dashboard.",
    "Temperature Alerts": "Configure temperature limits and email notifications.",
    "Cube Test Data": "Record and review compression test results.",
    "Download Report": "Generate and download a PDF, Excel or CSV report of the monitoring data.",
    "Settings": "Maturity method, refresh behaviour and operator details.",
}


# Authentication removed: dashboard opens directly.

# ============================================================== SIDEBAR
def goto(p):
    st.session_state.page = p


with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="brand-logo">'
        '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="#ffffff" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M3 20h18"/><rect x="5" y="12" width="14" height="8" rx="1"/>'
        '<path d="M12 3v9"/><circle cx="12" cy="4" r="1.1"/></svg></div>'
        '<div class="brand-title">IoT Based Concrete<br>Curing &amp; Strength<br>Monitoring System</div></div>'
        '<div class="brand-sub">Smarter Curing &nbsp;|&nbsp; Stronger Structures</div>',
        unsafe_allow_html=True,
    )
    current = st.session_state.page
    for name in SIDEBAR:
        st.button(name, key=f"nav_{name}", use_container_width=True,
                  type="primary" if current == name else "secondary", on_click=goto, args=(name,))
    st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
    st.markdown(
        f'<div class="side-box">Concrete Grade<br><b>{_html.escape(str(st.session_state.grade))}</b></div>'
        f'<div class="side-box" style="font-size:.78rem">Project: <b style="font-size:.82rem">{_html.escape(str(st.session_state.project))}</b><br>'
        f'Created by: <b style="font-size:.82rem">{_html.escape(str(st.session_state.operator))}</b></div>',
        unsafe_allow_html=True,
    )

# ============================================================== HEADER + TOP TABS
page = st.session_state.page


source_options = ["ThingSpeak live", "Uploaded File", "Supabase", "Demo (sample data)"]
# Apply programmatic changes before the widget is created (Streamlit requirement).
if st.session_state.pop("_sync_source_choice_widget", False):
    st.session_state["source_choice_widget"] = st.session_state.get("source_choice", "ThingSpeak live")


def on_source_choice_change():
    st.session_state["source_choice"] = st.session_state["source_choice_widget"]


def render_source_selector():
    st.selectbox(
        "Dashboard data source", source_options,
        key="source_choice_widget", on_change=on_source_choice_change,
        help="Choose Uploaded File after uploading to display your CSV/Excel data in every chart. ThingSpeak live never silently switches to demo readings."
    )


if page == "Upload Dataset":
    # Nothing but the page title until a file has been uploaded.
    st.markdown('<h1 class="page-title">Upload Dataset</h1>', unsafe_allow_html=True)
    st.write("")
elif page != "Home":
    render_source_selector()
    _df_hdr = get_data()
    h1, h2, h3 = st.columns([5, 1.3, 1.2])
    with h1:
        title = "Concrete Curing & Strength Monitoring Dashboard" if page == "Dashboard" else page
        st.markdown(f'<h1 class="page-title">{title}</h1><p class="page-sub">{PAGE_SUBTITLE[page]}</p>', unsafe_allow_html=True)
    with h2:
        st.markdown(f'<div class="upd">Last Sensor Reading<br><b>{_df_hdr["ts"].iloc[-1].strftime("%Y-%m-%d %H:%M") if not _df_hdr.empty else "Awaiting readings"}</b></div>', unsafe_allow_html=True)
    with h3:
        status_label = ("ThingSpeak · check reading age" if st.session_state.data_source == "ThingSpeak" else
                        f"{st.session_state.data_source} · NOT LIVE")
        st.markdown(f'<div style="text-align:right"><span class="pill-online">{status_label}</span></div>', unsafe_allow_html=True)
    st.write("")

# ============================================================== ROUTER
PAGE_FUNCS[page]()
