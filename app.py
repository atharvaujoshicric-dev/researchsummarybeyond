import streamlit as st
import pandas as pd
import google.generativeai as genai
import requests
import re
import json
import time

# --- SETUP ---
st.set_page_config(page_title="Pune Real Estate AI Dashboard", layout="wide")

st.title("🏙️ Real Estate Proximity & Market Dashboard")
st.markdown("Automated Analysis for Pune Projects using Gemini AI.")

# --- IMPROVED HELPER FUNCTIONS ---

def get_real_coords(url):
    """Expands shortened Google Maps links and extracts Lat/Long."""
    try:
        # 1. Expand the URL if it's a shortened link
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, allow_redirects=True, timeout=10, headers=headers)
        full_url = response.url
            
        # 2. Extract Lat/Long using multiple Regex patterns
        # Pattern A: @18.52,73.85
        match = re.search(r'@([-.\d]+),([-.\d]+)', full_url)
        if match:
            return f"{match.group(1)}, {match.group(2)}"
        
        # Pattern B: !3d18.52!4d73.85
        match_alt = re.search(r'!3d([-.\d]+)!4d([-.\d]+)', full_url)
        if match_alt:
            return f"{match_alt.group(1)}, {match_alt.group(2)}"
            
    except Exception as e:
        st.error(f"Error expanding link: {e}")
    return None

def get_gemini_analysis(society, locality, project_coords, api_key):
    """Uses Gemini 1.5 Flash to replicate your specific chat logic with coordinates."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # We provide the exact coordinates to ensure Gemini knows the origin point
    prompt = f"""
    Context: Act as a Pune real estate analyst.
    Origin Point (Project): {project_coords}
    Target Society: "{society}" in "{locality}, Pune"

    Task:
    1. Distance: Provide the driving distance (car route) from the origin to this society in KM. 
    2. Ticket Size: Give the average market price for units here (e.g., 75 Lakhs - 1.2 Cr). Do NOT say 'Check Online'.
    3. Configurations: List all typical configurations (Check for 1, 2, 3, 4, 5 BHK).

    Important: If you are unsure of the exact distance, provide an estimate based on the locality's general distance from the origin coordinates.
    Return ONLY a JSON object:
    {{"distance": "X.X km", "price": "range", "config": "list"}}
    """
    
    try:
        response = model.generate_content(prompt)
        # Handle cases where AI adds markdown backticks
        json_str = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return json.loads(json_str)
    except:
        # Final fallback if AI fails
        return {"distance": "Check Locality", "price": "Contact Builder", "config": "2, 3 BHK"}

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Configuration")
    # Using the key you provided
    api_key = st.text_input("Gemini API Key", value="AIzaSyA4i_sX4N1RgOIJyNkN3cH2n1iXE-e1DU4", type="password")
    project_link = st.text_input("Project Google Maps Link", placeholder="Paste your Shubh Tristar link...")
    
    st.divider()
    run_btn = st.button("🚀 Process My Excel")

# --- MAIN APP ---
uploaded_file = st.file_uploader("Upload 'Book 5.xlsx'", type=['csv', 'xlsx'])

if uploaded_file and project_link and run_btn:
    # Read the file
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    
    # 1. Get Project Coordinates first
    with st.spinner("Decoding your Google Maps link..."):
        proj_coords = get_real_coords(project_link)
    
    if not proj_coords:
        st.error("Could not find coordinates in your link. Try using the full URL from your browser address bar.")
    else:
        st.info(f"Project Origin: {proj_coords}. Starting Analysis...")
        
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, row in df.iterrows():
            soc = str(row.get('society', ''))
            loc = str(row.get('locality', ''))
            
            status_text.text(f"Analyzing {idx+1}/{len(df)}: {soc}")
            
            # Use AI to get the data
            ai_data = get_gemini_analysis(soc, loc, proj_coords, api_key)
            
            results.append({
                "Distance from project": ai_data.get("distance"),
                "Ticket Size": ai_data.get("price"),
                "Configurations": ai_data.get("config")
            })
            
            progress_bar.progress((idx + 1) / len(df))
            time.sleep(0.5) # Protect API quota

        # Final Table
        final_df = pd.concat([df.reset_index(drop=True), pd.DataFrame(results)], axis=1)
        st.success("✅ Dashboard Complete!")
        st.dataframe(final_df)
        
        # Download
        st.download_button("Download Processed Excel", final_df.to_csv(index=False), "pune_market_analysis.csv", "text/csv")
