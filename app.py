import streamlit as st
from supabase import create_client
import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # This line tells Python to read your .env file

# 1. Connect to Supabase
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)