import streamlit as st
import pandas as pd
import re
import io

def extract_area_logic(text):
    """
    Advanced logic to extract property area from Marathi text.
    Handles vowel variations, Metric/Imperial units, and parking exclusion.
    """
    if pd.isna(text) or text == "":
        return 0.0
    
    text = " ".join(str(text).split())
    text = text.replace(' ,', ',').replace(', ', ',')
    
    m_unit = r'(?:चौ\.?\s*मी\.?|चौरस\s*मी[टत]र|sq\.?\s*m(?:tr)?\.?)'
    f_unit = r'(?:चौ\.?\s*फू\.?|चौरस\s*फु[टत]|sq\.?\s*f(?:t)?\.?)'
    total_keywords = r'(?:ए[ककु]ण\s*क्षेत्र|क्षेत्रफळ|total\s*area)'
    
    # METRIC EXTRACTION
    m_segments = re.split(f'(\d+\.?\d*)\s*{m_unit}', text, flags=re.IGNORECASE)
    m_vals = []
    for i in range(1, len(m_segments), 2):
        val = float(m_segments[i])
        context_before = m_segments[i-1].lower()
        if 0 < val < 500:
            if "पार्किंग" not in context_before and "parking" not in context_before:
                m_vals.append(val)
    
    if m_vals:
        t_m_match = re.search(rf'{total_keywords}\s*:?\s*(\d+\.?\d*)\s*{m_unit}', text, re.IGNORECASE)
        if t_m_match: return round(float(t_m_match.group(1)), 3)
        if len(m_vals) > 1 and abs(m_vals[-1] - sum(m_vals[:-1])) < 1: return round(m_vals[-1], 3)
        return round(sum(m_vals), 3)
        
    # FALLBACK TO SQ.FT
    f_segments = re.split(f'(\d+\.?\d*)\s*{f_unit}', text, flags=re.IGNORECASE)
    f_vals = []
    for i in range(1, len(f_segments), 2):
        val = float(f_segments[i])
        context_before = f_segments[i-1].lower()
        if 0 < val < 5000:
            if "पार्किंग" not in context_before and "parking" not in context_before:
                f_vals.append(val)
                
    if f_vals:
        t_f_match = re.search(rf'{total_keywords}\s*:?\s*(\d+\.?\d*)\s*{f_unit}', text, re.IGNORECASE)
        if t_f_match: return round(float(t_f_match.group(1)) / 10.764, 3)
        if len(f_vals) > 1 and abs(f_vals[-1] - sum(f_vals[:-1])) < 1: return round(f_vals[-1] / 10.764, 3)
        return round(sum(f_vals) / 10.764, 3)

    return 0.0

def determine_config(area, t1, t2, t3):
    if area == 0: return "N/A"
    if area < t1: return "1 BHK"
    elif area < t2: return "2 BHK"
    elif area < t3: return "3 BHK"
    else: return "4 BHK"

# --- STREAMLIT UI ---
st.set_page_config(page_title="Real Estate Analytics Tool", layout="wide")
st.title("🏠 Property Data Extractor & Summary Generator")

st.sidebar.header("Settings")
loading_factor = st.sidebar.number_input("Loading Factor", min_value=1.0, value=1.35, step=0.001, format="%.3f")
t1 = st.sidebar.number_input("1 BHK Threshold (<)", value=600)
t2 = st.sidebar.number_input("2 BHK Threshold (<)", value=850)
t3 = st.sidebar.number_input("3 BHK Threshold (<)", value=1100)

uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type="xlsx")

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    # Flexible column name check for 'Consideration Value' (Case sensitivity)
    cons_col = next((c for c in df.columns if c.lower() == 'Consideration Value'), None)
    prop_col = next((c for c in df.columns if c.lower() == 'property'), None)
    
    if "Property Description" in df.columns and cons_col and prop_col:
        with st.spinner('Generating Report...'):
            # 1. Base Calculations
            df['Carpet Area (SQ.MT)'] = df['Property Description'].apply(extract_area_logic)
            df['Carpet Area (SQ.FT)'] = (df['Carpet Area (SQ.MT)'] * 10.764).round(3)
            df['Saleable Area'] = (df['Carpet Area (SQ.FT)'] * loading_factor).round(3)
            df['APR'] = df.apply(lambda r: round(r[cons_col] / r['Saleable Area'], 3) if r['Saleable Area'] > 0 else 0, axis=1)
            df['Configuration'] = df['Carpet Area (SQ.FT)'].apply(lambda x: determine_config(x, t1, t2, t3))
            
            # 2. Summary Sheet Logic
            # Filter out zero areas for cleaner averages
            valid_df = df[df['Carpet Area (SQ.FT)'] > 0]
            
            summary = valid_df.groupby([prop_col, 'Configuration']).agg(
                Carpet_Area_FT=('Carpet Area (SQ.FT)', 'mean'),
                Min_APR=('APR', 'min'),
                Max_APR=('APR', 'max'),
                Avg_APR=('APR', 'mean'),
                Property_Count=('APR', 'count')
            ).reset_index()
            
            # Rename columns to match request exactly
            summary.columns = ['Property', 'Configuration', 'Carpet Area(SQ.FT)', 'Min. APR', 'Max APR', 'Average of APR', 'Count of Property']
            summary[['Carpet Area(SQ.FT)', 'Min. APR', 'Max APR', 'Average of APR']] = summary[['Carpet Area(SQ.FT)', 'Min. APR', 'Max APR', 'Average of APR']].round(3)

            # 3. Export to Multiple Sheets
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Raw Data', index=False)
                summary.to_excel(writer, sheet_name='Summary', index=False)
            
            st.success("Report Generated!")
            st.subheader("Summary Preview")
            st.dataframe(summary)
            
            st.download_button(
                label="📥 Download Multi-Sheet Excel Report",
                data=output.getvalue(),
                file_name="Property_Summary_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error(f"Required columns missing. Ensure file has: 'Property Description', 'Property', and 'Consideration Value'.")
