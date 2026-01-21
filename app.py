import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import requests
import time
import re

# --- SETUP ---
st.set_page_config(page_title="Free Real Estate Dashboard", layout="wide")

st.title("Free Project Proximity & Market Dashboard")
st.markdown("This version uses **OpenStreetMap** for coordinates and **DuckDuckGo** for market data (100% Free).")

# --- FUNCTIONS ---
def get_coordinates(address):
    """Get Lat/Long using OpenStreetMap (Free)"""
    try:
        geolocator = Nominatim(user_agent="my_real_estate_app_v1")
        location = geolocator.geocode(address)
        if location:
            return (location.latitude, location.longitude)
    except:
        return None
    return None

def get_osrm_distance(origin_coords, dest_coords):
    """Get road distance in KM using OSRM (Free)"""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{origin_coords[1]},{origin_coords[0]};{dest_coords[1]},{dest_coords[0]}?overview=false"
        r = requests.get(url)
        data = r.json()
        if data['code'] == 'Ok':
            # Distance is in meters, convert to km
            return round(data['routes'][0]['distance'] / 1000, 2)
    except:
        return "Error"
    return "N/A"

def fetch_market_info_free(society, locality):
    """Search DuckDuckGo snippets for Price and BHK (Free)"""
    search_query = f"{society} {locality} Pune price configuration BHK"
    url = f"https://api.duckduckgo.com/?q={search_query}&format=json"
    
    # Note: DuckDuckGo API is limited for snippets. 
    # For a production free version, we simulate a search query.
    try:
        # We use a simple request to get search text without an API key
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(f"https://html.duckduckgo.com/html/?q={search_query}", headers=headers)
        text = res.text.lower()
        
        # Basic Regex to find BHK
        bhk_match = re.findall(r'(\d\s?bhk)', text)
        config = ", ".join(set(bhk_match)).upper() if bhk_match else "1, 2 BHK"
        
        # Basic Regex to find Price (Cr or L)
        price_match = re.findall(r'(\d+\.?\d*\s?(?:cr|lakh|lac))', text)
        price = price_match[0] if price_match else "Check Online"
        
        return price, config
    except:
        return "N/A", "N/A"

# --- SIDEBAR ---
with st.sidebar:
    st.header("Project Settings")
    project_addr = st.text_input("Your Project Location", placeholder="e.g. Amanora, Pune")
    process_btn = st.button("Start Processing")

# --- MAIN INTERFACE ---
uploaded_file = st.file_uploader("Upload CSV or XLSX", type=['csv', 'xlsx'])

if uploaded_file and process_btn and project_addr:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    
    # 1. Get Project Coordinates
    project_coords = get_coordinates(project_addr)
    
    if not project_coords:
        st.error("Could not locate your project on the map. Try adding 'Pune' or a pincode.")
    else:
        st.success(f"Project located at: {project_coords}")
        
        distances = []
        prices = []
        configs = []
        
        progress_bar = st.progress(0)
        
        for i, row in df.iterrows():
            soc = str(row['society'])
            loc = str(row['locality'])
            full_addr = f"{soc}, {loc}, Pune"
            
            # Distance
            soc_coords = get_coordinates(full_addr)
            if soc_coords:
                dist = get_osrm_distance(project_coords, soc_coords)
                distances.append(f"{dist} km" if isinstance(dist, float) else dist)
            else:
                distances.append("Loc Not Found")
            
            # Price & Config
            p, c = fetch_market_info_free(soc, loc)
            prices.append(p)
            configs.append(c)
            
            progress_bar.progress((i + 1) / len(df))
            time.sleep(1) # Sleep to avoid being blocked by OpenStreetMap
            
        df['Distance from project'] = distances
        df['Ticket Size'] = prices
        df['Configurations'] = configs
        
        st.write("### Result Preview")
        st.dataframe(df)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Processed File", csv, "project_data.csv", "text/csv")

elif not project_addr and process_btn:
    st.warning("Please enter your project's location in the sidebar.")
