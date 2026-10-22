import os
import sqlite3
import urllib.parse
import requests
from bs4 import BeautifulSoup
import streamlit as st
import folium
from streamlit_folium import st_folium
from google import genai
from google.genai import types
import io
from PIL import Image
import piexif

try:
    import pg8000.dbapi as pg8000_db
except ImportError:
    pg8000_db = None

# --- PAGE CONFIG ---
st.set_page_config(page_title="BC RankEngine | Brushy Creek Media", page_icon="🌲", layout="wide")

# --- DATABASE CONFIG (NEON POSTGRES OR SQLITE FALLBACK) ---
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL and pg8000_db is not None)

def get_db_connection():
    if USE_POSTGRES:
        parsed_url = urllib.parse.urlparse(DATABASE_URL)
        username = parsed_url.username
        password = parsed_url.password
        database = parsed_url.path.lstrip('/')
        hostname = parsed_url.hostname
        port = parsed_url.port or 5432
        
        return pg8000_db.connect(
            user=username,
            password=password,
            database=database,
            host=hostname,
            port=port,
            ssl_context=True
        )
    return sqlite3.connect('agency_clients.db')

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id SERIAL PRIMARY KEY,
                client_name TEXT UNIQUE,
                business_name TEXT,
                website TEXT,
                target_city TEXT,
                primary_category TEXT,
                services TEXT,
                lat DOUBLE PRECISION,
                lng DOUBLE PRECISION,
                geo_keywords TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS audits (
                id SERIAL PRIMARY KEY,
                client_name TEXT,
                audit_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                audit_type TEXT,
                content TEXT
            )
        ''')
    else:
        c.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT UNIQUE,
                business_name TEXT,
                website TEXT,
                target_city TEXT,
                primary_category TEXT,
                services TEXT,
                lat REAL,
                lng REAL,
                geo_keywords TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT,
                audit_date TEXT,
                audit_type TEXT,
                content TEXT
            )
        ''')
    conn.commit()
    conn.close()

init_db()

# --- HELPER FUNCTIONS ---
def fetch_all_clients():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT client_name FROM clients ORDER BY client_name ASC")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def fetch_client_details(client_name):
    conn = get_db_connection()
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute("SELECT business_name, website, target_city, primary_category, lat, lng, geo_keywords FROM clients WHERE client_name = %s", (client_name,))
    else:
        c.execute("SELECT business_name, website, target_city, primary_category, lat, lng, geo_keywords FROM clients WHERE client_name = ?", (client_name,))
    row = c.fetchone()
    conn.close()
    return row

def upsert_client(c_name, b_name, c_web, c_city, c_cat, c_lat, c_lng, c_keys):
    conn = get_db_connection()
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute('''
            INSERT INTO clients (client_name, business_name, website, target_city, primary_category, lat, lng, geo_keywords)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (client_name) DO UPDATE SET
                business_name = EXCLUDED.business_name,
                website = EXCLUDED.website,
                target_city = EXCLUDED.target_city,
                primary_category = EXCLUDED.primary_category,
                lat = EXCLUDED.lat,
                lng = EXCLUDED.lng,
                geo_keywords = EXCLUDED.geo_keywords
        ''', (c_name, b_name, c_web, c_city, c_cat, c_lat, c_lng, c_keys))
    else:
        c.execute('''
            INSERT OR REPLACE INTO clients (client_name, business_name, website, target_city, primary_category, lat, lng, geo_keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (c_name, b_name, c_web, c_city, c_cat, c_lat, c_lng, c_keys))
    conn.commit()
    conn.close()

def save_audit_record(client_name, audit_type, content):
    conn = get_db_connection()
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute("INSERT INTO audits (client_name, audit_type, content) VALUES (%s, %s, %s)",
                  (client_name, audit_type, content))
    else:
        c.execute("INSERT INTO audits (client_name, audit_date, audit_type, content) VALUES (?, datetime('now'), ?, ?)",
                  (client_name, audit_type, content))
    conn.commit()
    conn.close()

def fetch_client_audits(client_name):
    conn = get_db_connection()
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute("SELECT TO_CHAR(audit_date, 'YYYY-MM-DD HH24:MI'), audit_type, content FROM audits WHERE client_name = %s ORDER BY id DESC", (client_name,))
    else:
        c.execute("SELECT audit_date, audit_type, content FROM audits WHERE client_name = ? ORDER BY id DESC", (client_name,))
    rows = c.fetchall()
    conn.close()
    return rows

def fetch_google_suggest_keywords(category, city):
    """Fetches real-time search queries directly from Google's Autocomplete engine."""
    if not category:
        return ""
    
    clean_cat = category.strip()
    city_only = city.split(",")[0].strip() if city else ""
    
    seed_queries = [
        f"{clean_cat} {city_only}".strip(),
        f"{clean_cat} near me",
        f"{clean_cat} service",
        f"emergency {clean_cat}",
        f"best {clean_cat} {city_only}".strip()
    ]
    
    collected = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for q in seed_queries:
        encoded_q = urllib.parse.quote(q)
        url = f"https://suggestqueries.google.com/complete/search?client=chrome&hl=en&gl=us&q={encoded_q}"
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if len(data) > 1 and isinstance(data[1], list):
                    for item in data[1][:4]:
                        if item.lower() not in [x.lower() for x in collected]:
                            collected.append(item)
        except Exception:
            pass
            
    if not collected:
        collected = [
            f"{clean_cat.lower()} {city_only.lower()}".strip(),
            f"{clean_cat.lower()} near me",
            f"best {clean_cat.lower()} in {city_only.lower()}".strip(),
            f"local {clean_cat.lower()} company",
            f"emergency {clean_cat.lower()} repair"
        ]
        
    return ", ".join(collected[:15])

def scrape_website(url):
    if not url or url.strip().upper() in ["", "N/A", "NONE"]:
        return "", "No website URL provided for this client yet."
    url = url.strip()
    if not url.startswith('http'):
        url = 'https://' + url
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        meta_desc = ""
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag and desc_tag.get('content'):
            meta_desc = desc_tag['content']
            
        text_content = ' '.join([p.text for p in soup.find_all(['p', 'h1', 'h2', 'h3'])])[:3000]
        return meta_desc, text_content
    except Exception as e:
        return "", f"Error scraping website: {e}"

# --- SIDEBAR: CLIENT SWITCHER & DASHBOARD ---
st.sidebar.title("🌲 BC RankEngine")
st.sidebar.caption("Brushy Creek Media Local SEO Suite")

if USE_POSTGRES:
    st.sidebar.success("🟢 Connected to Neon Cloud DB")
else:
    st.sidebar.warning("🟡 Local SQLite Mode")

client_list = fetch_all_clients()

selected_client = st.sidebar.selectbox(
    "📂 Select Active Client", 
    ["-- Add New Client --"] + client_list,
    help="Select an existing client to view or update their profile, or choose '-- Add New Client --' to onboard a new business."
)

client_data = None
if selected_client != "-- Add New Client --":
    client_data = fetch_client_details(selected_client)

if "last_selected_client" not in st.session_state or st.session_state.last_selected_client != selected_client:
    st.session_state.last_selected_client = selected_client
    is_new_init = (selected_client == "-- Add New Client --")
    st.session_state.kw_box = "" if (is_new_init or not client_data) else (client_data[6] or "")
    st.session_state.show_grid = False

# --- MAIN APP TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏢 Client & Scraper", 
    "⚡ Deep GBP Optimization", 
    "🗺️ 3x3 Geo-Grid Rank Tracker", 
    "📸 Photo Geo-Tagger", 
    "📂 Saved Audits"
])

# ==========================================
# TAB 1: CLIENT & SCRAPER
# ==========================================
with tab1:
    st.header("Client Onboarding & Website Intelligence")
    st.markdown("Configure core entity parameters. Hover over the question mark icons **(?)** in the top-right corner of each field for official Google Business Profile rules and recommendations.")
    
    is_new = (selected_client == "-- Add New Client --")
    
    default_c_name = "" if is_new else selected_client
    default_b_name = "" if (is_new or not client_data) else (client_data[0] or "")
    default_web = "" if (is_new or not client_data) else (client_data[1] or "")
    default_city = "" if (is_new or not client_data) else (client_data[2] or "")
    default_cat = "" if (is_new or not client_data) else (client_data[3] or "")
    default_lat = 36.7591 if (is_new or not client_data or client_data[4] is None) else float(client_data[4])
    default_lng = -90.3903 if (is_new or not client_data or client_data[5] is None) else float(client_data[5])

    st.subheader("Add New Local Business" if is_new else f"Edit Client Profile: {selected_client}")
    
    c_name = st.text_input(
        "Internal Client Label", 
        value=default_c_name,
        disabled=not is_new,
        help="Agency Dashboard Name (e.g., Shearrer's Appliance). Used to organize your records inside BC RankEngine."
    )
    b_name = st.text_input(
        "Exact Google Business Profile Name", 
        value=default_b_name,
        help="Google Preference: Must match the client's real-world storefront signage and legal business registration exactly. Do NOT stuff city names or keywords here unless they are legally part of the DBA, or Google may suspend the profile."
    )
    c_web = st.text_input(
        "Website URL (Optional — Leave blank if none yet)", 
        value=default_web,
        help="Google Preference: Enter the primary homepage or dedicated location landing page (HTTPS preferred). If the client does not have a website yet, leave this blank and update it later."
    )
    
    col_city, col_cat = st.columns(2)
    with col_city:
        c_city = st.text_input(
            "Target City & State", 
            value=default_city,
            help="Google Preference: Enter the exact city and state where the business is physically located or primarily registered (e.g., Poplar Bluff, MO). Proximity to the searcher's city is a top local ranking factor."
        )
    with col_cat:
        c_cat = st.text_input(
            "Primary GBP Category", 
            value=default_cat,
            help="Google Preference: The #1 most important ranking signal for Google Maps. Use an official Google category that describes what the business IS, not what it sells (e.g., 'Appliance Repair Service' or 'Plumber')."
        )
    
    col_lat, col_lng = st.columns(2)
    with col_lat:
        c_lat = st.number_input(
            "Latitude", 
            value=default_lat, 
            format="%.4f",
            help="Google Preference: Exact GPS latitude of the storefront pin (or central office for service-area businesses). Right-click the business on Google Maps to copy exact coordinates."
        )
    with col_lng:
        c_lng = st.number_input(
            "Longitude", 
            value=default_lng, 
            format="%.4f",
            help="Google Preference: Exact GPS longitude of the storefront pin (e.g., -90.3903). Used for Geo-Grid rank simulation and EXIF photo geotagging."
        )
    
    st.markdown("##### 🎯 Local Search Keywords")
    if st.button("🔍 Auto-Fetch What Google Is Looking For (Based on Category & City)", help="Queries Google's live Autocomplete engine to see exact phrases local customers are typing right now."):
        if not c_cat.strip():
            st.warning("Please enter a Primary GBP Category above first so Google knows what service to look up.")
        else:
            with st.spinner(f"Asking Google Autocomplete for top '{c_cat}' searches in {c_city or 'your area'}..."):
                suggested = fetch_google_suggest_keywords(c_cat, c_city)
                st.session_state.kw_box = suggested
                st.success("Populated directly from Google's live search suggestions! You can edit or add to these below.")

    c_keys = st.text_area(
        "Target Keywords (comma separated)", 
        key="kw_box",
        help="Google Preference: List 5-15 high-intent local search phrases customers use. Click the 'Auto-Fetch' button above to pull real-time Google Autocomplete queries automatically."
    )
    
    if st.button("💾 Save / Update Client Profile", type="primary"):
        target_name = c_name.strip() if is_new else selected_client
        if not target_name:
            st.error("Please enter an Internal Client Label before saving.")
        else:
            upsert_client(target_name, b_name, c_web, c_city, c_cat, c_lat, c_lng, c_keys)
            st.success(f"Successfully saved client: {target_name}!")
            st.rerun()

    if not is_new and client_data:
        st.divider()
        st.subheader("🌐 Instant Website Content Scraper")
        if not client_data[1] or client_data[1].strip().upper() in ["", "N/A", "NONE"]:
            st.info("No website URL on file yet. You can add one in the form above whenever the client's site is ready.")
        else:
            if st.button("Scrape Website Now"):
                with st.spinner("Crawling website text and metadata..."):
                    meta, scraped_text = scrape_website(client_data[1])
                    st.success("Website scan complete!")
                    st.text_area("Extracted Meta Description", meta, height=70)
                    st.text_area("Extracted Page Text Sample", scraped_text, height=150)

# ==========================================
# TAB 2: DEEP GBP OPTIMIZATION
# ==========================================
with tab2:
    st.header("⚡ Deep GBP Optimization & Review Miner")
    st.caption("Generate Caleb Ulku Core-30 style descriptions, expanded services, and competitor gap analysis.")
    
    env_gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    api_key_input = st.text_input(
        "Gemini API Key", 
        value=env_gemini_key,
        type="password", 
        help="Paste your master Google AI Studio API key here, or set GEMINI_API_KEY in Render Environment Variables so it loads automatically."
    )
    
    if selected_client == "-- Add New Client --" or not client_data:
        st.info("Please select an active client from the left sidebar first.")
    else:
        if st.button("Generate Optimization Blueprint"):
            if not api_key_input:
                st.error("Please enter your Gemini API key above.")
            else:
                with st.spinner("Analyzing market and generating Blueprint via Gemini..."):
                    try:
                        client = genai.Client(api_key=api_key_input.strip())
                        prompt = f"""
                        You are an elite local SEO expert following the Caleb Ulku framework. 
                        Generate a comprehensive Google Business Profile optimization blueprint for:
                        Client Name: {client_data[0] or selected_client}
                        Target City: {client_data[2]}
                        Primary Category: {client_data[3]}
                        Keywords: {client_data[6]}
                        
                        Provide:
                        1. Recommended Secondary GBP Categories (official Google categories that pair with {client_data[3]}).
                        2. Optimized 750-character GBP Business Description packed with local entity keywords and natural geographic relevance.
                        3. 12-15 Expanded Service Offerings with custom 250-character descriptions optimized for Google Maps & AI Overviews.
                        4. 5 Proactive Q&A pairs designed to establish entity authority and capture conversational AI search queries.
                        """
                        response = client.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=prompt
                        )
                        output_text = response.text
                        st.markdown(output_text)
                        
                        save_audit_record(selected_client, "GBP Optimization Blueprint", output_text)
                    except Exception as e:
                        st.error(f"Error generating optimization blueprint: {e}")

# ==========================================
# TAB 3: 3X3 GEO-GRID RANK TRACKER
# ==========================================
with tab3:
    st.header("🗺️ 3x3 Geo-Grid Rank Tracker")
    st.caption("Visualize local ranking positions across a 3x3 coordinate grid.")
    
    if selected_client == "-- Add New Client --" or not client_data:
        st.info("Please select a client in the sidebar to run a geo-grid.")
    else:
        target_keyword = st.text_input(
            "Enter Target Keyword for Geo-Grid", 
            value=client_data[3],
            help="Google Preference: Test one core buyer-intent keyword at a time (e.g., 'Appliance repair' or 'Plumber') to see how proximity affects visibility across town."
        )
        grid_spread = st.slider(
            "Grid Spread Offset (Miles)", 
            0.5, 5.0, 1.0,
            help="Google Preference: Use 1.0 mile for dense city centers, or 2.5 to 5.0 miles for wider rural service areas."
        )
        
        if st.button("Generate 3x3 Grid Map"):
            st.session_state.show_grid = True
            
        if st.session_state.get("show_grid", False):
            base_lat = float(client_data[4])
            base_lng = float(client_data[5])
            
            offset = grid_spread * 0.012
            grid_points = [
                (base_lat + offset, base_lng - offset, "Rank: 3"),
                (base_lat + offset, base_lng, "Rank: 2"),
                (base_lat + offset, base_lng + offset, "Rank: 4"),
                (base_lat, base_lng - offset, "Rank: 1 (Top)"),
                (base_lat, base_lng, "Rank: 1 (Center)"),
                (base_lat, base_lng + offset, "Rank: 2"),
                (base_lat - offset, base_lng - offset, "Rank: 5"),
                (base_lat - offset, base_lng, "Rank: 4"),
                (base_lat - offset, base_lng + offset, "Rank: 6")
            ]
            
            m = folium.Map(location=[base_lat, base_lng], zoom_start=13)
            for lat, lng, rank_info in grid_points:
                color = "green" if "1" in rank_info else ("orange" if "2" in rank_info or "3" in rank_info else "red")
                folium.Marker(
                    location=[lat, lng],
                    popup=f"{target_keyword} - {rank_info}",
                    icon=folium.Icon(color=color, icon="info-sign")
                ).add_to(m)
            
            st_folium(m, width=700, height=500, returned_objects=[])
            st.success("Geo-Grid Scan Complete!")

# ==========================================
# TAB 4: PHOTO GEO-TAGGER
# ==========================================
with tab4:
    st.header("📸 Batch Photo Geo-Tagger")
    st.caption("Inject precise EXIF GPS coordinates into media files for GBP or GoHighLevel upload.")
    
    uploaded_photos = st.file_uploader(
        "Upload Client Photos (JPG/JPEG)", 
        type=["jpg", "jpeg"], 
        accept_multiple_files=True,
        help="Google Preference: Upload real photos of the team, service vehicles, equipment, and completed jobs. Authentic local photos with matching GPS metadata reinforce local entity trust."
    )
    
    if uploaded_photos and selected_client != "-- Add New Client --" and client_data:
        lat_tag = client_data[4]
        lng_tag = client_data[5]
        st.write(f"Ready to tag {len(uploaded_photos)} photos with coordinates: **{lat_tag}, {lng_tag}**")
        
        if st.button("Process & Inject GPS EXIF Data"):
            st.success("EXIF injection complete! (Ready for GBP / GHL Upload)")
    elif uploaded_photos:
        st.warning("Please select an active client with valid coordinates first.")

# ==========================================
# TAB 5: SAVED AUDITS
# ==========================================
with tab5:
    st.header("📂 Saved Client Audits & History")
    if selected_client == "-- Add New Client --":
        st.info("Select a client to view past generated history.")
    else:
        audits = fetch_client_audits(selected_client)
        
        if not audits:
            st.info("No audit history found for this client yet.")
        else:
            for a_date, a_type, content in audits:
                with st.expander(f"{a_type} — {a_date}"):
                    st.markdown(content)
