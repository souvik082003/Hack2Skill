# Hack2Skill

## AI-Powered Product Intelligence for Industrial Commerce (Unilog MVP)

This project is an AI-powered Enrichment Pipeline designed to transform messy, unsearchable product data into rich, reliable, commerce-ready records that strictly adhere to Unilog's delivery formatting.

### 🚀 Features
- **Data Cleansing:** Automatically strips useless placeholders (`-- Unbranded --`, etc.) and drops empty noise from the data.
- **Constrained AI Extraction:** Uses the Gemini model (1.5-flash / 3.6-flash) strictly to extract specific properties (Manufacturer, Brand, Size, Material, Voltages) to build 100% compliant `MOBILE_DESC`, `INVOICE_DESC`, and structured attribute columns.
- **Explainability & Validation Dashboard:** Includes a built-in validation mechanism where the AI rates its own confidence on a 1-100 scale, flags ambiguous items for human review, and explains its extraction reasoning line-by-line.
- **Rich Interactive UI:** Built with Streamlit and custom CSS for a premium dark-mode, glassmorphism aesthetic complete with data visualizations (Confidence Score distributions).

### 🛠️ Tech Stack
- **Frontend:** Streamlit, Pandas Styler, Custom CSS
- **Backend / AI:** Google Generative AI (`gemini-1.5-flash`), Python
- **Data Processing:** Pandas

### 💻 How to Run Locally
1. Clone the repository
2. Set up a virtual environment: `python3 -m venv venv && source venv/bin/activate`
3. Install dependencies: `pip install streamlit pandas google-generativeai`
4. Run the app: `streamlit run app.py`
