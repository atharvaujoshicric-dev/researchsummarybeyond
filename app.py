import streamlit as st
import pandas as pd
import google.generativeai as genai
from geopy.geocoders import Nominatim
import requests
import time
import re
import json

# --- SETUP ---
st.set_page_config(page_title="Pro Real Estate Dashboard", layout="wide")

st.title("🏙️ Project Proximity & AI Market Dashboard")
st.markdown("Powered by **Gemini AI** for accurate pricing and configurations.")

# --- SIDEBAR CONFIG ---
# --- Update this section in your app.py ---
with st.sidebar:
    st.header("1. API & Project Info")
    
    # Check if key is in Streamlit Secrets, otherwise ask user
    if "GEMINI_API_KEY" in st.secrets:
        gemini_key = st.secrets["GEMINI_API_KEY"]
        st.success("API Key loaded from Secrets!")
    else:
        gemini_key = st.text_input("Enter Gemini API Key", type="password")
        st.info("Tip: Add GEMINI_API_KEY to your Streamlit Cloud secrets to skip this.")
    
    project_addr = st.text_input("Project Location", value="Shubh Tristar, Mundhwa Rd, Pune 411036")
    st.divider()
    run_btn = st.button("🚀 Analyze Societies")

# --- AI DATA ENGINE ---
def get_ai_market_data(society, locality, city, api_key):
    """Uses Gemini to find precise real estate data."""
    if not api_key:
        return {"price": "Need API Key", "config": "Need API Key", "lat": None, "lon": None}
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Act as a Pune Real Estate expert. For the society "{society}" in "{locality}, {city}", provide:
    1. Average Ticket Size (Price range in Cr or Lakhs).
    2. All available configurations (from 1 BHK to 5 BHK).
    3. Approximate Latitude and Longitude of this society.
    
    Return ONLY a JSON object like this:
    {{"price": "1.2 - 1.5 Cr", "config": "2 BHK, 3 BHK", "lat": 18.5, "lon": 73.9}}
    """
    
    try:
        response = model.generate_content(prompt)
        # Clean the response to ensure it's valid JSON
        data_str = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return json.loads(data_str)
    except:
        return {"price": "Search Error", "config": "1-5 BHK", "lat": None, "lon": None}

def get_car_distance(origin_coords, dest_coords):
    """Calculates car driving distance via OSRM."""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{origin_coords[1]},{origin_coords[0]};{dest_coords[1]},{dest_coords[0]}?overview=false"
        r = requests.get(url, timeout=5)
        data = r.json()
        if data['code'] == 'Ok':
            return round(data['routes'][0]['distance'] / 1000, 2)
    except:
        return "N/A"
    return "N/A"

# --- MAIN INTERFACE ---
uploaded_file = st.file_uploader("Upload your Excel/CSV", type=['csv', 'xlsx'])

if uploaded_file and run_btn:
    if not gemini_key:
        st.error("Please enter a Gemini API Key in the sidebar.")
    else:
        # Load Data
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        
        # Geocode the main project once
        geolocator = Nominatim(user_agent="pune_ai_dash")
        project_loc = geolocator.geocode(project_addr)
        
        if not project_loc:
            st.error("Could not locate your project address. Please be more specific.")
        else:
            proj_coords = (project_loc.latitude, project_loc.longitude)
            
            results = []
            progress = st.progress(0)
            status = st.empty()
            
            for idx, row in df.iterrows():
                soc = str(row.get('society', ''))
                loc = str(row.get('locality', ''))
                city = str(row.get('city', 'Pune'))
                
                status.text(f"AI Analyzing ({idx+1}/{len(df)}): {soc}")
                
                # 1. Get AI Market Data (Price, Config, and Coords)
                ai_data = get_ai_market_data(soc, loc, city, gemini_key)
                
                # 2. Calculate Driving Distance
                dist_val = "Not Found"
                if ai_data.get('lat') and ai_data.get('lon'):
                    soc_coords = (ai_data['lat'], ai_data['lon'])
                    dist_km = get_car_distance(proj_coords, soc_coords)
                    dist_val = f"{dist_km} km" if dist_km != "N/A" else "Route Error"
                
                results.append({
                    "Distance from project": dist_val,
                    "Ticket Size": ai_data.get('price', 'N/A'),
                    "Configurations": ai_data.get('config', 'N/A')
                })
                
                progress.progress((idx + 1) / len(df))
                time.sleep(0.5) # Fast but respectful of API limits
            
            # Combine and Show
            res_df = pd.concat([df, pd.DataFrame(results)], axis=1)
            st.success("Analysis Complete!")
            st.dataframe(res_df)
            
            # Download
            st.download_button("Download Updated Report", res_df.to_csv(index=False), "Market_Report.csv")
