import streamlit as st
import pandas as pd
import googlemaps
import requests
import time

# --- SETUP ---
st.set_page_config(page_title="Real Estate Proximity Dashboard", layout="wide")

st.title("Project Proximity & Market Intelligence Dashboard")
st.markdown("""
Upload your society list, provide your project's location, and this tool will calculate distances and find market data (Ticket Size & Configurations).
""")

# --- SIDEBAR: API KEYS & INPUTS ---
with st.sidebar:
    st.header("Configuration")
    gmaps_key = st.text_input("Google Maps API Key", type="password")
    serp_api_key = st.text_input("SerpApi Key (for Price/Config search)", type="password", help="Get one at serpapi.com")
    
    st.divider()
    
    project_location = st.text_input("Enter Your Project's Google Maps Location", placeholder="e.g., Amanora Park Town, Hadapsar, Pune")
    
    st.info("The tool will add 3 columns: 'Distance from project', 'Ticket Size', and 'Configurations'.")

# --- FILE UPLOADER ---
uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=['csv', 'xlsx'])

def get_market_data(society_name, locality, api_key):
    """
    Uses SerpApi to search for property details.
    """
    if not api_key:
        return "N/A", "N/A"
    
    query = f"{society_name} {locality} price configuration BHK"
    search_url = "https://serpapi.com/search"
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": 3  # Look at top 3 results
    }
    
    try:
        response = requests.get(search_url, params=params)
        data = response.json()
        
        # This is a simplified logic to extract info from search snippets
        # In a production environment, you might use LLMs to parse this text
        snippets = " ".join([result.get("snippet", "") for result in data.get("organic_results", [])])
        
        # Placeholder extraction logic (Basic keyword search)
        # In practice, these details are best fetched via specific Real Estate APIs if available
        ticket_size = "Contact for Price"
        if "Cr" in snippets or "Lakh" in snippets:
            # Very basic extraction - improvement would involve Regex or LLM
            words = snippets.split()
            for i, word in enumerate(words):
                if "Cr" in word or "Lakh" in word:
                    ticket_size = f"{words[i-1]} {word}"
                    break
                    
        config = "1, 2, 3 BHK" # Default fallback
        if "4 BHK" in snippets: config = "2, 3, 4 BHK"
        elif "3 BHK" in snippets: config = "2, 3 BHK"
        
        return ticket_size, config
    except:
        return "Search Error", "Search Error"

def process_data(df, gmaps, project_loc, serp_key):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    distances = []
    ticket_sizes = []
    configs = []
    
    # Geocode the project location first
    project_geo = gmaps.geocode(project_loc)
    if not project_geo:
        st.error("Could not find your project location. Please be more specific.")
        return None
    
    origin_coords = project_geo[0]['geometry']['location']
    
    for index, row in df.iterrows():
        society = str(row['society'])
        locality = str(row['locality'])
        city = str(row.get('city', ''))
        
        search_query = f"{society}, {locality}, {city}"
        status_text.text(f"Processing: {society}...")
        
        # 1. Distance Calculation
        try:
            # Using Distance Matrix for accurate road distance
            dist_result = gmaps.distance_matrix(project_loc, search_query, mode="driving")
            if dist_result['rows'][0]['elements'][0]['status'] == 'OK':
                dist_km = dist_result['rows'][0]['elements'][0]['distance']['text']
                distances.append(dist_km)
            else:
                distances.append("Not Found")
        except:
            distances.append("Error")

        # 2. Market Data (Ticket Size & Config)
        t_size, cfg = get_market_data(society, locality, serp_key)
        ticket_sizes.append(t_size)
        configs.append(cfg)
        
        # Update progress
        progress = (index + 1) / len(df)
        progress_bar.progress(progress)
        time.sleep(0.1) # Small delay to respect rate limits

    df['Distance from project'] = distances
    df['Ticket Size'] = ticket_sizes
    df['Configurations'] = configs
    
    status_text.text("Processing Complete!")
    return df

# --- MAIN LOGIC ---
if uploaded_file and gmaps_key and project_location:
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    st.write("### Original Data Preview", df.head())
    
    if st.button("Generate Dashboard Data"):
        gmaps = googlemaps.Client(key=gmaps_key)
        
        with st.spinner("Fetching distances and market data..."):
            result_df = process_data(df, gmaps, project_location, serp_api_key)
            
            if result_df is not None:
                st.success("Successfully updated all records!")
                st.write("### Updated Data", result_df)
                
                # Download Button
                csv = result_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Updated CSV",
                    data=csv,
                    file_name="updated_real_estate_data.csv",
                    mime="text/csv",
                )
else:
    if not gmaps_key:
        st.warning("Please enter your Google Maps API Key in the sidebar.")
    if not project_location:
        st.warning("Please enter your Project Location in the sidebar.")
    if not uploaded_file:
        st.info("Upload an Excel/CSV file to begin.")
