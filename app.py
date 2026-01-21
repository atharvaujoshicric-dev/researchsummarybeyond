import streamlit as st
import pandas as pd
import google.generativeai as genai
import requests
import time
import re
import json

# --- CONFIGURATION ---
st.set_page_config(page_title="Real Estate Intelligence Dashboard", layout="wide")

st.title("🏙️ Real Estate Proximity & Market Dashboard")
st.markdown("Automating the logic from your Gemini chat for the entire society list.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Setup")
    # Using the API Key you provided
    api_key = st.text_input("Gemini API Key", value="AIzaSyA4i_sX4N1RgOIJyNkN3cH2n1iXE-e1DU4", type="password")
    
    # Base project location as per your context
    project_base = st.text_input("Your Project", value="Shubh Tristar, Mundhwa, Pune")
    
    st.divider()
    run_btn = st.button("🚀 Run Analysis")

# --- CORE FUNCTIONS ---

def get_gemini_data(society, locality, project_name, api_key):
    """Replicates your specific Gemini chat logic."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    I have a real estate project called "{project_name}". 
    For the society "{society}" in "{locality}, Pune", please find:
    1. The driving distance (car route) from {project_name} to this society in KM.
    2. The current Ticket Size (Price range in Lakhs/Crores).
    3. All available configurations (check for 1, 2, 3, 4, and 5 BHK).
    
    Return the result strictly in this JSON format:
    {{"distance": "value in km", "price": "value", "config": "value"}}
    """
    
    try:
        response = model.generate_content(prompt)
        # Extract JSON from the response text
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        return {"distance": "Error", "price": "Error", "config": "Error"}
    return {"distance": "N/A", "price": "N/A", "config": "N/A"}

# --- MAIN APP ---
uploaded_file = st.file_uploader("Upload 'Book 5.xlsx'", type=['csv', 'xlsx'])

if uploaded_file and run_btn:
    # Load the data
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    
    st.info(f"Processing {len(df)} societies. This will take a few minutes...")
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, row in df.iterrows():
        soc_name = str(row['society'])
        loc_name = str(row['locality'])
        
        status_text.text(f"Analyzing {idx+1}/{len(df)}: {soc_name}")
        
        # Get data using your Gemini logic
        data = get_gemini_data(soc_name, loc_name, project_base, api_key)
        
        results.append({
            "Distance from project": data.get("distance"),
            "Ticket Size": data.get("price"),
            "Configurations": data.get("config")
        })
        
        # Update UI
        progress_bar.progress((idx + 1) / len(df))
        # Small sleep to respect rate limits
        time.sleep(0.5)

    # Merge results and display
    output_df = pd.concat([df, pd.DataFrame(results)], axis=1)
    
    st.success("✅ Analysis Complete!")
    st.dataframe(output_df)
    
    # Download Button
    csv = output_df.to_csv(index=False).encode('utf-8')
    st.download_button("Download Processed Excel", csv, "shubh_tristar_analysis.csv", "text/csv")
