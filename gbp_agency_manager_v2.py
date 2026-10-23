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
    page_title="BC RankEngine | GBP Synergy & Local SEO Suite",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM DARK & GOLD STYLING ---
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px 6px 0px 0px;
        padding: 10px 16px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1f2937 !important;
        border-bottom: 3px solid #10b981 !important;
        color: #10b981 !important;
    }
    div[data-testid="stSidebarContent"] {
        border-right: 1px solid #d97706;
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
        # Safe Auto-Migration for existing Neon tables
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
        st.error("⚠️ Please provide a valid Gemini API Key in Streamlit Secrets or the top bar.")
        return ""
    try:
        if GENAI_SDK == "new":
            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(temperature=0.3)
            if use_search:
                config.tools = [{"google_search": {}}]
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=config
            )
            return resp.text
        elif GENAI_SDK == "legacy":
            genai_legacy.configure(api_key=api_key)
            model = genai_legacy.GenerativeModel("gemini-1.5-flash")
            resp = model.generate_content(prompt)
            return resp.text
        else:
            st.error("Google GenAI SDK is not installed.")
            return ""
    except Exception as e:
        st.error(f"Gemini API Error: {str(e)}")
        return ""

def geocode_address(address):
    if not address.strip():
        return None, None
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json", "limit": 1}
        headers = {"User-Agent": "BC_RankEngine_SEO_Suite/2.0"}
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
        f"UID:gbp-cadence-{ int(datetime.datetime.utcnow().timestamp()) }@bcrankengine",
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

# --- HEADER BAR ---
col_head1, col_head2 = st.columns([3, 2])
with col_head1:
    st.markdown("### 📍 GBP Synergy & Local SEO Suite — **BC RankEngine**")
    db_badge = "🟢 Connected to Neon PostgreSQL Cloud" if USE_POSTGRES else "🟡 Local SQLite Fallback"
    st.caption(f"Caleb Ulku Framework • Hover over any (?) icon for Official Google Guidelines • {db_badge}")

with col_head2:
    with st.expander("🔑 AI Engine & API Settings", expanded=not bool(st.session_state["api_key"])):
        key_input = st.text_input(
            "Google Gemini API Key",
            value=st.session_state["api_key"],
            type="password",
            help="Stored automatically via Streamlit Secrets (`GEMINI_API_KEY`), or paste a temporary key here."
        )
        if key_input != st.session_state["api_key"]:
            st.session_state["api_key"] = key_input
        if st.button("✅ Test Key & Sync Model", use_container_width=True):
            test_res = call_gemini("Reply with: 'Gemini 2.5 Flash Connected!'")
            if test_res:
                st.success(test_res.strip())

st.divider()

# --- LOAD CLIENTS & SIDEBAR ENTITY PROFILE ---
clients = fetch_all_clients()
client_names = ["+ Create New Client Profile"] + [f"{c['business_name']} ({c['target_city']})" for c in clients]

with st.sidebar:
    st.markdown("### 🏢 Business Entity Profile")
    selected_idx = st.selectbox(
        "Select Saved Client Profile",
        range(len(client_names)),
        format_func=lambda i: client_names[i],
        help="Switch between client profiles stored in your Neon PostgreSQL database, or create a new client."
    )

    col_ex1, col_ex2 = st.columns(2)
    with col_ex1:
        if st.button("📋 Load Example", use_container_width=True, help="Auto-populate sidebar with Shearrer's Appliance Service example data."):
            st.session_state["form_bname"] = "Shearrer's Appliance Service"
            st.session_state["form_niche"] = "Appliance Repair"
            st.session_state["form_city"] = "Piedmont, Missouri"
            st.session_state["form_years"] = "15+"
            st.session_state["form_phone"] = "573-998-2337"
            st.session_state["form_usp"] = "More than 30 years of appliance repair knowledge. Repair of all makes and models. HVAC, microwaves, refrigerators, freezers, cook ranges, washers and dryers."
            st.session_state["form_url"] = "https://shearrersappliance.com"
            st.session_state["form_addr"] = "31558 State Highway 49, Williamsville, MO 63967"
            st.session_state["form_lat"] = "36.974096"
            st.session_state["form_lon"] = "-90.574269"
            st.rerun()
    with col_ex2:
        if selected_idx > 0 and st.button("🗑️ Delete Client", use_container_width=True, help="Permanently remove this client from the database."):
            delete_client_record(clients[selected_idx - 1]["id"])
            st.success("Client deleted.")
            st.rerun()

    # Sync sidebar inputs when switching clients
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
        help="Google Guideline: Use your exact real-world legal business name as shown on signage, LLC docs, and utility bills. Do NOT stuff keywords here or risk instant suspension."
    )

    if st.button("🌐 Search Web & Auto-Fill Business Info", use_container_width=True, type="primary", help="Uses Gemini with Google Search Grounding to look up this business online and auto-populate its niche, phone, address, and USP."):
        if not b_name.strip():
            st.warning("Enter a Business Name first.")
        else:
            with st.spinner(f"Searching the web for {b_name}..."):
                lookup_prompt = f"""
                Search the web for the business "{b_name}" {st.session_state.get('form_city', '')}.
                Return ONLY a valid JSON object with these exact keys (use empty string if unknown):
                {{
                  "primary_niche": "Primary GBP category (e.g. Appliance Repair Service)",
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
                try:
                    clean_json = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                    parsed_info = json.loads(clean_json)
                    st.session_state["form_niche"] = parsed_info.get("primary_niche", st.session_state["form_niche"])
                    st.session_state["form_city"] = parsed_info.get("target_city", st.session_state["form_city"])
                    st.session_state["form_years"] = parsed_info.get("years_in_business", st.session_state["form_years"])
                    st.session_state["form_phone"] = parsed_info.get("phone", st.session_state["form_phone"])
                    st.session_state["form_usp"] = parsed_info.get("usp", st.session_state["form_usp"])
                    st.session_state["form_url"] = parsed_info.get("website_url", st.session_state["form_url"])
                    st.session_state["form_addr"] = parsed_info.get("street_address", st.session_state["form_addr"])
                    st.session_state["form_lat"] = str(parsed_info.get("latitude", st.session_state["form_lat"]))
                    st.session_state["form_lon"] = str(parsed_info.get("longitude", st.session_state["form_lon"]))
                    st.rerun()
                except Exception:
                    st.warning("Could not parse structured web results automatically. Check fields manually.")

    c_niche, c_city = st.columns(2)
    with c_niche:
        b_niche = st.text_input(
            "Primary Niche",
            key="form_niche",
            help="Google Guideline: Your #1 primary GBP category dictates the core search queries you rank for (e.g., Appliance Repair Service, HVAC Contractor)."
        )
    with c_city:
        b_city = st.text_input(
            "Target City & State",
            key="form_city",
            help="The primary municipal market where the client wants to dominate the Google Local 3-Pack."
        )

    c_yr, c_ph = st.columns(2)
    with c_yr:
        b_years = st.text_input(
            "Years in Business",
            key="form_years",
            help="Used to establish entity authority in your 750-char description and GBP 'From the business' opening date."
        )
    with c_ph:
        b_phone = st.text_input(
            "Phone Number",
            key="form_phone",
            help="Google Guideline: Must match your website NAP (Name, Address, Phone) 100% across all directory citations."
        )

    b_usp = st.text_area(
        "Unique Selling Proposition (USP)",
        key="form_usp",
        height=90,
        help="Specialties, certifications, warranties, or specific equipment/brands serviced. Injected naturally into GBP posts, website copy, and review replies."
    )

    b_url = st.text_input(
        "Website URL",
        key="form_url",
        help="The primary domain linked on the GBP listing. Used for Website-to-GBP Blended Algorithm Synergy."
    )

    b_addr = st.text_input(
        "Full Street Address (for Geotagging)",
        key="form_addr",
        help="Rural / Home Office Tip: Even if you hide your address on GBP as a Service Area Business (SAB), enter your physical shop/home-base address or target city center here to geotag job photos."
    )

    if st.button("🧭 Auto-Lookup GPS Coordinates from Address", use_container_width=True, help="Queries OpenStreetMap Nominatim to convert the street address above into exact GPS Latitude & Longitude."):
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
            help="Decimal latitude injected into client JPEG EXIF metadata (e.g., 36.974096)."
        )
    with c_lon:
        b_lon = st.text_input(
            "Longitude",
            key="form_lon",
            help="Decimal longitude injected into client JPEG EXIF metadata (e.g., -90.574269)."
        )

    if st.button("💾 Save / Update Client in Cloud DB", type="primary", use_container_width=True, help="Saves all sidebar profile fields permanently to your Neon PostgreSQL database."):
        if not b_name.strip():
            st.error("Business Legal Name is required.")
        elif selected_idx == 0:
            new_id = create_new_client(b_name, b_niche, b_city, b_years, b_phone, b_usp, b_url, b_addr, b_lat, b_lon)
            st.session_state["loaded_client_id"] = new_id
            st.success(f"Created {b_name} in database!")
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
            st.success("Client profile saved to Neon DB!")
            st.rerun()

# Require an active or entered client profile
if not b_name.strip():
    st.info("👈 Select an existing client from the left sidebar, click **Load Example**, or enter a **Business Legal Name** and click **Save / Update Client in Cloud DB** to begin.")
    st.stop()

# Ensure defaults for active client workspace
client_record = active_client or {
    "id": 0, "services_list": "", "categories_list": "", "gbp_description": "",
    "silo_architecture": "", "posts_json": "[]", "review_scripts": "",
    "verification_json": "{}", "video_script": "", "place_id": "", "gbp_location_id": ""
}

# --- 7-TAB CALEB ULKU SUITE + FUTURE GBP API SYNC ---
tabs = st.tabs([
    "📚 1. GBP Core Setup (AI)",
    "💻 2. Website Synergy Engine",
    "📅 3. GBP Posts & GHL CSV",
    "🖼️ 4. Bulk EXIF Geotagger",
    "💬 5. Reviews & SMS Engine",
    "🛡️ 6. Verification & Ops",
    "🔌 7. Direct GBP API Sync (Future)"
])

# ==============================================================================
# TAB 1: SERVICES-FIRST GBP ARCHITECTURE
# ==============================================================================
with tabs[0]:
    st.subheader("Step 1: Services-First GBP Architecture")
    st.caption("Caleb's framework starts by generating 25+ specific services first, then mapping up to 5 official GBP categories to those services, followed by a 750-character USP description. Everything you edit saves to your Neon database.")

    if st.button("✨ Generate All 3 Core Assets", type="primary", help="Generates 25+ granular services, 5 mapped GBP categories, and a 750-character SEO description in one click."):
        with st.spinner("Generating Services-First Architecture via Gemini..."):
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
              "services": "25 to 35 specific, high-intent granular service names (one per line, no bullets or numbers)",
              "categories": "Primary GBP category on line 1, followed by 3 to 4 closely related official Google Business Profile secondary categories (one per line, no bullets)",
              "description": "A compelling, conversion-focused Google Business Profile description strictly between 600 and 740 characters. Weave in the primary city, core services, years of experience, and call-to-action with phone number. Do NOT exceed 750 characters."
            }}
            """
            raw_res = call_gemini(prompt_all)
            try:
                clean = raw_res.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                parsed = json.loads(clean)
                client_record["services_list"] = parsed.get("services", "")
                client_record["categories_list"] = parsed.get("categories", "")
                client_record["gbp_description"] = parsed.get("description", "")[:750]
                if current_client_id:
                    save_client_data(current_client_id, {
                        "services_list": client_record["services_list"],
                        "categories_list": client_record["categories_list"],
                        "gbp_description": client_record["gbp_description"]
                    })
                st.rerun()
            except Exception as e:
                st.error(f"Could not parse response: {e}")

    col_1a, col_1b, col_1c = st.columns(3)

    with col_1a:
        st.markdown("##### 1A. 25+ GRANULAR SERVICES")
        srv_val = st.text_area(
            "Granular Services List (1 per line)",
            value=client_record.get("services_list", ""),
            height=340,
            help="Caleb Ulku Rule: Add 25 to 35 specific services under your categories. Google indexes custom services directly for long-tail 'near me' searches."
        )

    with col_1b:
        st.markdown("##### 1B. 5 GBP CATEGORIES")
        cat_val = st.text_area(
            "Primary + Secondary Categories (1 per line)",
            value=client_record.get("categories_list", ""),
            height=340,
            help="Google Guideline: Select 1 laser-focused Primary Category and 3–4 relevant Secondary Categories. Avoid unrelated categories to prevent category dilution."
        )

    with col_1c:
        st.markdown("##### 1C. 750-CHAR DESCRIPTION")
        desc_val = st.text_area(
            "GBP Business Description (Max 750 chars)",
            value=client_record.get("gbp_description", ""),
            height=300,
            help="Google Guideline: Maximum 750 characters. No URLs or HTML allowed. Highlight your USP, primary city, surrounding counties, and phone number."
        )
        char_len = len(desc_val)
        color = "green" if char_len <= 750 else "red"
        st.markdown(f":{color}[**{char_len} / 750 chars**]")

    if st.button("💾 Save Step 1 Edits to Database", help="Saves any manual edits made in the three boxes above to your Neon database."):
        if current_client_id:
            save_client_data(current_client_id, {
                "services_list": srv_val,
                "categories_list": cat_val,
                "gbp_description": desc_val[:750]
            })
            st.success("Saved Step 1 assets to Neon DB!")
        else:
            st.warning("Click 'Save / Update Client in Cloud DB' in the left sidebar first to create this client record.")

# ==============================================================================
# TAB 2: WEBSITE-TO-GBP BLENDED ALGORITHM SYNERGY
# ==============================================================================
with tabs[1]:
    st.subheader("Step 2: Website-to-GBP Blended Algorithm Synergy")
    st.caption("Google's local algorithm blends your website's H1/H2 structure with your GBP categories and services. Choose your competition tier below.")

    comp_mode = st.radio(
        "Select Market Competition Strategy",
        [
            "Low/Med Comp (Homepage H2s — Rural & Small Town Markets)",
            "High Comp (Dedicated Category Silo Pages — Metro Markets)"
        ],
        horizontal=True,
        help="In rural/small towns (like Wayne or Butler County), placing your secondary categories and services as H2/H3 sections directly on the Homepage ranks fastest. In larger cities, build dedicated Category Silo pages."
    )

    if st.button("🏗️ Build Website Synergy Architecture & Copy", type="primary", help="Generates exact-match URL slugs, Title Tags, H1/H2 headings, SEO copy, and internal linking instructions aligned with Step 1."):
        with st.spinner("Generating Website Synergy Blueprint..."):
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
            1. Exact Title Tag, Meta Description, and H1 for the Homepage (`{b_url}`).
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
        "Generated Silo Pages, H1/H2 Copy & Schema Architecture (Editable)",
        value=client_record.get("silo_architecture", ""),
        height=450,
        help="Edit this blueprint freely and click Save or Download below."
    )

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("💾 Save Website Blueprint to DB", use_container_width=True):
            if current_client_id:
                save_client_data(current_client_id, {"silo_architecture": silo_text})
                st.success("Saved Website Synergy Blueprint!")
    with col_s2:
        st.download_button(
            "📥 Download Website Blueprint (.md)",
            data=silo_text,
            file_name=f"{b_name.lower().replace(' ', '_')}_website_synergy.md",
            mime="text/markdown",
            use_container_width=True
        )

# ==============================================================================
# TAB 3: 20-WEEK EVERGREEN GBP POST GENERATOR & GOHIGHLEVEL CSV
# ==============================================================================
with tabs[2]:
    st.subheader("Step 3: 20-Week Evergreen GBP Post Generator")
    st.caption("\"It only takes a half hour to write and schedule a lifetime of GBP posts.\" Generate 20 non-duplicate posts cycling through your client's services and export directly to a GoHighLevel-ready CSV.")

    if st.button("🚀 Generate 20 Weekly GBP Posts", type="primary", help="Cycles through your Step 1 services to create 20 unique, local-keyword-rich GBP posts scheduled 7 days apart."):
        with st.spinner("Writing 20 Weekly Evergreen GBP Posts..."):
            services_lines = [s.strip() for s in srv_val.split("\n") if s.strip()]
            if not services_lines:
                services_lines = [b_niche or "Local Service"]
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
                        "GBP Post Content": item.get("content", ""),
                        "Action Type": "LEARN_MORE",
                        "Action URL": b_url
                    })
                client_record["posts_json"] = json.dumps(enriched)
                if current_client_id:
                    save_client_data(current_client_id, {"posts_json": client_record["posts_json"]})
                st.rerun()
            except Exception as e:
                st.error(f"Error parsing generated posts: {e}")

    try:
        loaded_posts = json.loads(client_record.get("posts_json", "[]") or "[]")
    except Exception:
        loaded_posts = []

    if loaded_posts:
        df_posts = pd.DataFrame(loaded_posts)
        edited_df = st.data_editor(
            df_posts,
            use_container_width=True,
            num_rows="dynamic",
            height=420,
            help="Double-click any cell to edit the scheduled date, featured service, or post copy before exporting to GoHighLevel."
        )

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            if st.button("💾 Save Edited Posts Table to DB", use_container_width=True):
                updated_json = edited_df.to_json(orient="records")
                if current_client_id:
                    save_client_data(current_client_id, {"posts_json": updated_json})
                    st.success("20-Week Posts saved to Neon DB!")
        with col_p2:
            csv_bytes = edited_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📊 Export CSV (GoHighLevel Social Planner Ready)",
                data=csv_bytes,
                file_name=f"{b_name.lower().replace(' ', '_')}_20_week_gbp_posts.csv",
                mime="text/csv",
                type="primary",
                use_container_width=True,
                help="Download this CSV and upload it directly into GoHighLevel -> Marketing -> Social Planner -> Import CSV."
            )
    else:
        st.info("Click **Generate 20 Weekly GBP Posts** above to build your 20-week evergreen schedule.")

# ==============================================================================
# TAB 4: BULK PHOTO EXIF GEOTAGGER
# ==============================================================================
with tabs[3]:
    st.subheader("Step 4: Bulk Photo EXIF Geotagger")
    st.caption("Inject exact GPS Latitude/Longitude coordinates and NAP metadata directly into your client's authentic job-site JPEG photos.")

    col_geo1, col_geo2 = st.columns([1, 2])
    with col_geo1:
        st.markdown(f"""
        **Target Geotag Coordinates:**
        * **Latitude:** `{b_lat or 'Not Set'}`
        * **Longitude:** `{b_lon or 'Not Set'}`
        * **Business Artist Tag:** `{b_name}`
        * **Target City:** `{b_city}`
        """)
        st.info("💡 **Google Photo Guideline:** Use real, well-lit 720x720px+ job-site, team, or service truck photos. Never use stock photos!")

    with col_geo2:
        uploaded_photos = st.file_uploader(
            "Drop Client JPEG/PNG Photos Here (Bulk Upload Supported)",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            help="Upload authentic client photos. The tool converts them to high-res JPEG and embeds GPS EXIF coordinates + business metadata."
        )

        if uploaded_photos:
            try:
                lat_f = float(str(b_lat).replace(",", "").strip())
                lon_f = float(str(b_lon).replace(",", "").strip())
                coords_valid = True
            except ValueError:
                coords_valid = False
                st.error("⚠️ Invalid Latitude or Longitude in the left sidebar. Click the '🧭 Auto-Lookup GPS Coordinates' button in the sidebar first.")

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
                    "📦 Download Geotagged Photos (.ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name=f"{b_name.lower().replace(' ', '_')}_geotagged_photos.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                    help="Downloads a ZIP archive containing all your newly geotagged, SEO-named JPEG photos ready to upload to Google Business Profile."
                )

# ==============================================================================
# TAB 5: REVIEWS & SMS ENGINE
# ==============================================================================
with tabs[4]:
    col_r1, col_r2 = st.columns(2)

    with col_r1:
        st.subheader("5A. High-Converting Review Request Scripts")
        st.caption("Caleb's #1 method (60–70% conversion): Direct text from the owner's cell phone, plus a 6-step GoHighLevel automation sequence.")
        place_link = st.text_input(
            "Google Place ID or Direct Review Link",
            value=client_record.get("place_id", ""),
            placeholder="[https://g.page/r/.../review](https://g.page/r/.../review) or ChIJ...",
            help="Paste the client's short GBP review link or Google Place ID so it auto-inserts into every SMS and email template."
        )
        if st.button("📲 Generate Review Request Scripts", type="primary", help="Generates the Owner Personal SMS script plus a 3-SMS / 3-Email GoHighLevel drip sequence."):
            with st.spinner("Generating Review Request Sequence..."):
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
            "Owner Personal SMS & GoHighLevel Sequence",
            value=client_record.get("review_scripts", ""),
            height=320
        )
        if st.button("💾 Save Outreach Scripts to DB"):
            if current_client_id:
                save_client_data(current_client_id, {"place_id": place_link, "review_scripts": rev_scripts_box})
                st.success("Saved Review Scripts!")

    with col_r2:
        st.subheader("5B. SEO Keyword-Injected Review Responder")
        st.caption("Respond to 100% of reviews while naturally weaving in your target services, categories, and city.")
        c_rn, c_rt = st.columns(2)
        with c_rn:
            rev_name = st.text_input("Reviewer Name", placeholder="e.g. John D.")
        with c_rt:
            rev_stars = st.selectbox("Star Rating", ["5 Stars (Positive)", "4 Stars (Positive)", "3 Stars (Neutral)", "1-2 Stars (Negative - De-escalate)"])
        cust_review = st.text_area(
            "Customer's Review Text (Leave blank if rating-only)",
            height=110,
            help="Paste the customer's review. The AI will naturally weave your target service and city into the owner response."
        )
        if st.button("✍️ Write SEO Review Reply", type="primary"):
            with st.spinner("Crafting keyword-optimized reply..."):
                reply_prompt = f"""
                Write an authentic, warm, professional owner response to a {rev_stars} Google review from "{rev_name or 'Valued Customer'}" for {b_name} ({b_niche} in {b_city}).
                Customer Review: "{cust_review or '(Left star rating only, no text)'}"
                Naturally mention 1 relevant service and {b_city} without sounding robotic. If 1-2 stars, stay polite, protect reputation, and invite them to call {b_phone} offline.
                """
                st.session_state["last_review_reply"] = call_gemini(reply_prompt)

        st.text_area(
            "SEO-Optimized Review Response",
            value=st.session_state.get("last_review_reply", ""),
            height=180
        )

# ==============================================================================
# TAB 6: PRE-VERIFICATION CHECKLIST, VIDEO SCRIPT & OPS CADENCE
# ==============================================================================
with tabs[5]:
    col_v1, col_v2 = st.columns(2)

    checklist_items = [
        "1. Verify exact legal business name matches LLC/Inc paperwork, insurance, and utility bills.",
        "2. Purchase branded or Niche+City domain and deploy basic homepage talking about core services.",
        "3. Submit foundational local directory citations (Yelp, BBB, Facebook, Apple Maps) with 100% consistent NAP.",
        "4. Distribute press release mentioning Business Name, Address, Phone, and Website URL.",
        "5. Order physical verification proof: vehicle magnets, business cards, and yard/shop signage.",
        "6. Wait ~30 days for citations, press release, and website to index and age in Google.",
        "7. Record continuous, unedited verification video (street sign -> unlock door/truck -> tools/docs).",
        "8. Enable GBP Messaging & connect GoHighLevel Missed-Call Text-Back + auto-responder.",
        "9. Brief phone staff: Answer 100% of calls and keep even spam callers on the line for 15–20 seconds (protects behavioral call signals).",
        "10. Set recurring 60-day calendar reminder to update GBP Holiday Hours & reject unauthorized user edits."
    ]

    try:
        saved_checks = json.loads(client_record.get("verification_json", "{}") or "{}")
    except Exception:
        saved_checks = {}

    with col_v1:
        st.subheader("6A. Pre-Verification & 30-Day Entity Checklist")
        st.caption("Build online trust before submitting your GBP video verification to prevent instant suspension.")
        updated_checks = {}
        completed_count = 0
        for idx, item_text in enumerate(checklist_items):
            key_id = f"chk_{idx}"
            is_checked = st.checkbox(item_text, value=bool(saved_checks.get(key_id, False)), key=f"ui_{current_client_id}_{key_id}")
            updated_checks[key_id] = is_checked
            if is_checked:
                completed_count += 1

        st.progress(completed_count / 10.0, text=f"Entity Readiness: {completed_count} / 10 Completed")
        if st.button("💾 Save Checklist Progress to DB"):
            if current_client_id:
                save_client_data(current_client_id, {"verification_json": json.dumps(updated_checks)})
                st.success("Checklist saved to Neon DB!")

    with col_v2:
        st.subheader("6B. Ongoing Operational Cadence & Holiday Hours")
        ics_data = build_ics_reminder(b_name)
        st.download_button(
            "📅 Download .ICS 60-Day Recurring Calendar Reminder",
            data=ics_data,
            file_name=f"{b_name.lower().replace(' ', '_')}_gbp_60day_cadence.ics",
            mime="text/calendar",
            type="primary",
            use_container_width=True,
            help="Imports a recurring 60-day reminder into Apple Calendar, Google Calendar, or Outlook so you never forget to confirm Holiday Hours."
        )

        st.markdown("""
        **Upcoming Holiday Hours to Confirm Every 60 Days:**
        * **Veterans Day** (Nov 11)
        * **Thanksgiving Day & Black Friday** (Late Nov)
        * **Christmas Eve & Christmas Day** (Dec 24 – Dec 25)
        * **New Year's Eve & New Year's Day** (Dec 31 – Jan 1)
        * **Martin Luther King Jr. Day** (3rd Monday in Jan)
        * **Presidents' Day** (3rd Monday in Feb)
        * **Memorial Day** (Last Monday in May)
        * **Independence Day** (July 4)
        * **Labor Day** (1st Monday in Sep)
        """)

        st.divider()
        st.markdown("##### 🎥 Client Video Verification Shot-List Generator")
        if st.button("🎬 Generate Custom Video Verification Script", help="Creates a step-by-step unedited smartphone video shot-list tailored to this specific business and address."):
            with st.spinner("Writing custom GBP Video Verification script..."):
                vid_prompt = f"""
                Create a step-by-step, 90-second continuous smartphone Video Verification shot-list for:
                Business: {b_name}
                Niche: {b_niche}
                Address: {b_addr} ({b_city})
                Explain exactly what the business owner needs to film (street sign, branded service truck/signage, unlocking the door or vehicle with a key, tools of the trade, POS/invoicing software, and utility/LLC doc) without any camera cuts.
                """
                v_out = call_gemini(vid_prompt)
                if v_out:
                    client_record["video_script"] = v_out
                    if current_client_id:
                        save_client_data(current_client_id, {"video_script": v_out})
                    st.rerun()

        st.text_area(
            "Custom Video Verification Shot-List",
            value=client_record.get("video_script", "1. Start outside showing the nearest official street sign & surrounding area.\n2. Walk continuously (no cuts) to the building entrance or branded service vehicle.\n3. Show physical signage, car magnet, or equipment matching the exact GBP name.\n4. Unlock the front door or service truck with your physical key.\n5. Show tools of the trade, invoicing software, and LLC/utility bill matching address."),
            height=200
        )

# ==============================================================================
# TAB 7: DIRECT GOOGLE BUSINESS PROFILE API SYNC (FUTURE-READY ARCHITECTURE)
# ==============================================================================
with tabs[6]:
    st.subheader("🔌 Direct Google Business Profile API Sync (Agency OAuth Bridge)")
    st.caption("Future-Ready Module: When you apply for and receive Google Business Profile API approval, this tab lets you push your categories, services, 750-char descriptions, and posts directly to client GBP listings with one click.")

    col_api1, col_api2 = st.columns([1, 1])
    with col_api1:
        st.info("""
        **How to Activate Google Business Profile API Access Later:**
        1. Create a project in the **Google Cloud Console** and note your **Project Number**.
        2. Submit the official **Google Business Profile API Request Form** using your agency domain email (`@brushycreekmedia.com` or `@timothyhicks.com`).
        3. Once approved by Google (typically 5–14 days), enable these 3 APIs in Google Cloud:
           * *My Business Business Information API*
           * *My Business Account Management API*
           * *My Business Verifications API*
        4. Paste your `GBP_CLIENT_ID`, `GBP_CLIENT_SECRET`, and `GBP_REFRESH_TOKEN` into your **Streamlit Secrets** vault.
        """)

    with col_api2:
        gbp_loc_id = st.text_input(
            "Client GBP Location Resource Name",
            value=client_record.get("gbp_location_id", ""),
            placeholder="locations/12345678901234567890",
            help="Once OAuth is connected, enter the client's Google Location ID here to link this database profile directly to their live Google Business Profile."
        )
        if st.button("💾 Save GBP Location ID to Client Record"):
            if current_client_id:
                save_client_data(current_client_id, {"gbp_location_id": gbp_loc_id})
                st.success("Saved GBP Location ID!")

        has_gbp_oauth = bool(hasattr(st, "secrets") and "GBP_CLIENT_ID" in st.secrets)
        st.markdown(f"**OAuth API Status:** {'🟢 Credentials Detected' if has_gbp_oauth else '⚪ Standby Mode (Awaiting GBP API Approval)'}")

        st.button(
            "🔄 Push Step 1 Categories, Services & Description to Live GBP",
            disabled=not has_gbp_oauth,
            use_container_width=True,
            help="Requires GBP API OAuth credentials in Streamlit Secrets. Automatically sends a PATCH request to `[https://mybusinessbusinessinformation.googleapis.com/v1/](https://mybusinessbusinessinformation.googleapis.com/v1/){location_id}`."
        )
        st.button(
            "📥 Pull Live Client Reviews & Insights from GBP",
            disabled=not has_gbp_oauth,
            use_container_width=True,
            help="Requires GBP API OAuth credentials in Streamlit Secrets."
        )
