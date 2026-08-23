import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import time

st.set_page_config(page_title="Unilog MVP: Full Batch Pipeline", layout="wide")

# Custom CSS for Premium UI
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

.stApp {
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
    color: #e2e8f0;
    font-family: 'Inter', sans-serif;
}

h1 {
    font-weight: 800;
    background: -webkit-linear-gradient(45deg, #38bdf8, #818cf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-align: center;
    padding-bottom: 10px;
}

h2, h3 {
    color: #e2e8f0;
    font-weight: 600;
}

.stButton>button {
    background: linear-gradient(90deg, #38bdf8 0%, #818cf8 100%);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
    font-weight: 600;
    transition: all 0.3s ease;
    box-shadow: 0 4px 15px rgba(56, 189, 248, 0.4);
    width: 100%;
}
.stButton>button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(56, 189, 248, 0.6);
    color: white;
}

.stDownloadButton>button {
    background: linear-gradient(90deg, #10b981 0%, #34d399 100%);
    box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
}
.stDownloadButton>button:hover {
    box-shadow: 0 6px 20px rgba(16, 185, 129, 0.6);
    color: white;
}

[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

[data-testid="stSidebar"] {
    background-color: rgba(15, 23, 42, 0.6) !important;
    backdrop-filter: blur(10px);
    border-right: 1px solid rgba(255, 255, 255, 0.05);
}

[data-testid="stFileUploader"] {
    background: rgba(255, 255, 255, 0.03);
    border: 1px dashed rgba(255, 255, 255, 0.2);
    border-radius: 12px;
    padding: 15px;
    transition: all 0.3s ease;
}
[data-testid="stFileUploader"]:hover {
    background: rgba(255, 255, 255, 0.05);
    border-color: #38bdf8;
}

hr {
    border-color: rgba(255, 255, 255, 0.1);
}
</style>
""", unsafe_allow_html=True)

st.title("🏭 Unilog Enrichment Pipeline")
st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 1.1rem; margin-bottom: 2rem;'>Transform raw product catalogues into search-ready gold records instantly.</p>", unsafe_allow_html=True)
mock_mode = st.sidebar.checkbox("🚀 Use Mock Mode (No API Key Needed)", value=False, help="Bypass API entirely and use mock data for demonstrations")

if not mock_mode:
    api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")
    if not api_key:
        st.warning("Enter your API Key to unlock the pipeline, or enable Mock Mode in the sidebar.")
        st.stop()
    
    genai.configure(api_key=api_key)
    
    # The Model
    try:
        available_models = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        if not available_models:
            st.error("No compatible models found for this API key.")
            st.stop()
        
        # Try to default to 3.6-flash if available, otherwise pick the first one
        if 'gemini-3.6-flash' in available_models:
            default_idx = available_models.index('gemini-3.6-flash')
        elif 'gemini-1.5-flash' in available_models:
            default_idx = available_models.index('gemini-1.5-flash')
        else:
            default_idx = 0
            
        selected_model_name = st.sidebar.selectbox("Select Model", available_models, index=default_idx)
        model = genai.GenerativeModel(selected_model_name, generation_config={"response_mime_type": "application/json"})
    except Exception as e:
        if "API_KEY_INVALID" in str(e) or "400" in str(e):
            st.sidebar.error("Invalid API Key. If you just created it, make sure there are no extra spaces and wait 1-2 minutes for it to activate.")
        else:
            st.sidebar.error(f"Failed to fetch models: {e}")
        st.stop()
else:
    st.sidebar.success("Mock Mode Enabled! Processing will use simulated AI responses.")

# The Prompt - Mapping to Expected Delivery Format Columns
prompt = """
You are an expert industrial data extractor for Unilog. Analyze the raw string and extract properties.
Return a JSON object with these EXACT keys based on the input text:
"MANUFACTURER_NAME": (string or "")
"BRAND_NAME": (string or "")
"MOBILE_DESC": (short mobile description up to 80 chars, string or "")
"INVOICE_DESC": (ALL CAPS invoice description up to 40 chars, string or "")
"SHORT_DESC": (Product Title, string or "")
"LONG_DESC1": (Full long description, string or "")
"ATTRIBUTE_LABEL 1": "Size"
"ATTRIBUTE_VALUE 1": (Extracted dimensions, formatted as fractions e.g. 1/2 in)
"ATTRIBUTE_LABEL 2": "Material"
"ATTRIBUTE_VALUE 2": (Extracted material)
"CONFIDENCE_SCORE": (number 1-100 representing confidence in extraction)
"NEEDS_REVIEW": (boolean true if data is very ambiguous/missing key info)
"REASONING": (Short 1-sentence explanation of your extraction logic)

Raw text: {text}
"""

with st.expander("📁 Upload Datasets", expanded=True):
    col1, col2 = st.columns(2)
    uploaded_input = col1.file_uploader("Upload Input Data (1000 Items)", type=["csv"])
    uploaded_template = col2.file_uploader("Upload Expected Output Template (252 Cols)", type=["csv"])

if uploaded_input and uploaded_template:
    # 1. Load Data
    st.success("Files uploaded successfully! Processing preview...")
    input_df = pd.read_csv(uploaded_input)
    template_df = pd.read_csv(uploaded_template)
    
    # Filter out placeholder values as per guidelines
    placeholders = ["-- Unbranded --", "-- No Unilog Brand --", "-- No DIB Brand --"]
    input_df = input_df.replace(placeholders, "", regex=False)
    
    # Drop columns that are entirely empty after cleaning to make it look nicer
    input_df = input_df.replace("", pd.NA).dropna(axis=1, how='all').fillna("")
    
    st.subheader("Data Preview (Cleaned)")
    st.dataframe(input_df.head(), width='stretch')
    
    if st.button("Run Full Enrichment Pipeline"):
        results = []
        progress_bar = st.progress(0, text="Initializing AI pipeline...")
        
        # Process the entire batch
        batch = input_df
        for idx, row in batch.iterrows():
            raw_text = row.get('Part_Desc', '') + ' ' + row.get('Mfg_Part_Num', '')
            progress_bar.progress(idx / len(batch), text=f"Analyzing item {idx+1}/{len(batch)}: {row.get('Mfg_Part_Num', 'Unknown')}...")
            try:
                if mock_mode:
                    # Simulate API call (fast for full batch demo)
                    time.sleep(0.01)
                    
                    # Create varied mock responses to actually demonstrate explainability!
                    part_num = str(row.get('Mfg_Part_Num', 'ITEM-X')).upper()
                    mfg = str(row.get('Part_Manuf', 'Acme Corp')).title()
                    
                    if idx == 1:
                        score = 45
                        needs_review = True
                        reason = f"WARNING: Ambiguous string. Could not definitively identify voltage or dimensions from '{raw_text[:20]}...'."
                        attr1, attr2 = "", ""
                    elif idx == 3:
                        score = 82
                        needs_review = False
                        reason = f"Inferred attributes, but brand was missing. Fallback to Manufacturer Name used."
                        attr1, attr2 = "Standard", "Steel"
                    else:
                        score = 98
                        needs_review = False
                        reason = f"Perfect match. Extracted exact dimensions and materials from the description."
                        attr1 = "1/2 in" if "1/2" in raw_text else "Standard Size"
                        attr2 = "Brass" if "BRS" in raw_text.upper() else "Alloy"
                        
                    extracted_data = {
                        "MANUFACTURER_NAME": mfg,
                        "BRAND_NAME": mfg,
                        "MOBILE_DESC": f"{mfg} {part_num} Industrial Component",
                        "INVOICE_DESC": f"{part_num} COMPONENT",
                        "SHORT_DESC": f"{mfg} {part_num} General Use Component",
                        "LONG_DESC1": f"Fully extracted long description for {mfg} part number {part_num}. Designed for heavy duty industrial applications.",
                        "ATTRIBUTE_LABEL 1": "Size",
                        "ATTRIBUTE_VALUE 1": attr1,
                        "ATTRIBUTE_LABEL 2": "Material",
                        "ATTRIBUTE_VALUE 2": attr2,
                        "CONFIDENCE_SCORE": score,
                        "NEEDS_REVIEW": needs_review,
                        "REASONING": reason
                    }
                else:
                    response = model.generate_content(prompt.format(text=raw_text))
                    extracted_data = json.loads(response.text)
                
                # Combine original row with extracted data for preview
                combined = {**row.to_dict(), **extracted_data}
                results.append(combined)
            except Exception as e:
                st.error(f"Error processing row {idx}: {e}")
            
            progress_bar.progress((idx + 1) / len(batch), text=f"Completed {idx+1}/{len(batch)}")
            time.sleep(1) # Simple rate limit handling
            
        st.success("Batch processing complete!")
        results_df = pd.DataFrame(results)
        
        # Explainability & Validation Dashboard
        st.markdown("### 🔍 Validation & Explainability Report")
        colA, colB, colC = st.columns(3)
        avg_confidence = results_df['CONFIDENCE_SCORE'].mean() if 'CONFIDENCE_SCORE' in results_df else 0
        needs_review_count = results_df['NEEDS_REVIEW'].sum() if 'NEEDS_REVIEW' in results_df else 0
        
        if len(results_df) > 0:
            colA.metric("Avg Confidence Score", f"{avg_confidence:.1f}/100", delta="Excellent")
            colB.metric("Items Flagged for Review", f"{needs_review_count} / {len(results_df)}", delta="-1", delta_color="inverse")
            colC.metric("Extraction Success Rate", f"{((len(results_df) - needs_review_count)/len(results_df))*100:.1f}%", delta="Above Target")
            
            st.markdown("#### Confidence Distribution")
            chart_data = results_df[['MANUFACTURER_NAME', 'CONFIDENCE_SCORE']].set_index('MANUFACTURER_NAME')
            st.bar_chart(chart_data)
        else:
            st.warning("No results were generated. Please check the errors above.")
        
        with st.expander("View AI Reasoning & Explanations", expanded=True):
            if 'REASONING' in results_df.columns:
                for idx, row in results_df.iterrows():
                    icon = "⚠️" if row.get("NEEDS_REVIEW") else "✅"
                    st.markdown(f"**Item {idx}** {icon} (Score: {row.get('CONFIDENCE_SCORE')}): {row.get('REASONING')}")
        
        # Rearrange columns to show AI-extracted data first so it's easy to see
        ai_cols = ["CONFIDENCE_SCORE", "NEEDS_REVIEW", "REASONING", "MANUFACTURER_NAME", "BRAND_NAME", "SHORT_DESC", "MOBILE_DESC", "INVOICE_DESC"]
        existing_ai_cols = [c for c in ai_cols if c in results_df.columns]
        other_cols = [c for c in results_df.columns if c not in existing_ai_cols]
        results_df = results_df[existing_ai_cols + other_cols]
        
        st.subheader("Enriched Results (AI Data First)")
        # Apply conditional formatting for the datagrame based on Confidence
        def highlight_confidence(val):
            if not isinstance(val, (int, float)): return ''
            if val < 60: return 'background-color: rgba(239, 68, 68, 0.4); color: white;' # Red
            elif val > 90: return 'background-color: rgba(34, 197, 94, 0.4); color: white;' # Green
            return 'background-color: rgba(234, 179, 8, 0.4); color: white;' # Yellow

        def highlight_review(val):
            if val is True: return 'background-color: rgba(239, 68, 68, 0.5); font-weight: bold; color: white;'
            return ''
            
        styled_df = results_df.style.map(highlight_confidence, subset=['CONFIDENCE_SCORE']) \
                                    .map(highlight_review, subset=['NEEDS_REVIEW'])

        st.dataframe(styled_df, width='stretch')
        
        # Add Wow Factor Animation
        st.balloons()
        
        # Convert to CSV for download
        csv = results_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Enriched Preview",
            data=csv,
            file_name="enriched_output.csv",
            mime="text/csv",
        )
