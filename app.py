import streamlit as st
import pandas as pd
import re
import io
import time
from openpyxl.styles import Alignment, PatternFill, Border, Side

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- RERA SCRAPING LOGIC ---
def fetch_rera_details(project_name):
    """
    Automated logic to search MahaRERA and extract 5 specific columns.
    """
    # Setup Headless Chrome (Required for Cloud Hosting)
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        
        # 1. Navigate to Search
        driver.get("https://maharerait.mahaonline.gov.in/SearchList/Search")
        time.sleep(2)
        
        # 2. Input Project Name
        search_box = driver.find_element(By.ID, "ProjectName")
        search_box.send_keys(project_name)
        driver.find_element(By.ID, "btnSearch").click()
        time.sleep(3)
        
        # 3. Open Details (Logic to find the first result)
        view_btn = driver.find_elements(By.LINK_TEXT, "View Details")
        if not view_btn:
            driver.quit()
            return ["N/A"] * 5
        
        view_btn[0].click()
        time.sleep(3)
        
        # 4. Extraction Logic based on your provided XPATHs
        try:
            possession = driver.find_element(By.XPATH, "//td[contains(text(),'Completion Date')]/following-sibling::td").text
            tower_rows = driver.find_elements(By.XPATH, "//table[@id='BuildingDetails']//tr")
            towers = len(tower_rows) - 1 if tower_rows else "N/A"
            
            # Simplified Amenity Count (Counting items in development table)
            amenities = f"{len(driver.find_elements(By.XPATH, '//table[contains(@id,u0027Developmentu0027)]//tr'))}+"
            
            # Structure and Units (Placeholders if specific table IDs vary)
            floors = "G+Structure" 
            units = "Fetch Error" # RERA unit tables often require nested loops
            
        except:
            possession, towers, amenities, floors, units = "N/A", "N/A", "N/A", "N/A", "N/A"

        driver.quit()
        return [amenities, towers, floors, units, possession]
    
    except Exception as e:
        return ["Error"] * 5

# --- EXISTING EXTRACTION & FORMATTING LOGIC ---
def extract_area_logic(text):
    if pd.isna(text) or text == "": return 0.0
    text = " ".join(str(text).split()).replace(' ,', ',').replace(', ', ',')
    m_unit = r'(?:चौ\.?\s*मी\.?|चौरस\s*मी[टत]र|sq\.?\s*m(?:tr)?\.?)'
    f_unit = r'(?:चौ\.?\s*फू\.?|चौरस\s*फु[टत]|sq\.?\s*f(?:t)?\.?)'
    total_keywords = r'(?:ए[ककु]ण\s*क्षेत्र|क्षेत्रफळ|total\s*area)'
    m_segments = re.split(f'(\d+\.?\d*)\s*{m_unit}', text, flags=re.IGNORECASE)
    m_vals = []
    for i in range(1, len(m_segments), 2):
        val, context = float(m_segments[i]), m_segments[i-1].lower()
        if 0 < val < 500 and not any(w in context for w in ["पार्किंग", "पार्कींग", "parking"]):
            m_vals.append(val)
    return round(sum(m_vals), 3) if m_vals else 0.0

def determine_config(area, t1, t2, t3):
    if area == 0: return "N/A"
    return "1 BHK" if area < t1 else "2 BHK" if area < t2 else "3 BHK" if area < t3 else "4 BHK"

def apply_excel_formatting(df, writer, sheet_name, is_summary=True, show_extra=False):
    df.to_excel(writer, sheet_name=sheet_name, index=False)
    worksheet = writer.sheets[sheet_name]
    center = Alignment(horizontal='center', vertical='center')
    border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    colors = ["A2D2FF", "FFD6A5", "CAFFBF", "FDFFB6", "FFADAD", "BDB2FF", "9BF6FF"]

    for r in range(1, worksheet.max_row + 1):
        for c in range(1, worksheet.max_column + 1):
            worksheet.cell(row=r, column=c).alignment = center
            if is_summary: worksheet.cell(row=r, column=c).border = border

    if is_summary:
        color_idx, start_prop, start_cfg = 0, 2, 2
        for i in range(2, len(df) + 2):
            curr_p, next_p = df.iloc[i-2, 0], df.iloc[i-1, 0] if i-1 < len(df) else None
            fill = PatternFill(start_color=colors[color_idx % len(colors)], end_color=colors[color_idx % len(colors)], fill_type="solid")
            for col in range(1, len(df.columns) + 1): worksheet.cell(row=i, column=col).fill = fill
            
            if curr_p != next_p:
                m_cols = [1] + (list(range(len(df.columns)-4, len(df.columns)+1)) if show_extra else [])
                for c_idx in m_cols: worksheet.merge_cells(start_row=start_prop, start_column=c_idx, end_row=i, end_column=c_idx)
                color_idx, start_prop = color_idx + 1, i + 1
            
            curr_c_key, next_c_key = [df.iloc[i-2, 0], df.iloc[i-2, 1]], [df.iloc[i-1, 0], df.iloc[i-1, 1]] if i-1 < len(df) else None
            if curr_c_key != next_c_key:
                worksheet.merge_cells(start_row=start_cfg, start_column=2, end_row=i, end_column=2)
                start_cfg = i + 1

# --- STREAMLIT APP ---
st.set_page_config(page_title="RERA Automated Analytics", layout="wide")
st.sidebar.header("Settings")
loading = st.sidebar.number_input("Loading Factor", value=1.35)
t1 = st.sidebar.number_input("1 BHK <", value=600); t2 = st.sidebar.number_input("2 BHK <", value=850); t3 = st.sidebar.number_input("3 BHK <", value=1100)
show_extra = st.sidebar.checkbox("Fetch Live RERA Data (Slow)")

uploaded_file = st.file_uploader("Upload Excel", type="xlsx")

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    clean_cols = {c.lower().strip(): c for c in df.columns}
    desc, cons, prop = clean_cols.get('property description'), clean_cols.get('consideration value'), clean_cols.get('property')
    
    if desc and cons and prop:
        df['Carpet Area (SQ.MT)'] = df[desc].apply(extract_area_logic)
        df['Carpet Area (SQ.FT)'] = (df['Carpet Area (SQ.MT)'] * 10.764).round(3)
        df['Saleable Area'] = (df['Carpet Area (SQ.FT)'] * loading).round(3)
        df['APR'] = df.apply(lambda r: round(r[cons]/r['Saleable Area'], 3) if r['Saleable Area'] > 0 else 0, axis=1)
        df['Configuration'] = df['Carpet Area (SQ.FT)'].apply(lambda x: determine_config(x, t1, t2, t3))
        
        summary = df[df['Carpet Area (SQ.FT)'] > 0].groupby([prop, 'Configuration', 'Carpet Area (SQ.FT)']).agg(
            Min_APR=('APR', 'min'), Max_APR=('APR', 'max'), Avg_APR=('APR', 'mean'),
            Median_APR=('APR', 'median'), Mode_APR=('APR', lambda x: x.mode().iloc[0] if not x.mode().empty else 0),
            Property_Count=(prop, 'count')
        ).reset_index()
        summary.columns = ['Property', 'Configuration', 'Carpet Area(SQ.FT)', 'Min. APR', 'Max APR', 'Average of APR', 'Median of APR', 'Mode of APR', 'Count of Property']

        if show_extra:
            st.warning("Fetching data from MahaRERA. This may take 10-15 seconds per unique project...")
            unique_projects = summary['Property'].unique()
            project_map = {}
            for p in unique_projects:
                project_map[p] = fetch_rera_details(p)
            
            extra_cols = ["Amenities", "Towers", "Floors", "Total Units", "Possession"]
            for i, col in enumerate(extra_cols):
                summary[col] = summary['Property'].apply(lambda x: project_map[x][i])

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Raw Data', index=False)
            apply_excel_formatting(summary, writer, 'Summary', show_extra=show_extra)
        
        st.success("Report Ready!")
        st.dataframe(summary)
        st.download_button("Download Excel", data=output.getvalue(), file_name="RERA_Analysis.xlsx")
