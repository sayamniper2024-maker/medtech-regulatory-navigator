
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import google.generativeai as genai # Added for Gemini API
import json # Added for JSON parsing

st.set_page_config(
    page_title="MedTech Regulatory Navigator",
    page_icon="🧬",
    layout="wide"
)

# ── Custom CSS for professional look ────────────────────────────────────────
st.markdown("""
<style>
    .main { padding-top: 1rem; }
    .stMetric { background: #f8f9fa; border-radius: 8px; padding: 12px; }
    .risk-badge {
        display: inline-block; padding: 4px 12px;
        border-radius: 20px; font-size: 13px; font-weight: 600;
    }
    .footer { color: #888; font-size: 12px; text-align: center; margin-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# ── Gemini API Setup ─────────────────────────────────────────────────────────
# For deployment on Streamlit Cloud, use st.secrets. For local, you might use os.environ.
# Make sure GEMINI_API_KEY is set in your Streamlit Cloud secrets.
# See: https://docs.streamlit.io/deploy/streamlit-cloud/connect-to-data-sources/secrets-management
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.warning("GEMINI_API_KEY not found in Streamlit secrets. AI classification may not work.")
    genai.configure(api_key="") # Provide an empty key to avoid errors, but it won't work

model = genai.GenerativeModel("gemini-2.5-flash") # Changed model to gemini-2.5-flash

# ── AI Classification Function (from TpKKp9k00pwg) ───────────────────────────
def ai_classify_device(device_name, device_description=""):
    if not device_name:
        return None

    prompt = f"""You are a senior medical device regulatory affairs expert with
deep knowledge of CDSCO MDR 2017 (India), FDA 21 CFR (USA), and EU MDR 2017/745 (Europe).

Classify this medical device and return ONLY valid JSON, nothing else.

Device: {device_name}
{f"Description: {device_description}" if device_description else ""}

Return exactly this JSON structure:
{{
  "device_name": "{device_name}",
  "intended_use": "brief one-line intended use",
  "cdsco": {{
    "risk_class": "A or B or C or D",
    "license_type": "MD-5 or MD-9 or MD-14",
    "timeline_months": 0,
    "qms_required": "Yes or No",
    "clinical_data_required": "Yes or No",
    "reasoning": "one sentence why this class"
  }},
  "fda": {{
    "risk_class": "I or II or III",
    "pathway": "Exempt or 510(k) or PMA",
    "predicate_needed": "No",
    "timeline_months": 0,
    "clinical_trials_required": "Yes or No",
    "ide_required": "Yes or No",
    "reasoning": "one sentence why this class"
  }},
  "eu": {{
    "risk_class": "I or IIa or IIb or III",
    "notified_body_needed": "Yes or No",
    "timeline_months": 0,
    "technical_file_type": "Basic UDI-DI or Full Tech File",
    "clinical_evaluation_required": "Yes or No",
    "pmcf_required": "Yes or No",
    "reasoning": "one sentence why this class"
  }},
  "confidence": "High or Medium or Low",
  "disclaimer": "any important caveats"
}}
Return ONLY the JSON object, no markdown, no explanation."""

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()

        # Clean markdown if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        return json.loads(raw)
    except Exception as e:
        st.error(f"AI classification failed: {e}. Please check your API key and try again.")
        return None

# ── Helpers ──────────────────────────────────────────────────────────────────
def get_risk_level(risk_class):
    return {"A":"Low","B":"Medium","C":"High","D":"Critical",
            "I":"Low","II":"Medium","III":"Critical",
            "IIa":"Medium","IIb":"High"}.get(risk_class,"Unknown")

def get_risk_color(level):
    return {"Low":"#1D9E75","Medium":"#BA7517",
            "High":"#D85A30","Critical":"#E24B4A"}.get(level,"#888")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/dna-helix.png", width=60)
    st.title("Navigator")
    st.caption("MDR 2017 · FDA 21 CFR · EU MDR 2017/745")
    st.divider()

    st.subheader("Device Input")
    selected_device = st.text_input("Enter Device Name", "Smart Insulin Pen")
    device_description = st.text_area("Optional: Device Description",
                                    "Bluetooth-connected insulin delivery device that tracks doses and syncs with a smartphone app")

    st.subheader("Target Markets")
    show_cdsco = st.checkbox("🇮🇳 India (CDSCO)", value=True)
    show_fda   = st.checkbox("🇺🇸 USA (FDA)",     value=True)
    show_eu    = st.checkbox("🇪🇺 Europe (CE Mark)",value=True)

    st.divider()
    analyse_button = st.button("Analyse Device", type="primary", use_container_width=True)
    st.caption("Enter device details and click Analyse.")

    st.divider()
    st.subheader("About this tool")
    st.caption("""
    Encodes 3 major regulatory frameworks
    into a single decision-support tool.
    Reduces pathway scoping from hours to
    minutes. Built with Python + Streamlit +
    Gemini API.
    """)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("## 🧬 MedTech Regulatory Pathway Navigator")
st.markdown(
    "Instantly identify the optimal regulatory pathway for any medical device "
    "across **CDSCO (India)**, **FDA 510(k)/PMA (USA)**, and **CE Mark (EU MDR)** using AI."
)
st.divider()

# Perform AI classification only when the button is clicked
if analyse_button:
    ai_classification = ai_classify_device(selected_device, device_description)

    if ai_classification:
        st.session_state['ai_classification_result'] = ai_classification
    else:
        st.session_state['ai_classification_result'] = None

# Display results if available in session state
if 'ai_classification_result' in st.session_state and st.session_state['ai_classification_result'] is not None:
    ai_result = st.session_state['ai_classification_result']

    # ── Intended use info box ──────────────────────────────────────────────
    st.info(f"**{ai_result['device_name']}** — Intended use: *{ai_result['intended_use']}*")

    # ── Risk classification ────────────────────────────────────────────────
    st.subheader("Risk Classification")
    col1, col2, col3 = st.columns(3)

    # CDSCO
    cdsco_class = ai_result['cdsco']['risk_class']
    cdsco_lvl   = get_risk_level(cdsco_class)
    cdsco_color = get_risk_color(cdsco_lvl)
    with col1:
        st.metric("CDSCO Class (India)", cdsco_class)
        st.markdown(
            f"<span class='risk-badge' style='background:{cdsco_color}22;color:{cdsco_color}'>{cdsco_lvl} Risk</span>",
            unsafe_allow_html=True
        )

    # FDA
    fda_class = ai_result['fda']['risk_class']
    fda_lvl   = get_risk_level(fda_class)
    fda_color = get_risk_color(fda_lvl)
    with col2:
        st.metric("FDA Class (USA)", fda_class)
        st.markdown(
            f"<span class='risk-badge' style='background:{fda_color}22;color:{fda_color}'>{fda_lvl} Risk</span>",
            unsafe_allow_html=True
        )

    # EU
    eu_class = ai_result['eu']['risk_class']
    eu_lvl   = get_risk_level(eu_class)
    eu_color = get_risk_color(eu_lvl)
    with col3:
        st.metric("EU MDR Class (Europe)", eu_class)
        st.markdown(
            f"<span class='risk-badge' style='background:{eu_color}22;color:{eu_color}'>{eu_lvl} Risk</span>",
            unsafe_allow_html=True
        )

    st.divider()

    # ── Timeline comparison chart ──────────────────────────────────────────
    st.subheader("Approval Timeline Comparison")

    markets, months, colors = [], [], []
    cmap = {"CDSCO (India)":"#1D9E75","FDA (USA)":"#378ADD","CE Mark (EU)":"#D85A30"}

    if show_cdsco:
        markets.append("CDSCO (India)")
        months.append(ai_result['cdsco']['timeline_months'])
        colors.append(cmap["CDSCO (India)"])
    if show_fda:
        markets.append("FDA (USA)")
        months.append(ai_result['fda']['timeline_months'])
        colors.append(cmap["FDA (USA)"])
    if show_eu:
        markets.append("CE Mark (EU)")
        months.append(ai_result['eu']['timeline_months'])
        colors.append(cmap["CE Mark (EU)"])

    if markets:
        fig = go.Figure(go.Bar(
            x=markets, y=months,
            marker_color=colors,
            text=[f"{m} months" for m in months],
            textposition="outside"
        ))
        avg = sum(months) / len(months)
        fig.add_hline(y=avg, line_dash="dot", line_color="#888",
                      annotation_text=f"Avg: {avg:.0f} mo",
                      annotation_position="top right")
        fig.update_layout(
            yaxis_title="Months to approval",
            plot_bgcolor="white", height=380,
            margin=dict(t=30,b=20),
            yaxis=dict(gridcolor="#f0f0f0")
        )
        st.plotly_chart(fig, use_container_width=True)

        fastest = min(zip(markets, months), key=lambda x: x[1])
        slowest = max(zip(markets, months), key=lambda x: x[1])
        c1, c2 = st.columns(2)
        c1.success(f"Fastest entry: **{fastest[0]}** — {fastest[1]} months")
        c2.warning(f"Longest path: **{slowest[0]}** — {slowest[1]} months")

    st.divider()

    # ── Tabbed pathway details ────────────────────────────────────────────
    st.subheader("Detailed Pathway Requirements")

    active_tabs = []
    if show_cdsco: active_tabs.append("🇮🇳 CDSCO")
    if show_fda:   active_tabs.append("🇺🇸 FDA")
    if show_eu:    active_tabs.append("🇪🇺 CE Mark")

    if active_tabs:
        tabs = st.tabs(active_tabs)
        tab_idx = 0

        if show_cdsco:
            with tabs[tab_idx]:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Key Details (AI-derived)**")
                    st.markdown(f"- License type: `{ai_result['cdsco']['license_type']}`")
                    st.markdown(f"- Timeline: **{ai_result['cdsco']['timeline_months']} months**")
                    st.markdown(f"- QMS required: {ai_result['cdsco']['qms_required']}")
                    st.markdown(f"- Clinical data: {ai_result['cdsco']['clinical_data_required']}")
                with c2:
                    st.markdown("**AI Reasoning for Classification**")
                    st.markdown(f"- {ai_result['cdsco']['reasoning']}")
            tab_idx += 1

        if show_fda:
            with tabs[tab_idx]:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Key Details (AI-derived)**")
                    st.markdown(f"- Pathway: `{ai_result['fda']['pathway']}`")
                    st.markdown(f"- Timeline: **{ai_result['fda']['timeline_months']} months**")
                    st.markdown(f"- Predicate needed: {ai_result['fda']['predicate_needed']}")
                    st.markdown(f"- Clinical trials: {ai_result['fda']['clinical_trials_required']}")
                    st.markdown(f"- IDE required: {ai_result['fda']['ide_required']}")
                with c2:
                    st.markdown("**AI Reasoning for Classification**")
                    st.markdown(f"- {ai_result['fda']['reasoning']}")
            tab_idx += 1

        if show_eu:
            with tabs[tab_idx]:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Key Details (AI-derived)**")
                    st.markdown(f"- Tech file: `{ai_result['eu']['technical_file_type']}`")
                    st.markdown(f"- Timeline: **{ai_result['eu']['timeline_months']} months**")
                    st.markdown(f"- Notified body: {ai_result['eu']['notified_body_needed']}")
                    st.markdown(f"- Clinical eval: {ai_result['eu']['clinical_evaluation_required']}")
                    st.markdown(f"- PMCF required: {ai_result['eu']['pmcf_required']}")
                with c2:
                    st.markdown("**AI Reasoning for Classification**")
                    st.markdown(f"- {ai_result['eu']['reasoning']}")

    st.divider()

    # ── Full comparison summary table ──────────────────────────────────────
    st.subheader("Side-by-Side Summary")

    summary_data = {
        "Parameter"      : ["Risk Class","Pathway/License","Timeline (months)",
                             "QMS / ISO 13485","Clinical Data","Notified Body / IDE"],
        "CDSCO (India)"  : [ai_result['cdsco']['risk_class'], ai_result['cdsco']['license_type'],
                             ai_result['cdsco']['timeline_months'], ai_result['cdsco']['qms_required'],
                             ai_result['cdsco']['clinical_data_required'], "N/A"], # AI does not provide direct IDE/NB info for CDSCO
        "FDA (USA)"      : [ai_result['fda']['risk_class'], ai_result['fda']['pathway'],
                             ai_result['fda']['timeline_months'], "Yes (21 CFR 820)", # General FDA requirement
                             ai_result['fda']['clinical_trials_required'], ai_result['fda']['ide_required']],
        "CE Mark (EU)"   : [ai_result['eu']['risk_class'], ai_result['eu']['technical_file_type'],
                             ai_result['eu']['timeline_months'], "Yes (ISO 13485)", # General EU requirement
                             ai_result['eu']['clinical_evaluation_required'], ai_result['eu']['notified_body_needed']]
    }
    st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(
        f"<div class='footer'>AI Confidence: **{ai_result['confidence']}** | "
        f"Disclaimer: {ai_result['disclaimer']} | "
        "Built with Python + Streamlit + Plotly + Gemini API</div>",
        unsafe_allow_html=True
    )
else:
    st.info("Enter a medical device name and description in the sidebar and click 'Analyse Device' to get AI-powered regulatory insights.")

