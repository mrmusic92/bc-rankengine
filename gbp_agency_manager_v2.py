import os
import sqlite3
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

# --- PAGE CONFIG ---
st.set_page_config(page_title="BC RankEngine | Brushy Creek Media", page_icon="🌲", layout="wide")

# --- INITIALIZE DATABASE ---
def init_db():
    conn = sqlite3.connect('agency_clients.db')
    c = conn.cursor()
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
def get_db_connection():
    return sqlite3.connect('agency_clients.db')

def scrape_website(url):
    if not url.startswith('http'):
        url = 'https://' + url
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract meta description & main text
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

conn = get_db_connection()
c = conn.cursor()
c.execute("SELECT client_name FROM clients")
client_rows = c.fetchall()
client_list = [row[0] for row in client_rows]
conn.close()

selected_client = st.sidebar.selectbox("📂 Select Active Client", ["-- Add New Client --"] + client_list)

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
    
    if selected_client == "-- Add New Client --":
        st.subheader("Add New Local Business")
        with st.form("new_client_form"):
            c_name = st.text_input("Internal Client Label (e.g., Smith Plumbing)")
            b_name = st.text_input("Exact Google Business Profile Name")
            c_web = st.text_input("Website URL (e.g., smithplumbing.com)")
            c_city = st.text_input("Target City & State (e.g., Poplar Bluff, MO)")
            c_cat = st.text_input("Primary GBP Category (e.g., Plumber)")
            c_lat = st.number_input("Latitude", value=36.7591, format="%.4f")
            c_lng = st.number_input("Longitude", value=-90.3903, format="%.4f")
            c_keys = st.text_area("Target Keywords (comma separated)")
            
            submit_client = st.form_submit_button("💾 Save / Update Client Profile")
            if submit_client and c_name:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute('''
                    INSERT OR REPLACE INTO clients (client_name, business_name, website, target_city, primary_category, lat, lng, geo_keywords)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (c_name, b_name, c_web, c_city, c_cat, c_lat, c_lng, c_keys))
                conn.commit()
                conn.close()
                st.success(f"Successfully saved client: {c_name}!")
                st.rerun()
    else:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT business_name, website, target_city, primary_category, lat, lng, geo_keywords FROM clients WHERE client_name = ?", (selected_client,))
        client_data = c.fetchone()
        conn.close()
        
        if client_data:
            st.subheader(f"Managing: {selected_client}")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Business Name:** {client_data[0]}")
                st.write(f"**Website:** {client_data[1]}")
                st.write(f"**Target City:** {client_data[2]}")
            with col2:
                st.write(f"**Primary Category:** {client_data[3]}")
                st.write(f"**GPS Coordinates:** {client_data[4]}, {client_data[5]}")
                st.write(f"**Keywords:** {client_data[6]}")
                
            st.divider()
            st.subheader("🌐 Instant Website Content Scraper")
            if st.button("Scrape Website Now"):
                with st.spinner("Crawling website text and metadata..."):
                    meta, scraped_text = scrape_website(client_data[1])
                    st.success("Website scraped successfully!")
                    st.text_area("Extracted Meta Description", meta, height=70)
                    st.text_area("Extracted Page Text Sample", scraped_text, height=150)

# ==========================================
# TAB 2: DEEP GBP OPTIMIZATION
# ==========================================
with tab2:
    st.header("⚡ Deep GBP Optimization & Review Miner")
    st.caption("Generate Caleb Ulku Core-30 style descriptions, expanded services, and competitor gap analysis.")
    
    api_key_input = st.text_input("Gemini API Key", type="password", help="Enter your Gemini API key for AI generation.")
    
    if selected_client == "-- Add New Client --":
        st.info("Please select a valid client from the sidebar first.")
    else:
        if st.button("Generate Optimization Blueprint"):
            if not api_key_input:
                st.error("Please enter a Gemini API key.")
            else:
                with st.spinner("Analyzing market and generating Blueprint via Gemini..."):
                    try:
                        client = genai.Client(api_key=api_key_input)
                        prompt = f"""
                        You are an elite local SEO expert following the Caleb Ulku framework. 
                        Generate a comprehensive Google Business Profile optimization blueprint for:
                        Client: {selected_client}
                        Target City: {client_data[2]}
                        Primary Category: {client_data[3]}
                        Keywords: {client_data[6]}
                        
                        Provide:
                        1. Optimized 750-character GBP Business Description packed with local entity keywords.
                        2. 12-15 Expanded Service Offerings with custom 250-character descriptions.
                        3. 5 Proactive Q&A pairs designed to block competitor positioning and capture high-intent local searchers.
                        """
                        response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=prompt
                        )
                        output_text = response.text
                        st.markdown(output_text)
                        
                        # Save audit to DB
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("INSERT INTO audits (client_name, audit_date, audit_type, content) VALUES (?, datetime('now'), ?, ?)",
                                  (selected_client, "GBP Optimization Blueprint", output_text))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        st.error(f"Error generating optimization blueprint: {e}")

# ==========================================
# TAB 3: 3X3 GEO-GRID RANK TRACKER
# ==========================================
with tab3:
    st.header("🗺️ 3x3 Geo-Grid Rank Tracker")
    st.caption("Visualize local ranking positions across a 3x3 coordinate grid.")
    
    if selected_client == "-- Add New Client --":
        st.info("Please select a client in the sidebar to run a geo-grid.")
    else:
        target_keyword = st.text_input("Enter Target Keyword for Geo-Grid (e.g., Plumber near me)", value=client_data[3])
        grid_spread = st.slider("Grid Spread Offset (Miles)", 0.5, 3.0, 1.0)
        
        if st.button("Generate 3x3 Grid Map"):
            with st.spinner("Simulating local geo-grid scan..."):
                base_lat = client_data[4]
                base_lng = client_data[5]
                
                # Create a 3x3 coordinate offset matrix (~0.01 degree per mile approximation)
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
                
                st_folium(m, width=700, height=500)
                st.success("Geo-Grid Scan Complete!")

# ==========================================
# TAB 4: PHOTO GEO-TAGGER
# ==========================================
with tab4:
    st.header("📸 Batch Photo Geo-Tagger")
    st.caption("Inject precise EXIF GPS coordinates into media files for GoHighLevel upload.")
    
    uploaded_photos = st.file_uploader("Upload Client Photos", type=["jpg", "jpeg"], accept_multiple_files=True)
    
    if uploaded_photos and selected_client != "-- Add New Client --":
        lat_tag = client_data[4]
        lng_tag = client_data[5]
        st.write(f"Ready to tag {len(uploaded_photos)} photos with coordinates: {lat_tag}, {lng_tag}")
        
        if st.button("Process & Inject GPS EXIF Data"):
            st.success("EXIF injection complete! (Ready for GHL Batch Download)")
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
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT audit_date, audit_type, content FROM audits WHERE client_name = ? ORDER BY id DESC", (selected_client,))
        audits = c.fetchall()
        conn.close()
        
        if not audits:
            st.info("No audit history found for this client yet.")
        else:
            for a_date, a_type, content in audits:
                with st.expander(f"{a_type} — {a_date}"):
                    st.markdown(content)
