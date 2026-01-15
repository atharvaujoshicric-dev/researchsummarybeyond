import streamlit as st
import pandas as pd
import re
import io
from openpyxl.styles import Alignment

def extract_area_logic(text):
    if pd.isna(text) or text == "": return 0.0
    text = " ".join(str(text).split())
    text = text.replace(' ,', ',').replace(', ', ',')
    m_unit = r'(?:चौ\.?\s*मी\.?|चौरस\s*मी[टत]र|sq\.?\s*m(?:tr)?\.?)'
    f_unit = r'(?:चौ\.?\s*फू\.?|चौरस\s*फु[टत]|sq\.?\s*f(?:t)?\.?)'
    total_keywords = r'(?:ए[ककु]ण\s*क्षेत्र|क्षेत्रफळ|total\s*area)'
    
    # Metric Extraction
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
        
    # Imperial Fallback
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

def apply_excel_formatting(df, writer, sheet_name):
    df.to_excel(writer, sheet_name=sheet_name, index=False)
    worksheet = writer.sheets[sheet_name]
    center_align = Alignment(horizontal='center', vertical='center')

    def merge_cells_for_col(col_idx, group_by_col_indices):
        start_row = 2
        for i in range(2, len(df) + 2):
            curr_key = [df.iloc[i-2, c] for c in group_by_col_indices]
            next_key = [df.iloc[i-1, c] for c in group_by_col_indices] if i-1 < len(df) else None
            if curr_key != next_key:
                if i > start_row:
                    worksheet.merge_cells(start_row=start_row, start_column=col_idx, end_row=i, end_column=col_idx)
                    worksheet.cell(row=start_row, column=col_idx).alignment = center_align
                start_row = i + 1

    merge_cells_for_col(1, [0])    # Merge Property
    merge_cells_for_col(2, [0, 1]) # Merge Configuration within Property

# --- STREAMLIT UI ---
st.set_page_config(page_title="Real Estate Analytics Dashboard", layout="wide")
st.title("🏠 Real Estate Data Extractor & Advanced Summary")

# Parameters in Sidebar
st.sidebar.header("Calculation Settings")
loading_factor = st.sidebar.number_input("Loading Factor", min_value=1.0, value=1.35, step=0.001, format="%.3f")
t1 = st.sidebar.number_input("1 BHK Threshold (<)", value=600)
t2 = st.sidebar.number_input("2 BHK Threshold (<)", value=850)
t3 = st.sidebar.number_input("3 BHK Threshold (<)", value=1100)

uploaded_file = st.file_uploader("Upload Raw Excel File (.xlsx)", type="xlsx")

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    clean_cols = {c.lower().strip(): c for c in df.columns}
    desc_col, cons_col, prop_col = clean_cols.get('property description'), clean_cols.get('consideration value'), clean_cols.get('property')
    
    if desc_col and cons_col and prop_col:
        with st.spinner('Calculating Statistics...'):
            # 1. Row Level Calculations
            df['Carpet Area (SQ.MT)'] = df[desc_col].apply(extract_area_logic)
            df['Carpet Area (SQ.FT)'] = (df['Carpet Area (SQ.MT)'] * 10.764).round(3)
            df['Saleable Area'] = (df['Carpet Area (SQ.FT)'] * loading_factor).round(3)
            df['APR'] = df.apply(lambda r: round(r[cons_col]/r['Saleable Area'], 3) if r['Saleable Area'] > 0 else 0, axis=1)
            df['Configuration'] = df['Carpet Area (SQ.FT)'].apply(lambda x: determine_config(x, t1, t2, t3))
            
            # Sort for clean grouping
            valid_df = df[df['Carpet Area (SQ.FT)'] > 0].sort_values([prop_col, 'Configuration', 'Carpet Area (SQ.FT)'])
            
            # 2. Summary Logic (Group by Project, BHK, and Size)
            summary = valid_df.groupby([prop_col, 'Configuration', 'Carpet Area (SQ.FT)']).agg(
                Min_APR=('APR', 'min'),
                Max_APR=('APR', 'max'),
                Avg_APR=('APR', 'mean'),
                Median_APR=('APR', 'median'),
                Mode_APR=('APR', lambda x: x.mode().iloc[0] if not x.mode().empty else 0),
                Property_Count=(prop_col, 'count')
            ).reset_index()
            
            # Column Renaming
            summary.columns = [
                'Property', 'Configuration', 'Carpet Area(SQ.FT)', 
                'Min. APR', 'Max APR', 'Average of APR', 
                'Median of APR', 'Mode of APR', 'Count of Property'
            ]
            
            # Precision Rounding
            stat_cols = ['Min. APR', 'Max APR', 'Average of APR', 'Median of APR', 'Mode of APR']
            summary[stat_cols] = summary[stat_cols].round(3)

            # 3. Multi-Sheet Export
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Raw Data', index=False)
                apply_excel_formatting(summary, writer, 'Summary')
            
            st.success("Analysis Complete!")
            st.subheader("Summary Preview (Median & Mode Included)")
            st.dataframe(summary.head(20))
            
            st.download_button(
                label="📥 Download Merged Excel Report",
                data=output.getvalue(),
                file_name="Property_Summary_Report_Final.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error("Required columns missing: 'Property Description', 'Property', 'Consideration Value'.")
