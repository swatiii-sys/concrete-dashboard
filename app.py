"""
IoT Based Concrete Curing & Strength Monitoring System
Professional multi-tab Streamlit dashboard.

Run:  streamlit run app.py
"""
import os
import time
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
