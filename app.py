import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
import google.generativeai as genai
import requests
import time
import re

# --- SETUP ---
st.set_page_config(page_title="AI Powered Real Estate Dashboard", layout="wide")

st.title("🚀 AI-Powered Project Proximity Dashboard")
st.markdown("Uses **OSRM** for Car Routes and **Gemini AI** for precise Market Intelligence.")

# --- HELPER FUNCTIONS ---

def extract_coords_from_url(url):
    """Extracts Lat/Long from a Google Maps Link (including redirects)."""
    try:
        if any(x in url for x in ["goo.gl", "google", "maps.app.goo.gl"]):
            r = requests.get(url, allow_redirects=True, timeout=10)
            url = r.url
        match = re.search(r'@([-.\d]+),([-.\d]+)', url)
        if match: return float(match.group(1)), float(match.group(2))
        match_alt = re.search(r'!3d([-.\d]+)!4d([-.\d]+)', url)
        if match_alt: return float(match_alt.group(1)), float(match_alt.group(2))
    except: pass
    return None

def get_soc_coordinates(society, locality, city="Pune"):
    """Finds society coordinates using multiple search attempts."""
    geolocator = Nominatim(user_agent="pune_ai_agent_v6")
    clean_soc = re.sub(r'\b(CHSL|CHS|Society|Phase \d+|Wing [A-Z])\b', '', society, flags=re.IGNORECASE).strip()
    
    queries = [f"{society}, {locality}, {city}", f"{clean_soc}, {locality}, {city}", f"{locality}, {city}"]
    for q in queries:
        try:
            loc = geolocator.geocode(q, timeout=10)
            if loc: return (loc.latitude, loc.longitude)
        except: continue
        time.sleep(1.1) # Free tier requirement
    return None

def get_car_distance(origin, dest):
    """Calculates road distance (Car) using OSRM."""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{origin[1]},{origin[0]};{dest[1]},{dest[0]}?overview=false"
        data = requests.get(url).json()
        if data['code'] == 'Ok':
            return round(data['routes'][0]['distance'] / 1000, 2)
    except: return "N/A"
    return "N/A"

def fetch_market_with_ai(society, locality, city, api_key):
    """Uses Gemini AI to extract structured info from search snippets."""
    if not api_key:
        return "Enter API Key", "Enter API Key"
    
    # 1. Search for data
    query = f"{society} {locality} {city} current price and BHK configurations"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(f"https://html.duckduckgo.com/html/?q={query}", headers=headers, timeout=10)
        search_text = res.text[:5000] # Grab first 5000 chars of HTML
        
        # 2. Ask Gemini to extract data
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Extract the following for '{society}' in '{locality}':
        1. All available BHK configurations (strictly 1 BHK to 5 BHK).
        2. The ticket size (Price range in Lakhs/Crores).
        
        Search Results Text: {search_text}
        
        Return ONLY in this format:
        BHK: [List BHKs found]
        Price: [Price found]
        """
        
        response = model.generate_content(prompt)
        content = response.text
        
        # Parse Gemini response
        bhk = re.search(r'BHK:\s*(.*)', content)
        price = re.search(r'Price:\s*(.*)', content)
        
        final_bhk = bhk.group(1).strip() if bhk else "1, 2, 3 BHK"
        final_price = price.group(1).strip() if price else "Check Online"
        
        return final_price, final_bhk
    except Exception as e:
        return "AI Error", "AI Error"

# --- SIDEBAR ---
with st.sidebar:
    st.header("Settings")
    gemini_key = st.text_input("Gemini API Key", type="password")
    project_url = st.text_input("Project Google Maps Link")
    st.info("Get a free Gemini key at aistudio.google.com")
    run_btn = st.button("Start Analysis")

# --- MAIN PAGE ---
uploaded_file = st.file_uploader("Upload Excel/CSV", type=['csv', 'xlsx'])

if uploaded_file and run_btn:
    if not gemini_key or not project_url:
        st.warning("Please provide both API Key and Project Link.")
    else:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        
        project_coords = extract_coords_from_url(project_url)
        
        if not project_coords:
            st.error("Invalid Google Maps Link.")
        else:
            results = []
            progress = st.progress(0)
            status = st.empty()
            
            for idx, row in df.iterrows():
                soc, loc = str(row.get('society', '')), str(row.get('locality', ''))
                city = str(row.get('city', 'Pune'))
                
                status.text(f"Analyzing {soc} via Gemini AI...")
                
                # 1. Car Distance
                soc_coords = get_soc_coordinates(soc, loc, city)
                dist = "Not Found"
                if soc_coords:
                    d_val = get_car_distance(project_coords, soc_coords)
                    dist = f"{d_val} km" if d_val != "N/A" else "N/A"
                
                # 2. Market Intel via Gemini
                price, bhk = fetch_market_with_ai(soc, loc, city, gemini_key)
                
                results.append({
                    "Distance from project": dist,
                    "Ticket Size": price,
                    "Configurations": bhk
                })
                
                progress.progress((idx + 1) / len(df))
            
            # Combine and Show
            final_df = pd.concat([df, pd.DataFrame(results)], axis=1)
            st.success("Analysis Finished!")
            st.dataframe(final_df)
            st.download_button("Download AI Report", final_df.to_csv(index=False), "ai_report.csv")
