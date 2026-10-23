import os
import io
import json
import zipfile
import datetime
import urllib.parse
import requests
import pandas as pd
import streamlit as st
from PIL import Image
import piexif

# Database Drivers (Neon PostgreSQL + SQLite Fallback)
try:
    import pg8000.dbapi as pg8000_db
except ImportError:
    pg8000_db = None
import sqlite3

# Gemini SDK (Supports both new google-genai and legacy google-generativeai)
try:
    from google import genai
    from google.genai import types
    GENAI_SDK = "new"
except ImportError:
    try:
        import google.generativeai as genai_legacy
        GENAI_SDK = "legacy"
    except ImportError:
        GENAI_SDK = None

st.set_page_config(
    page_title="GBP Synergy & Local SEO Suite | BC RankEngine",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# CALEB ULKU SUITE CUSTOM THEME (DARK OBSIDIAN, AMBER-GOLD SIDEBAR & EMERALD UI)
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    /* Global App Background & Typography */
    .stApp {
        background-color: #0b0d12 !important;
        color: #f3f4f6 !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    /* Reduce bulky default Streamlit top padding */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
        max-width: 98% !important;
    }

    /* Warm Dark Amber/Brown Sidebar (Matches Caleb Ulku Entity Profile Panel) */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #16110b 0%, #0e0b08 100%) !important;
        border-right: 1px solid #78350f !important;
    }
    section[data-testid="stSidebar"] label p {
        color: #fbbf24 !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        text-decoration: underline dotted #b45309;
        text-underline-offset: 4px;
    }

    /* Sidebar Inputs */
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] textarea,
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
        background-color: #090a0f !important;
        border: 1px solid #3b2814 !important;
        color: #f9fafb !important;
        border-radius: 6px !important;
    }
    section[data-testid="stSidebar"] input:focus,
    section[data-testid="stSidebar"] textarea:focus {
        border-color: #f59e0b !important;
        box-shadow: 0 0 0 1px #f59e0b !important;
    }

    /* Sidebar Primary Buttons -> Vibrant Gold/Orange (#f59e0b) */
    section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: linear-gradient(180deg, #f59e0b 0%, #d97706 100%) !important;
        color: #090a0f !important;
        font-weight: 700 !important;
        border: 1px solid #fbbf24 !important;
        border-radius: 8px !important;
        padding: 0.55rem 1rem !important;
        box-shadow: 0 3px 10px rgba(245, 158, 11, 0.25) !important;
    }
    section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
        background: linear-gradient(180deg, #fbbf24 0%, #f59e0b 100%) !important;
        color: #000000 !important;
    }

    /* Sidebar Secondary Buttons -> Dark Bronze Badge Style */
    section[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
        background-color: #271c10 !important;
        color: #fbbf24 !important;
        border: 1px solid #78350f !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
    }
    section[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
        background-color: #3b2814 !important;
        border-color: #f59e0b !important;
    }

    /* Main Workspace Primary Action Buttons -> Emerald Green (#10b981) */
    .main .stButton > button[kind="primary"],
    .main .stDownloadButton > button[kind="primary"] {
        background: linear-gradient(180deg, #10b981 0%, #059669 100%) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        border: 1px solid #34d399 !important;
        border-radius: 8px !important;
        padding: 0.55rem 1.2rem !important;
        box-shadow: 0 3px 12px rgba(16, 185, 129, 0.25) !important;
    }
    .main .stButton > button[kind="primary"]:hover,
    .main .stDownloadButton > button[kind="primary"]:hover {
        background: linear-gradient(180deg, #34d399 0%, #10b981 100%) !important;
        color: #052e16 !important;
    }

    /* Main Workspace Secondary Action Buttons -> Clean Slate Dark Button */
    .main .stButton > button[kind="secondary"],
    .main .stDownloadButton > button[kind="secondary"] {
        background-color: #1e2330 !important;
        color: #e5e7eb !important;
        border: 1px solid #374151 !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
    }
    .main .stButton > button[kind="secondary"]:hover,
    .main .stDownloadButton > button[kind="secondary"]:hover {
        border-color: #10b981 !important;
        color: #10b981 !important;
        background-color: #161b26 !important;
    }

    /* Navigation Tabs (Matches Caleb Ulku Top Tab Bar) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px !important;
        background-color: #11131a !important;
        padding: 8px 10px 0px 10px !important;
        border-radius: 10px 10px 0 0 !important;
        border: 1px solid #1f2430 !important;
        border-bottom: 2px solid #1e293b !important;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent !important;
        border: none !important;
        color: #9ca3af !important;
        padding: 10px 16px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #f3f4f6 !important;
        background-color: #181c26 !important;
        border-radius: 6px 6px 0 0 !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #122420 !important;
        color: #10b981 !important;
        border-bottom: 3px solid #10b981 !important;
        border-radius: 6px 6px 0 0 !important;
    }

    /* Monospace Dark Code Console Textareas */
    .main textarea {
        background-color: #080a0f !important;
        border: 1px solid #262b38 !important;
        color: #e2e8f0 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.86rem !important;
        line-height: 1.55 !important;
        border-radius: 8px !important;
    }
    .main textarea:focus {
        border-color: #10b981 !important;
        box-shadow: 0 0 0 1px #10b981 !important;
    }

    /* Main Text Inputs */
    .main input {
        background-color: #080a0f !important;
        border: 1px solid #262b38 !important;
        color: #f3f4f6 !important;
        border-radius: 8px !important;
    }

    /* Bordered Cards (st.container(border=True)) */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #11141c !important;
        border: 1px solid #222736 !important;
        border-radius: 12px !important;
        padding: 1.1rem !important;
    }

    /* Header Badges */
    .cu-header-bar {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
        margin-bottom: 4px;
    }
    .cu-title {
        font-size: 1.35rem;
        font-weight: 700;
        color: #ffffff;
        margin: 0;
    }
    .cu-badge-gold {
        background-color: #2b1d0c;
        color: #f59e0b;
        border: 1px solid #92400e;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .cu-badge-green {
        background-color: #07291e;
        color: #34d399;
        border: 1px solid #059669;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .cu-col-header-gold {
        color: #f59e0b;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .cu-col-header-green {
        color: #10b981;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .cu-col-header-purple {
        color: #c084fc;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
</style>
""", unsafe_allow_html=True)

# --- SECRETS & CONFIG ---
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL and hasattr(st, "secrets") and "DATABASE_URL" in st.secrets:
    DATABASE_URL = st.secrets["DATABASE_URL"].strip()

USE_POSTGRES = bool(DATABASE_URL and pg8000_db is not None)

env_gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
if not env_gemini_key and hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
    env_gemini_key = st.secrets["GEMINI_API_KEY"].strip()

if "api_key" not in st.session_state:
    st.session_state["api_key"] = env_gemini_key
if "selected_model" not in st.session_state:
    st.session_state["selected_model"] = "gemini-3.8-flash"

# --- DATABASE ENGINE & AUTO-MIGRATION ---
def get_db_conn():
    if USE_POSTGRES:
        parsed = urllib.parse.urlparse(DATABASE_URL)
        return pg8000_db.connect(
            user=urllib.parse.unquote(parsed.username or ""),
            password=urllib.parse.unquote(parsed.password or ""),
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/"),
            ssl_context=True
        )
    return sqlite3.connect("bc_rankengine_local.db")

def init_and_migrate_db():
    conn = get_db_conn()
    cur = conn.cursor()
    if USE_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id SERIAL PRIMARY KEY,
                business_name TEXT NOT NULL,
                primary_niche TEXT DEFAULT '',
                target_city TEXT DEFAULT '',
                years_in_business TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                usp TEXT DEFAULT '',
                website_url TEXT DEFAULT '',
                street_address TEXT DEFAULT '',
                latitude TEXT DEFAULT '',
                longitude TEXT DEFAULT '',
                place_id TEXT DEFAULT '',
                gbp_location_id TEXT DEFAULT '',
                services_list TEXT DEFAULT '',
                categories_list TEXT DEFAULT '',
                gbp_description TEXT DEFAULT '',
                silo_architecture TEXT DEFAULT '',
                posts_json TEXT DEFAULT '[]',
                review_scripts TEXT DEFAULT '',
                verification_json TEXT DEFAULT '{}',
                video_script TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        new_cols = [
            ("primary_niche", "TEXT DEFAULT ''"),
            ("target_city", "TEXT DEFAULT ''"),
            ("years_in_business", "TEXT DEFAULT ''"),
            ("phone", "TEXT DEFAULT ''"),
            ("usp", "TEXT DEFAULT ''"),
            ("website_url", "TEXT DEFAULT ''"),
            ("street_address", "TEXT DEFAULT ''"),
            ("latitude", "TEXT DEFAULT ''"),
            ("longitude", "TEXT DEFAULT ''"),
            ("place_id", "TEXT DEFAULT ''"),
            ("gbp_location_id", "TEXT DEFAULT ''"),
            ("services_list", "TEXT DEFAULT ''"),
            ("categories_list", "TEXT DEFAULT ''"),
            ("gbp_description", "TEXT DEFAULT ''"),
            ("silo_architecture", "TEXT DEFAULT ''"),
            ("posts_json", "TEXT DEFAULT '[]'"),
            ("review_scripts", "TEXT DEFAULT ''"),
            ("verification_json", "TEXT DEFAULT '{}'"),
            ("video_script", "TEXT DEFAULT ''")
        ]
        for col_name, col_type in new_cols:
            try:
                cur.execute(f"ALTER TABLE clients ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                conn.commit()
            except Exception:
                conn.rollback()
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name TEXT NOT NULL,
                primary_niche TEXT DEFAULT '',
                target_city TEXT DEFAULT '',
                years_in_business TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                usp TEXT DEFAULT '',
                website_url TEXT DEFAULT '',
                street_address TEXT DEFAULT '',
                latitude TEXT DEFAULT '',
                longitude TEXT DEFAULT '',
                place_id TEXT DEFAULT '',
                gbp_location_id TEXT DEFAULT '',
                services_list TEXT DEFAULT '',
                categories_list TEXT DEFAULT '',
                gbp_description TEXT DEFAULT '',
                silo_architecture TEXT DEFAULT '',
                posts_json TEXT DEFAULT '[]',
                review_scripts TEXT DEFAULT '',
                verification_json TEXT DEFAULT '{}',
                video_script TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    cur.close()
    conn.close()

init_and_migrate_db()

def fetch_all_clients():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, business_name, primary_niche, target_city, years_in_business,
               phone, usp, website_url, street_address, latitude, longitude,
               place_id, gbp_location_id, services_list, categories_list,
               gbp_description, silo_architecture, posts_json, review_scripts,
               verification_json, video_script
        FROM clients ORDER BY business_name ASC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    cols = [
        "id", "business_name", "primary_niche", "target_city", "years_in_business",
        "phone", "usp", "website_url", "street_address", "latitude", "longitude",
        "place_id", "gbp_location_id", "services_list", "categories_list",
        "gbp_description", "silo_architecture", "posts_json", "review_scripts",
        "verification_json", "video_script"
    ]
    return [dict(zip(cols, r)) for r in rows]

def save_client_data(client_id, data_dict):
    conn = get_db_conn()
    cur = conn.cursor()
    ph = "%s" if USE_POSTGRES else "?"
    set_clause = ", ".join([f"{k} = {ph}" for k in data_dict.keys()])
    values = list(data_dict.values()) + [client_id]
    cur.execute(f"UPDATE clients SET {set_clause} WHERE id = {ph}", values)
    conn.commit()
    cur.close()
    conn.close()

def create_new_client(name, niche, city, years, phone, usp, url, addr, lat, lon):
    conn = get_db_conn()
    cur = conn.cursor()
    ph = "%s" if USE_POSTGRES else "?"
    if USE_POSTGRES:
        cur.execute(f"""
            INSERT INTO clients (business_name, primary_niche, target_city, years_in_business, phone, usp, website_url, street_address, latitude, longitude)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph}) RETURNING id
        """, (name, niche, city, years, phone, usp, url, addr, lat, lon))
        new_id = cur.fetchone()[0]
    else:
        cur.execute(f"""
            INSERT INTO clients (business_name, primary_niche, target_city, years_in_business, phone, usp, website_url, street_address, latitude, longitude)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
        """, (name, niche, city, years, phone, usp, url, addr, lat, lon))
        new_id = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return new_id

def delete_client_record(client_id):
    conn = get_db_conn()
    cur = conn.cursor()
    ph = "%s" if USE_POSTGRES else "?"
    cur.execute(f"DELETE FROM clients WHERE id = {ph}", (client_id,))
    conn.commit()
    cur.close()
    conn.close()

# --- AI & GEOCODING HELPERS ---
def call_gemini(prompt, use_search=False):
    api_key = st.session_state.get("api_key", "").strip()
    if not api_key:
        st.error("⚠️ Please provide a valid Gemini API Key in the top configuration bar or Streamlit Secrets.")
        return ""

    primary_model = st.session_state.get("selected_model", "gemini-3.8-flash")
    fallback_models = [primary_model, "gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash"]
    # Remove duplicates while preserving order
    models_to_try = list(dict.fromkeys(fallback_models))

    last_err = None
    for m_name in models_to_try:
        try:
            if GENAI_SDK == "new":
                client = genai.Client(api_key=api_key)
                config = types.GenerateContentConfig(temperature=0.3)
                if use_search:
                    config.tools = [{"google_search": {}}]
                resp = client.models.generate_content(
                    model=m_name,
                    contents=prompt,
                    config=config
                )
                st.session_state["selected_model"] = m_name
                return resp.text
            elif GENAI_SDK == "legacy":
                genai_legacy.configure(api_key=api_key)
                model = genai_legacy.GenerativeModel(m_name)
                resp = model.generate_content(prompt)
                st.session_state["selected_model"] = m_name
                return resp.text
        except Exception as e:
            last_err = e
            continue

    st.error(f"Gemini API Error: {str(last_err)}")
    return ""

def geocode_address(address):
    if not address.strip():
        return None, None
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json", "limit": 1}
        headers = {"User-Agent": "BC_RankEngine_SEO_Suite/3.0"}
        r = requests.get(url, params=params, headers=headers, timeout=8)
        data = r.json()
        if data:
            return str(round(float(data[0]["lat"]), 6)), str(round(float(data[0]["lon"]), 6))
    except Exception:
        pass
    return None, None

# --- EXIF GPS INJECTION HELPERS ---
def deg_to_dms_rational(deg_float):
    deg_abs = abs(float(deg_float))
    d = int(deg_abs)
    m_float = (deg_abs - d) * 60
    m = int(m_float)
    s = int(round((m_float - m) * 60 * 10000))
    return ((d, 1), (m, 1), (s, 10000))

def inject_exif_gps(image_bytes, lat_float, lon_float, business_name, description):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")
    
    try:
        exif_dict = piexif.load(img.info.get("exif", b""))
    except Exception:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    lat_ref = b"N" if lat_float >= 0 else b"S"
    lon_ref = b"E" if lon_float >= 0 else b"W"

    exif_dict["GPS"][piexif.GPSIFD.GPSVersionID] = (2, 0, 0, 0)
    exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = lat_ref
    exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = deg_to_dms_rational(lat_float)
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = lon_ref
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = deg_to_dms_rational(lon_float)

    if business_name:
        exif_dict["0th"][piexif.ImageIFD.Artist] = business_name.encode("utf-8")
        exif_dict["0th"][piexif.ImageIFD.Copyright] = business_name.encode("utf-8")
    if description:
        exif_dict["0th"][piexif.ImageIFD.ImageDescription] = description.encode("utf-8")

    exif_bytes = piexif.dump(exif_dict)
    out_buf = io.BytesIO()
    img.save(out_buf, format="JPEG", exif=exif_bytes, quality=95)
    return out_buf.getvalue()

def build_ics_reminder(business_name):
    now = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    start_dt = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).strftime("%Y%m%dT140000Z")
    end_dt = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).strftime("%Y%m%dT143000Z")
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Brushy Creek Media//BC RankEngine//EN",
        "BEGIN:VEVENT",
        f"UID:gbp-cadence-{int(datetime.datetime.utcnow().timestamp())}@bcrankengine",
        f"DTSTAMP:{now}",
        f"DTSTART:{start_dt}",
        f"DTEND:{end_dt}",
        "RRULE:FREQ=DAILY;INTERVAL=60",
        f"SUMMARY:GBP 60-Day Holiday Hours & Audit Check - {business_name}",
        "DESCRIPTION:1. Update upcoming Google Business Profile Holiday Hours.\\n2. Reject unauthorized user-suggested edits.\\n3. Upload fresh geotagged job-site photos.",
        "END:VEVENT",
        "END:VCALENDAR"
    ]
    return "\r\n".join(ics_lines)

# ==============================================================================
# TOP HEADER & MODEL BAR (MATCHES SCREENSHOT HEADER)
# ==============================================================================
db_status_text = "Neon Cloud DB Connected" if USE_POSTGRES else "Local SQLite Mode"
st.markdown(f"""
<div class="cu-header-bar">
    <span style="font-size: 1.6rem;">📍</span>
    <span class="cu-title">GBP Synergy & Local SEO Suite</span>
    <span class="cu-badge-gold">Caleb Ulku Framework</span>
    <span class="cu-badge-green">Auto-Switched: {st.session_state.get('selected_model', 'gemini-3.8-flash')}</span>
    <span class="cu-badge-green">{db_status_text}</span>
</div>
<p style="color: #9ca3af; font-size: 0.85rem; margin-top: 2px; margin-bottom: 14px;">
    Hover over any (?) icon for Official Google Guidelines • Live Web Auto-Fill Enabled
</p>
""", unsafe_allow_html=True)

with st.container(border=True):
    t_col1, t_col2, t_col3 = st.columns([2, 2, 1.2])
    with t_col1:
        model_options = ["gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash"]
        curr_m = st.session_state.get("selected_model", "gemini-3.8-flash")
        m_idx = model_options.index(curr_m) if curr_m in model_options else 0
        chosen_model = st.selectbox(
            "AI Model Engine",
            model_options,
            index=m_idx,
            label_visibility="collapsed",
            help="Select the active Google Gemini Flash model."
        )
        st.session_state["selected_model"] = chosen_model
    with t_col2:
        key_input = st.text_input(
            "Gemini API Key",
            value=st.session_state["api_key"],
            type="password",
            placeholder="Paste Google Gemini API Key...",
            label_visibility="collapsed"
        )
        if key_input != st.session_state["api_key"]:
            st.session_state["api_key"] = key_input
    with t_col3:
        if st.button("✅ Test Key & Sync Models", use_container_width=True, type="secondary"):
            res = call_gemini("Reply with: 'API Connected & Active!'")
            if res:
                st.toast(f"✅ {res.strip()}", icon="🟢")

# ==============================================================================
# SIDEBAR: BUSINESS ENTITY PROFILE (GOLD / AMBER THEME)
# ==============================================================================
clients = fetch_all_clients()
client_names = ["+ Create New Client Profile"] + [f"{c['business_name']} ({c['target_city']})" for c in clients]

with st.sidebar:
    st.markdown("""
    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom: 8px;">
        <span style="color:#fbbf24; font-weight:700; font-size:1.05rem;">🏢 Business Entity Profile</span>
        <span class="cu-badge-gold">Cloud Sync</span>
    </div>
    """, unsafe_allow_html=True)

    selected_idx = st.selectbox(
        "Active Client Profile",
        range(len(client_names)),
        format_func=lambda i: client_names[i],
        help="Switch between saved clients in your Neon PostgreSQL database, or select '+ Create New Client Profile'."
    )

    col_ex1, col_ex2 = st.columns(2)
    with col_ex1:
        if st.button("Load Example", use_container_width=True, type="secondary", help="Load Shearrer's Appliance Service sample data."):
            st.session_state["form_bname"] = "Shearrer's Appliance Service"
            st.session_state["form_niche"] = "Appliance Repair"
            st.session_state["form_city"] = "Piedmont, Missouri"
            st.session_state["form_years"] = "15 +"
            st.session_state["form_phone"] = "573-998-2337"
            st.session_state["form_usp"] = "More than 30 years of appliance repair knowledge. Repair of all makes and models. HVAC, microwaves, refrigerators, freezers, cook ranges, washers and dryers."
            st.session_state["form_url"] = "https://shearrersappliance.com"
            st.session_state["form_addr"] = "31558 State Highway 49, Williamsville, MO 63967"
            st.session_state["form_lat"] = "36.974096"
            st.session_state["form_lon"] = "-90.574269"
            st.rerun()
    with col_ex2:
        if st.button("Clear / Delete", use_container_width=True, type="secondary", help="Clear fields or delete saved client from database."):
            if selected_idx > 0:
                delete_client_record(clients[selected_idx - 1]["id"])
            st.session_state["loaded_client_id"] = -1
            st.rerun()

    active_client = clients[selected_idx - 1] if selected_idx > 0 else None
    current_client_id = active_client["id"] if active_client else 0

    if st.session_state.get("loaded_client_id") != current_client_id:
        st.session_state["loaded_client_id"] = current_client_id
        st.session_state["form_bname"] = active_client["business_name"] if active_client else ""
        st.session_state["form_niche"] = active_client["primary_niche"] if active_client else ""
        st.session_state["form_city"] = active_client["target_city"] if active_client else ""
        st.session_state["form_years"] = active_client["years_in_business"] if active_client else ""
        st.session_state["form_phone"] = active_client["phone"] if active_client else ""
        st.session_state["form_usp"] = active_client["usp"] if active_client else ""
        st.session_state["form_url"] = active_client["website_url"] if active_client else ""
        st.session_state["form_addr"] = active_client["street_address"] if active_client else ""
        st.session_state["form_lat"] = active_client["latitude"] if active_client else ""
        st.session_state["form_lon"] = active_client["longitude"] if active_client else ""

    b_name = st.text_input(
        "Business Legal Name",
        key="form_bname",
        help="Google Guideline: Use your exact real-world legal business name as shown on signage, LLC docs, and utility bills. Never stuff keywords here."
    )

    if st.button("🌐 Search Web & Auto-Fill Business Info", use_container_width=True, type="primary", help="Uses Gemini 3.8 Flash with Google Search Grounding to look up this business online and auto-populate its niche, phone, address, and USP."):
        if not b_name.strip():
            st.warning("Enter a Business Legal Name first.")
        else:
            with st.spinner(f"Searching web for {b_name}..."):
                lookup_prompt = f"""
                Search the web for the business "{b_name}" {st.session_state.get('form_city', '')}.
                Return ONLY a valid JSON object with these exact keys (use empty string if unknown):
                {{
                  "primary_niche": "Primary GBP category (e.g. Appliance Repair)",
                  "target_city": "City, State",
                  "years_in_business": "e.g. 15+",
                  "phone": "Local phone number",
                  "usp": "2-3 sentence summary of specialties, brands serviced, and unique selling proposition",
                  "website_url": "Official website URL",
                  "street_address": "Full street address",
                  "latitude": "Decimal latitude",
                  "longitude": "Decimal longitude"
                }}
                """
                raw = call_gemini(lookup_prompt, use_search=True)
                if raw:
                    try:
                        clean_json = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                        parsed_info = json.loads(clean_json)
                        st.session_state["form_niche"] = parsed_info.get("primary_niche") or st.session_state["form_niche"]
                        st.session_state["form_city"] = parsed_info.get("target_city") or st.session_state["form_city"]
                        st.session_state["form_years"] = parsed_info.get("years_in_business") or st.session_state["form_years"]
                        st.session_state["form_phone"] = parsed_info.get("phone") or st.session_state["form_phone"]
                        st.session_state["form_usp"] = parsed_info.get("usp") or st.session_state["form_usp"]
                        st.session_state["form_url"] = parsed_info.get("website_url") or st.session_state["form_url"]
                        st.session_state["form_addr"] = parsed_info.get("street_address") or st.session_state["form_addr"]
                        st.session_state["form_lat"] = str(parsed_info.get("latitude") or st.session_state["form_lat"])
                        st.session_state["form_lon"] = str(parsed_info.get("longitude") or st.session_state["form_lon"])
                        st.rerun()
                    except Exception:
                        st.warning("Could not parse structured web results automatically. Check fields manually.")

    c_niche, c_city = st.columns(2)
    with c_niche:
        b_niche = st.text_input(
            "Primary Niche",
            key="form_niche",
            help="Google Guideline: Your #1 primary GBP category dictates the core search queries you rank for."
        )
    with c_city:
        b_city = st.text_input(
            "Target City & State",
            key="form_city",
            help="The primary city and state where the client wants to rank in the Local 3-Pack."
        )

    c_yr, c_ph = st.columns(2)
    with c_yr:
        b_years = st.text_input(
            "Years in Business",
            key="form_years",
            help="Used to build authority in your 750-character description and GBP opening date."
        )
    with c_ph:
        b_phone = st.text_input(
            "Phone Number",
            key="form_phone",
            help="Google Guideline: Must match your website NAP (Name, Address, Phone) 100% across all citations."
        )

    b_usp = st.text_area(
        "Unique Selling Proposition (USP)",
        key="form_usp",
        height=88,
        help="Specialties, certifications, warranties, or specific equipment/brands serviced."
    )

    b_url = st.text_input(
        "Website URL",
        key="form_url",
        help="The primary website URL linked to the Google Business Profile."
    )

    b_addr = st.text_input(
        "Full Street Address (for Geotagging)",
        key="form_addr",
        help="Even if you hide your address as a Service Area Business, enter your physical shop address or target city center here to geotag photos."
    )

    if st.button("🧭 Auto-Fill GPS Coordinates from Address", use_container_width=True, type="secondary", help="Converts the street address above into exact GPS Latitude and Longitude coordinates."):
        lat_res, lon_res = geocode_address(b_addr or b_city)
        if lat_res and lon_res:
            st.session_state["form_lat"] = lat_res
            st.session_state["form_lon"] = lon_res
            st.rerun()
        else:
            st.warning("Could not geocode address. Try entering 'City, State'.")

    c_lat, c_lon = st.columns(2)
    with c_lat:
        b_lat = st.text_input(
            "Latitude",
            key="form_lat",
            help="Decimal latitude injected into client JPEG EXIF metadata."
        )
    with c_lon:
        b_lon = st.text_input(
            "Longitude",
            key="form_lon",
            help="Decimal longitude injected into client JPEG EXIF metadata."
        )

    st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
    if st.button("💾 Save Profile to Cloud DB", type="primary", use_container_width=True, help="Saves this client profile permanently to your Neon PostgreSQL database."):
        if not b_name.strip():
            st.error("Business Legal Name is required.")
        elif selected_idx == 0:
            new_id = create_new_client(b_name, b_niche, b_city, b_years, b_phone, b_usp, b_url, b_addr, b_lat, b_lon)
            st.session_state["loaded_client_id"] = new_id
            st.toast(f"✅ Created {b_name} in Cloud DB!")
            st.rerun()
        else:
            save_client_data(current_client_id, {
                "business_name": b_name,
                "primary_niche": b_niche,
                "target_city": b_city,
                "years_in_business": b_years,
                "phone": b_phone,
                "usp": b_usp,
                "website_url": b_url,
                "street_address": b_addr,
                "latitude": b_lat,
                "longitude": b_lon
            })
            st.toast("✅ Saved Client Profile to Neon DB!")
            st.rerun()

# Ensure defaults for active client workspace
client_record = active_client or {
    "id": 0, "services_list": "", "categories_list": "", "gbp_description": "",
    "silo_architecture": "", "posts_json": "[]", "review_scripts": "",
    "verification_json": "{}", "video_script": "", "place_id": "", "gbp_location_id": ""
}

if not b_name.strip():
    st.info("👈 Click **Load Example** in the gold left sidebar, select a saved client, or type a **Business Legal Name** to unlock the 7-tab SEO workspace.")
    st.stop()

# ==============================================================================
# 7-TAB WORKSPACE (CALEB ULKU SUITE + FUTURE API SYNC)
# ==============================================================================
tabs = st.tabs([
    "📚 1. GBP Core Setup (AI)",
    "💻 2. Website Synergy Engine",
    "📅 3. GBP Posts & GHL CSV",
    "🖼️ 4. Bulk EXIF Geotagger",
    "💬 5. Reviews & SMS Engine",
    "🛡️ 6. Verification & Ops",
    "🔌 7. Direct GBP API Sync"
])

# ------------------------------------------------------------------------------
# TAB 1: SERVICES-FIRST GBP ARCHITECTURE
# ------------------------------------------------------------------------------
with tabs[0]:
    with st.container(border=True):
        st.markdown("### Step 1: Services-First GBP Architecture")
        st.caption("Caleb's framework starts by generating 25+ specific services first, then mapping 5 GBP categories to those services, followed by a 750-character USP description. You can freely edit any generated output below.")

        if st.button("✨ Generate All 3 Core Assets", type="primary", help="Generates 25+ granular services, 5 mapped GBP categories, and a 750-character description in one click."):
            with st.spinner("Generating Services-First Architecture via Gemini 3.8 Flash..."):
                prompt_all = f"""
                Act as an elite Local SEO specialist executing the Caleb Ulku GBP framework for:
                Business: {b_name}
                Primary Niche: {b_niche}
                Target City: {b_city}
                Years in Business: {b_years}
                Phone: {b_phone}
                USP: {b_usp}

                Return ONLY a valid JSON object with these 3 exact keys:
                {{
                  "services": "25 to 35 specific, high-intent granular service names (one per line, plain text, no bullets or numbers)",
                  "categories": "Primary GBP category on line 1, followed by 3 to 4 closely related official Google Business Profile secondary categories (one per line, plain text, no bullets)",
                  "description": "A compelling, conversion-focused Google Business Profile description strictly between 600 and 740 characters. Weave in the primary city, core services, years of experience, and call-to-action with phone number. Do NOT exceed 750 characters."
                }}
                """
                raw_res = call_gemini(prompt_all)
                if raw_res:
                    try:
                        clean = raw_res.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                        parsed = json.loads(clean)
                        s_txt = parsed.get("services", "")
                        if isinstance(s_txt, list):
                            s_txt = "\n".join(s_txt)
                        c_txt = parsed.get("categories", "")
                        if isinstance(c_txt, list):
                            c_txt = "\n".join(c_txt)
                        d_txt = str(parsed.get("description", ""))[:750]

                        client_record["services_list"] = s_txt
                        client_record["categories_list"] = c_txt
                        client_record["gbp_description"] = d_txt
                        if current_client_id:
                            save_client_data(current_client_id, {
                                "services_list": s_txt,
                                "categories_list": c_txt,
                                "gbp_description": d_txt
                            })
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not parse JSON response: {e}")

        st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
        col_1a, col_1b, col_1c = st.columns(3)

        with col_1a:
            with st.container(border=True):
                st.markdown('<div class="cu-col-header-gold">1A. 25+ GRANULAR SERVICES (?)</div>', unsafe_allow_html=True)
                st.caption("Editable list — changes save to your cloud database.")
                srv_val = st.text_area(
                    "1A Services",
                    value=client_record.get("services_list", ""),
                    height=330,
                    label_visibility="collapsed",
                    help="Caleb Ulku Rule: Add 25 to 35 specific services under your categories. Google indexes custom services directly for long-tail 'near me' searches."
                )

        with col_1b:
            with st.container(border=True):
                st.markdown('<div class="cu-col-header-green">1B. 5 GBP CATEGORIES (?)</div>', unsafe_allow_html=True)
                st.caption("Primary category on line 1 + up to 4 secondary categories.")
                cat_val = st.text_area(
                    "1B Categories",
                    value=client_record.get("categories_list", ""),
                    height=330,
                    label_visibility="collapsed",
                    help="Google Guideline: Select 1 Primary Category and 3–4 relevant Secondary Categories. Avoid unrelated categories to prevent category dilution."
                )

        with col_1c:
            with st.container(border=True):
                st.markdown('<div class="cu-col-header-purple">1C. 750-CHAR DESCRIPTION (?)</div>', unsafe_allow_html=True)
                st.caption("Editable description — live character counter below.")
                desc_val = st.text_area(
                    "1C Description",
                    value=client_record.get("gbp_description", ""),
                    height=295,
                    label_visibility="collapsed",
                    help="Google Guideline: Maximum 750 characters. No URLs or HTML allowed."
                )
                char_len = len(desc_val)
                badge_color = "#10b981" if char_len <= 750 else "#ef4444"
                st.markdown(f"<span style='color:{badge_color}; font-weight:700; font-family:monospace;'>{char_len} / 750 chars</span>", unsafe_allow_html=True)

        if st.button("💾 Save Step 1 Edits to Cloud Database", type="secondary"):
            if current_client_id:
                save_client_data(current_client_id, {
                    "services_list": srv_val,
                    "categories_list": cat_val,
                    "gbp_description": desc_val[:750]
                })
                st.toast("✅ Step 1 Core Assets saved to Neon DB!")
            else:
                st.warning("Click 'Save Profile to Cloud DB' in the left sidebar first to create this client record.")

# ------------------------------------------------------------------------------
# TAB 2: WEBSITE-TO-GBP BLENDED ALGORITHM SYNERGY
# ------------------------------------------------------------------------------
with tabs[1]:
    with st.container(border=True):
        st.markdown("### Step 2: Website-to-GBP Blended Algorithm Synergy")
        st.caption("Align your website's H1/H2 structure and service pages with your exact GBP categories and services.")

        comp_mode = st.radio(
            "Select Market Competition Tier",
            [
                "Low/Med Comp (Homepage H2s — Rural & Small Town Markets)",
                "High Comp (Dedicated Category Silos — Metro Markets)"
            ],
            horizontal=True,
            help="In smaller towns, placing secondary categories and services as H2/H3 sections directly on the Homepage ranks fastest. In high-competition metro areas, build dedicated Category Silo pages."
        )

        with st.container(border=True):
            st.markdown('<div class="cu-col-header-gold">CATEGORY SILO & HOMEPAGE SYNERGY BUILDER</div>', unsafe_allow_html=True)
            st.caption("Generates URL Slugs, Title Tags, H1s matching your GBP Categories, H2s matching your specific services, and internal linking architecture.")

            if st.button("📂 Build Category Silo Pages & Copy", type="primary"):
                with st.spinner("Building Website-to-GBP Synergy Architecture..."):
                    silo_prompt = f"""
                    Create a complete Website-to-GBP Blended Algorithm Synergy blueprint for:
                    Business: {b_name} ({b_url})
                    Target City: {b_city}
                    Primary Niche: {b_niche}
                    USP: {b_usp}
                    Mode Selected: {comp_mode}
                    GBP Categories:
                    {cat_val}
                    GBP Services:
                    {srv_val}

                    Provide:
                    1. Exact URL Structure, Title Tag, Meta Description, and H1 for the Homepage (`{b_url}`).
                    2. {"Complete Homepage H2/H3 section copy mapping every GBP category and service directly onto the homepage." if "Low/Med" in comp_mode else "Full Silo Page Blueprint + complete copy for all GBP Category pages (URL Slug, Title Tag, H1 matching Category + City, H2s matching exact services, and internal anchor text links pointing back to the homepage)."}
                    3. LocalBusiness JSON-LD Schema markup ready to paste into the website header.
                    """
                    silo_out = call_gemini(silo_prompt)
                    if silo_out:
                        client_record["silo_architecture"] = silo_out
                        if current_client_id:
                            save_client_data(current_client_id, {"silo_architecture": silo_out})
                        st.rerun()

        silo_text = st.text_area(
            "Generated Silo Pages & Internal Linking Architecture (Editable)",
            value=client_record.get("silo_architecture", ""),
            height=420,
            placeholder="Click 'Build Category Silo Pages & Copy' to generate exact-match H1/H2 silo page copy and URL structure..."
        )

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("💾 Save Website Blueprint to DB", use_container_width=True, type="secondary"):
                if current_client_id:
                    save_client_data(current_client_id, {"silo_architecture": silo_text})
                    st.toast("✅ Saved Website Synergy Blueprint!")
        with col_s2:
            st.download_button(
                "📥 Download Silo Blueprint (.md)",
                data=silo_text,
                file_name=f"{b_name.lower().replace(' ', '_')}_website_synergy.md",
                mime="text/markdown",
                use_container_width=True,
                type="primary"
            )

# ------------------------------------------------------------------------------
# TAB 3: 20-WEEK EVERGREEN GBP POST GENERATOR & GHL CSV
# ------------------------------------------------------------------------------
with tabs[2]:
    with st.container(border=True):
        st.markdown("### Step 3: 20-Week Evergreen GBP Post Generator")
        st.caption("\"It only takes a half hour to write and schedule a lifetime of GBP posts.\" Generate 20 non-duplicate posts cycling through your services & export to CSV.")

        try:
            loaded_posts = json.loads(client_record.get("posts_json", "[]") or "[]")
        except Exception:
            loaded_posts = []

        col_btn_p1, col_btn_p2 = st.columns([1, 1])
        with col_btn_p1:
            if st.button("✨ Generate 20 Weekly GBP Posts", type="primary", use_container_width=True, help="Cycles through your Step 1 services to generate 20 unique weekly GBP updates."):
                with st.spinner("Writing 20 Weekly Evergreen GBP Posts..."):
                    services_lines = [s.strip() for s in srv_val.split("\n") if s.strip()]
                    if not services_lines:
                        services_lines = [b_niche or "Professional Service"]
                    selected_20 = [services_lines[i % len(services_lines)] for i in range(20)]

                    posts_prompt = f"""
                    Write 20 unique, high-converting Google Business Profile updates for:
                    Business: {b_name}
                    Target City: {b_city}
                    Phone: {b_phone}
                    USP: {b_usp}
                    Website: {b_url}

                    Cycle through these 20 featured services in order:
                    {json.dumps(selected_20)}

                    Return ONLY a valid JSON array of 20 objects with keys:
                    "week" (e.g. "#1"),
                    "service" (the featured service name),
                    "content" (80 to 130 words, local problem/solution hook, mention {b_city}, mention {b_name}, end with Call {b_phone} or visit {b_url}).
                    """
                    raw_posts = call_gemini(posts_prompt)
                    if raw_posts:
                        try:
                            clean_p = raw_posts.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                            posts_list = json.loads(clean_p)
                            base_date = datetime.date.today() + datetime.timedelta(days=1)
                            enriched = []
                            for idx, item in enumerate(posts_list[:20]):
                                sched_dt = (base_date + datetime.timedelta(days=idx * 7)).strftime("%Y-%m-%d 09:00:00")
                                enriched.append({
                                    "Week": f"#{idx+1}",
                                    "Scheduled Date": sched_dt,
                                    "Featured Service": item.get("service", ""),
                                    "GBP Post Content (Editable)": item.get("content", ""),
                                    "Action Type": "LEARN_MORE",
                                    "Action URL": b_url
                                })
                            client_record["posts_json"] = json.dumps(enriched)
                            if current_client_id:
                                save_client_data(current_client_id, {"posts_json": client_record["posts_json"]})
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error parsing generated posts: {e}")

        if loaded_posts:
            df_posts = pd.DataFrame(loaded_posts)
            with col_btn_p2:
                csv_bytes = df_posts.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📊 Export CSV (GoHighLevel Ready)",
                    data=csv_bytes,
                    file_name=f"{b_name.lower().replace(' ', '_')}_20_week_gbp_posts.csv",
                    mime="text/csv",
                    type="primary",
                    use_container_width=True
                )

            edited_df = st.data_editor(
                df_posts,
                use_container_width=True,
                num_rows="dynamic",
                height=440,
                help="Double-click any cell to edit the post copy or scheduled date."
            )

            if st.button("💾 Save Edited Posts Table to Cloud DB", type="secondary"):
                updated_json = edited_df.to_json(orient="records")
                if current_client_id:
                    save_client_data(current_client_id, {"posts_json": updated_json})
                    st.toast("✅ Saved 20-Week Posts to Neon DB!")
        else:
            st.info("Click **Generate 20 Weekly GBP Posts** above to populate your 20-week schedule.")

# ------------------------------------------------------------------------------
# TAB 4: BULK PHOTO EXIF GEOTAGGER
# ------------------------------------------------------------------------------
with tabs[3]:
    with st.container(border=True):
        st.markdown("### Step 4: Client-Side Bulk Photo EXIF Geotagger")
        st.caption("Inject exact GPS Latitude/Longitude coordinates & business metadata directly into your client's authentic JPEG photos.")

        col_geo1, col_geo2 = st.columns([1.2, 2])
        with col_geo1:
            with st.container(border=True):
                st.markdown('<div class="cu-col-header-gold">TARGET GPS EXIF METADATA</div>', unsafe_allow_html=True)
                st.markdown(f"""
                * **Target Latitude:** `{b_lat or 'Not Set'}`
                * **Target Longitude:** `{b_lon or 'Not Set'}`
                * **Artist / Copyright Tag:** `{b_name}`
                * **Target City:** `{b_city}`
                """)
                st.caption("Google Photo Guideline: Use real, well-lit 720x720px+ job-site, team, or service truck photos. Never use stock photos!")

        with col_geo2:
            with st.container(border=True):
                uploaded_photos = st.file_uploader(
                    "☁️ Drop Client JPEG/PNG Photos Here",
                    type=["jpg", "jpeg", "png"],
                    accept_multiple_files=True,
                    help="Upload multiple client job photos to inject GPS coordinates and download as a ready-to-upload ZIP."
                )

                if uploaded_photos:
                    try:
                        lat_f = float(str(b_lat).replace(",", "").strip())
                        lon_f = float(str(b_lon).replace(",", "").strip())
                        coords_valid = True
                    except ValueError:
                        coords_valid = False
                        st.error("⚠️ Invalid Latitude/Longitude in left sidebar. Click '🧭 Auto-Fill GPS Coordinates' in the sidebar first.")

                    if coords_valid:
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                            for idx, up_file in enumerate(uploaded_photos):
                                meta_desc = f"{b_name} - {b_niche} in {b_city} ({b_phone})"
                                tagged_bytes = inject_exif_gps(
                                    up_file.read(),
                                    lat_f,
                                    lon_f,
                                    b_name,
                                    meta_desc
                                )
                                clean_slug = b_name.lower().replace(" ", "-")
                                out_name = f"{clean_slug}-{b_city.lower().replace(',','').replace(' ','-')}-{idx+1}.jpg"
                                zf.writestr(out_name, tagged_bytes)

                        st.success(f"✅ Injected GPS EXIF tags (`{lat_f}, {lon_f}`) into {len(uploaded_photos)} photo(s)!")
                        st.download_button(
                            "📦 Download Geotagged ZIP",
                            data=zip_buffer.getvalue(),
                            file_name=f"{b_name.lower().replace(' ', '_')}_geotagged_photos.zip",
                            mime="application/zip",
                            type="primary",
                            use_container_width=True
                        )

# ------------------------------------------------------------------------------
# TAB 5: REVIEWS & SMS ENGINE
# ------------------------------------------------------------------------------
with tabs[4]:
    col_r1, col_r2 = st.columns(2)

    with col_r1:
        with st.container(border=True):
            st.markdown("### 5A. High-Converting Review Request Scripts")
            st.caption("Caleb's #1 method (60–70% conversion): Direct text from the business owner's cell phone, plus the 6-step GoHighLevel automation sequence.")
            place_link = st.text_input(
                "Google Place ID or Direct Review URL",
                value=client_record.get("place_id", ""),
                placeholder="Paste Place ID (e.g. ChIJ...) or Review Link"
            )
            if st.button("🚀 Generate Scripts", type="primary", use_container_width=True):
                with st.spinner("Generating Owner SMS + GoHighLevel Sequence..."):
                    rev_req_prompt = f"""
                    Create a complete Local SEO Review Generation package for:
                    Business: {b_name} ({b_niche} in {b_city})
                    Review Link: {place_link or '[INSERT_REVIEW_LINK]'}

                    Include:
                    1. Caleb Ulku's Personal Owner Text Script (conversational, sent right after job completion asking if they're happy before sending the link, encouraging them to mention the specific service performed).
                    2. A 3-SMS + 3-Email GoHighLevel Automation Sequence (Day 1, Day 3, Day 7) with subject lines and merge tags.
                    """
                    scripts_out = call_gemini(rev_req_prompt)
                    if scripts_out:
                        client_record["review_scripts"] = scripts_out
                        if current_client_id:
                            save_client_data(current_client_id, {
                                "place_id": place_link,
                                "review_scripts": scripts_out
                            })
                        st.rerun()

            rev_scripts_box = st.text_area(
                "Generated Outreach Scripts",
                value=client_record.get("review_scripts", ""),
                height=310,
                label_visibility="collapsed",
                placeholder="Click 'Generate Scripts' to create the Owner Personal SMS scripts + the 3-SMS / 3-Email GoHighLevel sequence..."
            )
            if st.button("💾 Save Outreach Scripts", use_container_width=True, type="secondary"):
                if current_client_id:
                    save_client_data(current_client_id, {"place_id": place_link, "review_scripts": rev_scripts_box})
                    st.toast("✅ Saved Review Scripts!")

    with col_r2:
        with st.container(border=True):
            st.markdown("### 5B. SEO Keyword-Injected Review Responder")
            st.caption("Respond to 100% of reviews while naturally weaving in your target services, categories, and city.")
            c_rn, c_rt = st.columns(2)
            with c_rn:
                rev_name = st.text_input("Reviewer Name", placeholder="Reviewer Name")
            with c_rt:
                rev_stars = st.selectbox("Rating", ["5 Stars (Positive)", "4 Stars (Positive)", "3 Stars (Neutral)", "1-2 Stars (Negative - De-escalate)"])
            cust_review = st.text_area(
                "Customer Review",
                height=110,
                placeholder="Paste the customer's review here (or leave blank if it's a rating-only review)..."
            )
            if st.button("✨ Write Reply", type="primary", use_container_width=True):
                with st.spinner("Writing keyword-injected review response..."):
                    reply_prompt = f"""
                    Write an authentic, warm, professional owner response to a {rev_stars} Google review from "{rev_name or 'Valued Customer'}" for {b_name} ({b_niche} in {b_city}).
                    Customer Review: "{cust_review or '(Left star rating only, no text)'}"
                    Naturally mention 1 relevant service and {b_city} without sounding robotic. If 1-2 stars, stay polite, protect reputation, and invite them to call {b_phone} offline.
                    """
                    st.session_state["last_review_reply"] = call_gemini(reply_prompt)

            st.text_area(
                "Your SEO-optimized review response",
                value=st.session_state.get("last_review_reply", ""),
                height=175,
                placeholder="Your SEO-optimized review response will appear here..."
            )

# ------------------------------------------------------------------------------
# TAB 6: PRE-VERIFICATION CHECKLIST & OPS CADENCE
# ------------------------------------------------------------------------------
with tabs[5]:
    col_v1, col_v2 = st.columns(2)

    checklist_items = [
        "Verify exact legal business name matches LLC/Inc paperwork, insurance, and utility bills.",
        "Purchase branded or Niche+City domain and deploy basic homepage talking about core services.",
        "Submit foundational local directory citations with 100% consistent NAP.",
        "Distribute press release mentioning Business Name, Address, Phone, and Website URL.",
        "Order physical verification proof: vehicle magnets, business cards, and yard sign.",
        "Wait ~30 days for citations, press release, and website to index and age in Google.",
        "Record continuous, unedited verification video (street sign -> unlock door/truck -> tools/docs).",
        "Enable GBP Messaging & connect GoHighLevel auto-responder + push notifications.",
        "Brief phone staff: Answer 100% of calls and keep even spam callers on the line for 15–20 seconds.",
        "Set recurring 60-day calendar reminder to update GBP Holiday Hours & review user-suggested edits."
    ]

    try:
        saved_checks = json.loads(client_record.get("verification_json", "{}") or "{}")
    except Exception:
        saved_checks = {}

    with col_v1:
        with st.container(border=True):
            st.markdown("### 6A. Pre-Verification & 30-Day Entity Checklist")
            st.caption("Build online trust before submitting your GBP video verification.")
            updated_checks = {}
            completed_count = 0
            for idx, item_text in enumerate(checklist_items):
                key_id = f"chk_{idx}"
                is_checked = st.checkbox(item_text, value=bool(saved_checks.get(key_id, False)), key=f"ui_{current_client_id}_{key_id}")
                updated_checks[key_id] = is_checked
                if is_checked:
                    completed_count += 1

            st.progress(completed_count / 10.0, text=f"Entity Readiness: {completed_count} / 10 Completed")
            if st.button("💾 Save Checklist Progress", type="secondary", use_container_width=True):
                if current_client_id:
                    save_client_data(current_client_id, {"verification_json": json.dumps(updated_checks)})
                    st.toast("✅ Checklist saved to Neon DB!")

    with col_v2:
        with st.container(border=True):
            st.markdown("### 6B. Ongoing Operational Cadence & Holiday Hours")
            st.caption("Keep the profile active and protect behavioral signals.")
            ics_data = build_ics_reminder(b_name)
            st.download_button(
                "📅 Download .ICS Calendar Reminder (60-Day Cadence)",
                data=ics_data,
                file_name=f"{b_name.lower().replace(' ', '_')}_gbp_60day_cadence.ics",
                mime="text/calendar",
                type="primary",
                use_container_width=True
            )

            with st.container(border=True):
                st.markdown('<div class="cu-col-header-gold">UPCOMING HOLIDAY HOURS TO UPDATE NOW</div>', unsafe_allow_html=True)
                st.caption("Google only lets you set holiday hours a few months ahead. Log in every 60 days and confirm hours for these upcoming dates:")
                st.markdown("""
                * `Veterans Day (Nov 11)`
                * `Thanksgiving Day & Black Friday (Late Nov)`
                * `Christmas Eve & Christmas Day (Dec 24 – Dec 25)`
                * `New Year's Eve & New Year's Day (Dec 31 – Jan 1)`
                * `Martin Luther King Jr. Day (3rd Monday in Jan)`
                * `Presidents' Day (3rd Monday in Feb)`
                * `Memorial Day (Last Monday in May)`
                * `Independence Day (July 4)`
                * `Labor Day (1st Monday in Sep)`
                """)

            with st.container(border=True):
                st.markdown('<div class="cu-col-header-green">CLIENT VIDEO VERIFICATION SHOT-LIST</div>', unsafe_allow_html=True)
                if st.button("🎬 Generate Custom Video Script", type="secondary", use_container_width=True):
                    with st.spinner("Writing custom GBP Video Verification script..."):
                        vid_prompt = f"""
                        Create a step-by-step, 90-second continuous smartphone Video Verification shot-list for:
                        Business: {b_name} ({b_niche}) at {b_addr}, {b_city}.
                        Explain exactly what the business owner needs to film (street sign, branded service truck/signage, unlocking the door or vehicle with a key, tools of the trade, POS/invoicing software, and utility/LLC doc) without any camera cuts.
                        """
                        v_out = call_gemini(vid_prompt)
                        if v_out:
                            client_record["video_script"] = v_out
                            if current_client_id:
                                save_client_data(current_client_id, {"video_script": v_out})
                            st.rerun()

                st.text_area(
                    "Shot-List",
                    value=client_record.get("video_script", "1. Start outside showing the nearest official street sign & surrounding businesses.\n2. Walk continuously (no cuts) to the building entrance or branded service vehicle.\n3. Show your physical signage, car magnet, or yard sign matching the exact GBP name.\n4. Unlock the front door or service vehicle with your physical key.\n5. Show tools of the trade, POS/invoicing software, utility bill, or formation docs with matching address."),
                    height=155,
                    label_visibility="collapsed"
                )

# ------------------------------------------------------------------------------
# TAB 7: DIRECT GBP API SYNC (FUTURE OAUTH BRIDGE)
# ------------------------------------------------------------------------------
with tabs[6]:
    with st.container(border=True):
        st.markdown("### 🔌 Direct Google Business Profile API Sync (Agency OAuth Bridge)")
        st.caption("Future-Ready Module: When you apply for and receive Google Business Profile API approval, this tab lets you push your categories, services, 750-char descriptions, and posts directly to client GBP listings.")

        col_api1, col_api2 = st.columns(2)
        with col_api1:
            with st.container(border=True):
                st.markdown('<div class="cu-col-header-gold">HOW TO ACTIVATE DIRECT GBP API ACCESS LATER</div>', unsafe_allow_html=True)
                st.markdown("""
                1. Create a project in the **Google Cloud Console** and note your **Project Number**.
                2. Submit the official **Google Business Profile API Request Form** using your agency domain email.
                3. Once approved by Google, enable the *My Business Business Information API* and *Account Management API*.
                4. Add `GBP_CLIENT_ID`, `GBP_CLIENT_SECRET`, and `GBP_REFRESH_TOKEN` to your **Streamlit Secrets**.
                """)
        with col_api2:
            with st.container(border=True):
                gbp_loc_id = st.text_input(
                    "Client GBP Location ID",
                    value=client_record.get("gbp_location_id", ""),
                    placeholder="locations/12345678901234567890"
                )
                if st.button("💾 Save GBP Location ID", type="secondary", use_container_width=True):
                    if current_client_id:
                        save_client_data(current_client_id, {"gbp_location_id": gbp_loc_id})
                        st.toast("✅ Saved GBP Location ID!")

                has_gbp_oauth = bool(hasattr(st, "secrets") and "GBP_CLIENT_ID" in st.secrets)
                st.markdown(f"**OAuth Status:** `{'🟢 Connected' if has_gbp_oauth else '⚪ Standby (Awaiting GBP API Credentials)'}`")
                st.button(
                    "🔄 Sync Core Assets Directly to Client GBP",
                    disabled=not has_gbp_oauth,
                    type="primary",
                    use_container_width=True
                )
