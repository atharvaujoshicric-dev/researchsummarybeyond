import streamlit as st
import pandas as pd
import re
import io
from openpyxl.styles import Alignment, PatternFill, Border, Side

def extract_area_logic(text):
    if pd.isna(text) or text == "": return 0.0
    
    # 1. Standardize text
    text = " ".join(str(text).split())
    text = text.replace(' ,', ',').replace(', ', ',')
    
    # 2. Refined Split: Only look at the portion describing the SPECIFIC unit
    # We split at the building name or flat number to ignore large plot areas (3336, 5813, etc.)
    unit_start_keywords = r'(?:इमारतीमधील|अपार्टमेंटमधील|टॉवरमधील|सदनिका|फ्लॅट|युनिट|unit|flat|tower)'
    parts = re.split(unit_start_keywords, text, flags=re.IGNORECASE)
    
    # If the description is long, the unit details are usually in the last 2 sections
    relevant_text = " ".join(parts[1:]) if len(parts) > 1 else parts[0]
    
    # 3. Unit Definitions
    m_unit = r'(?:चौ\.?\s*मी\.?|चौरस\s*मी[टत]र|sq\.?\s*m(?:tr)?\.?)'
    f_unit = r'(?:चौ\.?\s*फू\.?|चौरस\s*फु[टत]|sq\.?\s*f(?:t)?\.?)'
    
    # 4. Strategy: Priority to Explicit Metric (SQ.MT)
    # We find ALL metric numbers. To avoid double-counting "551 SQMT (5940 SQFT)", 
    # we ONLY look for numbers followed by SQ.MT.
    
    # Find all sequences of [Number] + [SQ.MT]
    metric_matches = re.findall(rf'(\d+(?:\.\d+)?)\s*{m_unit}', relevant_text, re.IGNORECASE)
    m_vals = [float(v) for v in metric_matches]

    # Filter out obvious plot/land areas that might have leaked into the second half
    # A single flat component (carpet/terrace) is rarely > 600 sq.mt.
    m_vals = [v for v in m_vals if 0 < v < 650]

    if m_vals:
        # Check if the last value is the sum of the others (Common in legal text)
        if len(m_vals) > 1 and abs(m_vals[-1] - sum(m_vals[:-1])) < 1.0:
            return round(m_vals[-1], 3)
        return round(sum(m_vals), 3)

    # 5. Fallback: Strategy for Imperial (SQ.FT)
    # Only if no metric values were found
    ft_matches = re.findall(rf'(\d+(?:\.\d+)?)\s*{f_unit}', relevant_text, re.IGNORECASE)
    f_vals = [float(v.replace(',', '')) for v in ft_matches]
    f_vals = [v for v in f_vals if 0 < v < 7000]

    if f_vals:
        if len(f_vals) > 1 and abs(f_vals[-1] - sum(f_vals[:-1])) < 5.0:
            return round(f_vals[-1] / 10.764, 3)
        return round(sum(f_vals) / 10.764, 3)
        
    return 0.0

def determine_config(area, t1, t2, t3):
    if area == 0: return "N/A"
    if area < t1: return "1 BHK"
    elif area < t2: return "2 BHK"
    elif area < t3: return "3 BHK"
    else: return "4+ BHK / Duplex"

def apply_excel_formatting(df, writer, sheet_name, is_summary=True):
    df.to_excel(writer, sheet_name=sheet_name, index=False)
    worksheet = writer.sheets[sheet_name]
    center_align = Alignment(horizontal='center', vertical='center')
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    
    colors = ["A2D2FF", "FFD6A5", "CAFFBF", "FDFFB6", "FFADAD", "BDB2FF", "9BF6FF"]
    color_idx = 0
    start_row_prop = 2
    
    for i in range(1, worksheet.max_row + 1):
        for j in range(1, worksheet.max_column + 1):
            cell = worksheet.cell(row=i, column=j)
            cell.alignment = center_align
            if is_summary: cell.border = thin_border

    if is_summary:
        for i in range(2, len(df) + 2):
            curr_prop = df.iloc[i-2, 0]
            next_prop = df.iloc[i-1, 0] if i-1 < len(df) else None
            fill = PatternFill(start_color=colors[color_idx % len(colors)], end_color=colors[color_idx % len(colors)], fill_type="solid")
            for col in range(1, len(df.columns) + 1):
                worksheet.cell(row=i, column=col).fill = fill
            if curr_prop != next_prop:
                color_idx += 1

# --- STREAMLIT UI ---
st.set_page_config(page_title="Real Estate Area Extractor", layout="wide")
st.sidebar.header("Settings")
loading_factor = st.sidebar.number_input("Loading Factor", value=1.35, format="%.3f")
t1 = st.sidebar.number_input("1 BHK Threshold (<)", value=650)
t2 = st.sidebar.number_input("2 BHK Threshold (<)", value=1000)
t3 = st.sidebar.number_input("3 BHK Threshold (<)", value=1500)

uploaded_file = st.file_uploader("Upload Property Excel", type="xlsx")

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    clean_cols = {c.lower().strip(): c for c in df.columns}
    desc_col = clean_cols.get('property description')
    cons_col = clean_cols.get('consideration value')
    prop_col = clean_cols.get('property')
    
    if desc_col and cons_col and prop_col:
        with st.spinner('Processing...'):
            df['Carpet Area (SQ.MT)'] = df[desc_col].apply(extract_area_logic)
            df['Carpet Area (SQ.FT)'] = (df['Carpet Area (SQ.MT)'] * 10.764).round(2)
            df['Saleable Area'] = (df['Carpet Area (SQ.FT)'] * loading_factor).round(2)
            df['APR'] = df.apply(lambda r: round(r[cons_col]/r['Saleable Area'], 2) if r['Saleable Area'] > 0 else 0, axis=1)
            df['Configuration'] = df['Carpet Area (SQ.FT)'].apply(lambda x: determine_config(x, t1, t2, t3))
            
            valid_df = df[df['Carpet Area (SQ.MT)'] > 0].copy()
            
            summary = valid_df.groupby([prop_col, 'Configuration', 'Carpet Area (SQ.FT)']).agg(
                Min_APR=('APR', 'min'), Max_APR=('APR', 'max'), Avg_APR=('APR', 'mean'), Property_Count=(prop_col, 'count')
            ).reset_index().round(2)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                apply_excel_formatting(df, writer, 'Raw Data', is_summary=False)
                apply_excel_formatting(summary, writer, 'Summary', is_summary=True)
            
            st.success("Calculations updated for Duplex and Multi-floor flats!")
            st.download_button("📥 Download Report", output.getvalue(), "Property_Analysis.xlsx")
