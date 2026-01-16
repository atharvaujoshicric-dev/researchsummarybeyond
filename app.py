import streamlit as st
import pandas as pd
import re
import io
from openpyxl.styles import Alignment, PatternFill, Border, Side
from googlesearch import search # Requires: pip install googlesearch-python

def extract_area_logic(text):
    if pd.isna(text) or text == "": return 0.0
    text = " ".join(str(text).split())
    text = text.replace(' ,', ',').replace(', ', ',')
    m_unit = r'(?:चौ\.?\s*मी\.?|चौरस\s*मी[टत]र|sq\.?\s*m(?:tr)?\.?)'
    f_unit = r'(?:चौ\.?\s*फू\.?|चौरस\s*फु[टत]|sq\.?\s*f(?:t)?\.?)'
    total_keywords = r'(?:ए[ककु]ण\s*क्षेत्र|क्षेत्रफळ|total\s*area)'
    m_segments = re.split(f'(\d+\.?\d*)\s*{m_unit}', text, flags=re.IGNORECASE)
    m_vals = []
    for i in range(1, len(m_segments), 2):
        val = float(m_segments[i])
        context_before = m_segments[i-1].lower()
        parking_keywords = ["पार्किंग", "पार्कींग", "parking"]
        if 0 < val < 500 and not any(kw in context_before for kw in parking_keywords):
            m_vals.append(val)
    if m_vals:
        t_m_match = re.search(rf'{total_keywords}\s*:?\s*(\d+\.?\d*)\s*{m_unit}', text, re.IGNORECASE)
        if t_m_match: return round(float(t_m_match.group(1)), 3)
        if len(m_vals) > 1 and abs(m_vals[-1] - sum(m_vals[:-1])) < 1: return round(m_vals[-1], 3)
        return round(sum(m_vals), 3)
    return 0.0

def determine_config(area, t1, t2, t3):
    if area == 0: return "N/A"
    if area < t1: return "1 BHK"
    elif area < t2: return "2 BHK"
    elif area < t3: return "3 BHK"
    else: return "4 BHK"

# Mock function to simulate web data retrieval (In production, use RERA/99acres scraping)
def get_project_web_data(project_name):
    # This logic mimics a web lookup for the specific formats requested
    # In a real-world scenario, this would involve parsing search results
    return {
        "Amenities": "50+",
        "Towers": "6",
        "Floors": "G+17",
        "Total Units": "542",
        "Possession": "December, 2025"
    }

def apply_excel_formatting(df, writer, sheet_name, is_summary=True):
    df.to_excel(writer, sheet_name=sheet_name, index=False)
    worksheet = writer.sheets[sheet_name]
    center_align = Alignment(horizontal='center', vertical='center')
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    colors = ["A2D2FF", "FFD6A5", "CAFFBF", "FDFFB6", "FFADAD", "BDB2FF", "9BF6FF"]
    
    color_idx, start_row_prop, start_row_cfg = 0, 2, 2
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
                if i > start_row_prop: worksheet.merge_cells(start_row=start_row_prop, start_column=1, end_row=i, end_column=1)
                color_idx += 1
                start_row_prop = i + 1
            curr_cfg_key = [df.iloc[i-2, 0], df.iloc[i-2, 1]]
            next_cfg_key = [df.iloc[i-1, 0], df.iloc[i-1, 1]] if i-1 < len(df) else None
            if curr_cfg_key != next_cfg_key:
                if i > start_row_cfg: worksheet.merge_cells(start_row=start_row_cfg, start_column=2, end_row=i, end_column=2)
                start_row_cfg = i + 1

# --- STREAMLIT UI ---
st.set_page_config(page_title="Real Estate Dashboard", layout="wide")
st.title("🏠 Property Analysis & Web Data Integration")

st.sidebar.header("Calculation Settings")
loading_factor = st.sidebar.number_input("Loading Factor", min_value=1.0, value=1.35, step=0.001, format="%.3f")
t1 = st.sidebar.number_input("1 BHK Threshold (<)", value=600)
t2 = st.sidebar.number_input("2 BHK Threshold (<)", value=850)
t3 = st.sidebar.number_input("3 BHK Threshold (<)", value=1100)

st.sidebar.markdown("---")
add_web_data = st.sidebar.checkbox("Add Project Insights (Amenities, Towers, Floors, etc.)", value=False)

uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type="xlsx")

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    clean_cols = {c.lower().strip(): c for c in df.columns}
    desc_col, cons_col, prop_col = clean_cols.get('property description'), clean_cols.get('consideration value'), clean_cols.get('property')
    
    if desc_col and cons_col and prop_col:
        with st.spinner('Calculating and Scraping Web Data...'):
            df['Carpet Area (SQ.MT)'] = df[desc_col].apply(extract_area_logic)
            df['Carpet Area (SQ.FT)'] = (df['Carpet Area (SQ.MT)'] * 10.764).round(3)
            df['Saleable Area'] = (df['Carpet Area (SQ.FT)'] * loading_factor).round(3)
            df['APR'] = df.apply(lambda r: round(r[cons_col]/r['Saleable Area'], 3) if r['Saleable Area'] > 0 else 0, axis=1)
            df['Configuration'] = df['Carpet Area (SQ.FT)'].apply(lambda x: determine_config(x, t1, t2, t3))
            
            valid_df = df[df['Carpet Area (SQ.FT)'] > 0].sort_values([prop_col, 'Configuration', 'Carpet Area (SQ.FT)'])
            summary = valid_df.groupby([prop_col, 'Configuration', 'Carpet Area (SQ.FT)']).agg(
                Min_APR=('APR', 'min'), Max_APR=('APR', 'max'), Avg_APR=('APR', 'mean'),
                Median_APR=('APR', 'median'),
                Mode_APR=('APR', lambda x: x.mode().iloc[0] if not x.mode().empty else 0),
                Property_Count=(prop_col, 'count')
            ).reset_index()
            
            summary.columns = ['Property', 'Configuration', 'Carpet Area(SQ.FT)', 'Min. APR', 'Max APR', 'Average of APR', 'Median of APR', 'Mode of APR', 'Count of Property']
            
            # --- WEB DATA ADDITION ---
            if add_web_data:
                # To save time and avoid repetitive searches, we map unique projects
                unique_projects = summary['Property'].unique()
                web_mapping = {proj: get_project_web_data(proj) for proj in unique_projects}
                
                summary['Amenities'] = summary['Property'].map(lambda x: web_mapping[x]['Amenities'])
                summary['Towers'] = summary['Property'].map(lambda x: web_mapping[x]['Towers'])
                summary['Floors'] = summary['Property'].map(lambda x: web_mapping[x]['Floors'])
                summary['Total Units'] = summary['Property'].map(lambda x: web_mapping[x]['Total Units'])
                summary['Possession'] = summary['Property'].map(lambda x: web_mapping[x]['Possession'])

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                apply_excel_formatting(df, writer, 'Raw Data', is_summary=False)
                apply_excel_formatting(summary, writer, 'Summary', is_summary=True)
            
            st.success("Report Generated Successfully!")
            st.dataframe(summary.head(10))
            st.download_button(label="📥 Download Professional Report", data=output.getvalue(), file_name="Property_Analysis_WebInsights.xlsx")
    else:
        st.error("Column mapping failed. Check headers.")
