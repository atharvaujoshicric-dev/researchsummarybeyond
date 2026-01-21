import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
import google.generativeai as genai
import requests
import time
import re
import json

# --- APP SETUP ---
st.set_page_config(page_title="Real Estate Market Intelligence", layout="wide")

st.title("🚗 AI-Powered Real Estate Dashboard")
st.markdown("""
This tool calculates **Car Road Distances** and uses **Gemini AI** to find 1-5 BHK configurations and prices.
""")

# --- LOGIC FUNCTIONS ---

def extract_coords_from_url(url):
    """Extracts Lat/Long from a Google Maps Link (Shortened or Full)."""
    try:
        if any(x in url for x in ["goo.gl", "google", "maps.app.goo.gl"]):
            r = requests.get(url, allow_redirects=True, timeout=10)
            url = r.url
        
        # Regex for @lat,long
        match = re.search(r'@([-.\d]+),([-.\d]+)', url)
        if match: return float(match.group(1)), float(match.group(2))
        
        # Regex for !3d...!4d...
        match_alt = re.search(r'!3d([-.\d]+)!4d([-.\d]+)', url)
        if match_alt: return float(match_alt.group(1)), float(match_alt.group(2))
    except Exception as e:
        st.error(f"Error parsing link: {e}")
    return None

def clean_society_name(name):
    """Removes noise like 'A1- Maintenance', 'CHSL', 'C Wing' to improve search hits."""
    # Pattern to remove common Pune/Excel suffixes
    noise = r'\b(CHSL|CHS|Society|Phase \d+|Wing [A-Z]|Maintenance|Limited|Ltd|Pune)\b'
    cleaned = re.sub(noise, '', str(name), flags=re.IGNORECASE)
    # Remove extra dashes or special characters often found in your file
    cleaned = re.sub(r'[-–—]', ' ', cleaned)
    return ' '.join(cleaned.split()).strip()

def get_coordinates(society, locality, city="Pune"):
    """Finds coordinates using iterative search (Full -> Cleaned -> Locality)."""
    geolocator = Nominatim(user_agent="pune_real_estate_ai_v7")
    clean_soc = clean_society_name(society)
    
    # Try 3 different combinations to ensure we don't get "Location Not Found"
    search_queries = [
        f"{society}, {locality}, {city}", 
        f"{clean_soc}, {locality}, {city}",
        f"{locality}, {city}" # Fallback to Locality center
    ]
    
    for q in search_queries:
        try:
            loc = geolocator.geocode(q, timeout=10)
            if loc: return (loc.latitude, loc.longitude)
        except: continue
        time.sleep(1.2) # Required for free usage
    return None

def get_car_distance(origin, dest):
    """Calculates driving distance via OSRM Car Routing API."""
    try:
        # Format: lon,lat;lon,lat
        url = f"http://router.project-osrm.org/route/v1/driving/{origin[1]},{origin[0]};{dest[1]},{dest[0]}?overview=false"
        data = requests.get(url, timeout=10).json()
        if data['code'] == 'Ok':
            dist_km = data['routes'][0]['distance'] / 1000
            return round(dist_km, 2)
    except:
        return "N/A"
    return "N/A"

def fetch_market_ai(society, locality, city, gemini_key):
    """Uses Gemini AI to find Price and 1-5 BHK configurations from web search snippets."""
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    search_query = f"{society} {locality} {city} price configurations 1bhk 2bhk 3bhk 4bhk 5bhk"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        # Search DuckDuckGo (Free/No Key)
        res = requests.get(f"https://html.duckduckgo.com/html/?q={search_query}", headers=headers, timeout=10)
        snippet = res.text[:7000] # Provide context to Gemini
        
        prompt = f"""
        Analyze the search results for the society '{society}' in '{locality}, {city}'.
        Identify:
        1. Every available BHK configuration (strictly from 1 to 5 BHK).
        2. The 'Ticket Size' (Current market price/range in Cr or Lakhs).
        
        Search Context: {snippet}
        
        Output ONLY in this JSON format:
        {{"bhk": "1, 2, 3 BHK", "price": "₹85 L - 1.5 Cr"}}
        If no price is found, use 'Market Rates'.
        """
        
        response = model.generate_content(prompt)
        # Clean JSON from markdown if Gemini adds it
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return data.get('price', 'N/A'), data.get('bhk', 'N/A')
    except:
        pass
    return "Market Rates", "1, 2, 3 BHK"

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("🔑 Credentials")
    gemini_api_key = st.text_input("Gemini API Key", type="password", help="Get at aistudio.google.com")
    st.header("📍 Project Location")
    project_url = st.text_input("Project Google Maps Link")
    st.divider()
    run_button = st.button("Generate Dashboard", use_container_width=True)

# --- MAIN PAGE LOGIC ---
uploaded_file = st.file_uploader("Upload your file (Excel or CSV)", type=['csv', 'xlsx'])

if uploaded_file and run_button:
    if not gemini_api_key or not project_url:
        st.error("Please provide both the Gemini API Key and Project Link in the sidebar.")
    else:
        # Load File
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        # Extract Project Coords
        project_coords = extract_coords_from_url(project_url)
        
        if not project_coords:
            st.error("Could not extract coordinates from the Google Maps link. Try copying it again.")
        else:
            st.success(f"Project Location Locked. Processing {len(df)} rows...")
            
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, row in df.iterrows():
                soc = str(row.get('society', ''))
                loc = str(row.get('locality', ''))
                city = str(row.get('city', 'Pune'))
                
                status_text.text(f"Analyzing ({i+1}/{len(df)}): {soc}")
                
                # 1. Road Distance (Car)
                soc_coords = get_coordinates(soc, loc, city)
                dist_str = "Not Found"
                if soc_coords:
                    d_val = get_car_distance(project_coords, soc_coords)
                    dist_str = f"{d_val} km" if d_val != "N/A" else "N/A"
                
                # 2. Market Data (AI)
                price, bhks = fetch_market_ai(soc, loc, city, gemini_api_key)
                
                results.append({
                    "Distance from project": dist_str,
                    "Ticket Size": price,
                    "Configurations": bhks
                })
                
                progress_bar.progress((i + 1) / len(df))
            
            # Combine Data
            results_df = pd.DataFrame(results)
            final_df = pd.concat([df.reset_index(drop=True), results_df], axis=1)
            
            # Show Results
            st.subheader("Final Processed Data")
            st.dataframe(final_df)
            
            # Download Button
            csv_output = final_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download Updated File", csv_output, "Project_Analysis.csv", "text/csv")

elif not run_button:
    st.info("👈 Enter your details in the sidebar and click Generate.")
