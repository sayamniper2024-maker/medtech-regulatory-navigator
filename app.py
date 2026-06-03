
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import google.generativeai as genai
import json, os

st.set_page_config(page_title="MedTech Regulatory Navigator", page_icon="🧬", layout="wide")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# ── Framework config — single source of truth ────────────────────────────────
FRAMEWORKS = {
    "cdsco"         : {"label": "CDSCO (India)",          "flag": "IN", "color": "#1D9E75"},
    "fda"           : {"label": "FDA (USA)",               "flag": "US", "color": "#378ADD"},
    "eu"            : {"label": "CE Mark (EU)",            "flag": "EU", "color": "#D85A30"},
    "health_canada" : {"label": "Health Canada",           "flag": "CA", "color": "#C0392B"},
    "japan"         : {"label": "Japan PMDA",              "flag": "JP", "color": "#8E44AD"},
    "australia"     : {"label": "Australia TGA",           "flag": "AU", "color": "#E67E22"},
}

RISK_LEVEL = {
    "A":"Low","B":"Medium","C":"High","D":"Critical",
    "I":"Low","II":"Medium","III":"Critical","IV":"Critical",
    "IIa":"Medium","IIb":"High","AIMD":"Critical"
}
RISK_COLOR = {
    "Low":"#1D9E75","Medium":"#BA7517","High":"#D85A30","Critical":"#E24B4A"
}

# In-memory cache — persists for the whole session
if "classify_cache" not in st.session_state:
    st.session_state.classify_cache = {}

def ai_classify_device(device_name, device_description=""):
    cache_key = f"{device_name.lower().strip()}_{device_description.lower().strip()}"
    if cache_key in st.session_state.classify_cache:
        return st.session_state.classify_cache[cache_key]
    prompt = f"""You are a senior medical device regulatory affairs expert.
Classify this device across all 6 frameworks. Return ONLY valid JSON.

Device: {device_name}
{f"Description: {device_description}" if device_description else ""}

Return exactly this structure:
{{
  "device_name": "{device_name}",
  "intended_use": "brief intended use",
  "cdsco": {{
    "risk_class": "A/B/C/D", "license_type": "MD-5/MD-9/MD-14",
    "timeline_months": 0, "qms_required": "Yes/No",
    "clinical_data_required": "Yes/No", "reasoning": "cite MDR 2017 rule"
  }},
  "fda": {{
    "risk_class": "I/II/III", "pathway": "Exempt/510(k)/PMA",
    "predicate_needed": "Yes/No", "timeline_months": 0,
    "clinical_trials_required": "Yes/No", "ide_required": "Yes/No",
    "reasoning": "cite 21 CFR product code"
  }},
  "eu": {{
    "risk_class": "I/IIa/IIb/III", "notified_body_needed": "Yes/No",
    "timeline_months": 0, "technical_file_type": "Basic UDI-DI/Full Tech File",
    "clinical_evaluation_required": "Yes/No", "pmcf_required": "Yes/No",
    "reasoning": "cite Annex VIII rule"
  }},
  "health_canada": {{
    "risk_class": "I/II/III/IV", "licence_type": "MDEL only/Device Licence",
    "timeline_months": 0, "qms_required": "Yes/No",
    "clinical_data_required": "Yes/No", "hpfb_review": "Yes/No",
    "reasoning": "cite Canadian MDR rule"
  }},
  "japan": {{
    "risk_class": "I/II/III/IV", "approval_type": "Notification/Certification/Approval",
    "dmah_required": "Yes", "timeline_months": 0,
    "clinical_trial_required": "Yes/No", "jis_standard_required": "Yes/No",
    "reasoning": "cite Yakuji Ho rule"
  }},
  "australia": {{
    "risk_class": "I/IIa/IIb/III/AIMD",
    "artg_pathway": "Self-assessment/Conformity assessment",
    "timeline_months": 0, "audited_qms_required": "Yes/No",
    "clinical_evidence_required": "Yes/No",
    "conformity_assessment_body": "None/TGA/TGA or Notified Body",
    "reasoning": "cite TGA Therapeutic Goods Regulations rule"
  }},
  "confidence": "High/Medium/Low",
  "disclaimer": ""
}}"""
    response = model.generate_content(prompt)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    result = json.loads(raw.strip())
    st.session_state.classify_cache[cache_key] = result
    return result

def get_timeline(data, fw):
    key = "timeline_months"
    return int(data[fw].get(key, 0))

def get_risk(data, fw):
    return data[fw].get("risk_class", "?")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧬 Navigator")
    st.caption("6 global regulatory frameworks")
    st.divider()

    input_mode = st.radio("Input method",
                          ["Type any device name", "Choose from preset list"])
    if input_mode == "Type any device name":
        device_name = st.text_input("Device name",
                                    placeholder="e.g. AI-powered retinal scanner")
        device_desc = st.text_area("Description (optional)", height=80,
                                   placeholder="e.g. Uses deep learning to detect diabetic retinopathy from fundus images")
    else:
        presets = sorted(["Pacemaker","Thermometer","Blood Pressure Monitor",
                   "Pulse Oximeter","ECG Machine","Ventilator",
                   "Surgical Scissors","Infusion Pump","MRI Scanner",
                   "HIV Test Kit","Glucose Meter","Bone Implant"])
        device_name = st.selectbox("Select device", presets)
        device_desc = ""

    st.subheader("Target markets")
    selected_fws = []
    cols_sb = st.columns(2)
    checks = {
        "cdsco"         : cols_sb[0].checkbox("IN India",     value=True),
        "fda"           : cols_sb[1].checkbox("US USA",       value=True),
        "eu"            : cols_sb[0].checkbox("EU Europe",    value=True),
        "health_canada" : cols_sb[1].checkbox("CA Canada",    value=True),
        "japan"         : cols_sb[0].checkbox("JP Japan",     value=True),
        "australia"     : cols_sb[1].checkbox("AU Australia", value=True),
    }
    selected_fws = [fw for fw, checked in checks.items() if checked]

    st.divider()
    analyse = st.button("Analyse Device", type="primary", use_container_width=True)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("## 🧬 MedTech Regulatory Pathway Navigator")
st.markdown("*AI-powered classification across 6 global regulatory frameworks*")
st.divider()

if analyse and device_name.strip():
    with st.spinner(f"Classifying **{device_name}** across 6 frameworks..."):
        try:
            data = ai_classify_device(device_name.strip(), device_desc.strip())
        except Exception as e:
            st.error(f"Classification failed: {e}")
            st.stop()

    st.info(f"**{data['device_name']}** — {data['intended_use']}")
    conf_colors = {"High":"green","Medium":"orange","Low":"red"}
    conf = data.get("confidence","Medium")
    st.markdown(f"AI confidence: :{conf_colors.get(conf,'orange')}[**{conf}**]"
                + (f"  |  _{data.get('disclaimer')}_" if data.get("disclaimer") else ""))

    # ── Risk classification grid ─────────────────────────────────────────────
    st.subheader("Risk classification")
    cols = st.columns(len(selected_fws))
    for i, fw in enumerate(selected_fws):
        rc  = get_risk(data, fw)
        lvl = RISK_LEVEL.get(rc, "Unknown")
        clr = RISK_COLOR.get(lvl, "#888")
        with cols[i]:
            st.metric(FRAMEWORKS[fw]["label"], rc)
            st.markdown(
                f"<span style='color:{clr};font-weight:600'>{lvl} Risk</span>",
                unsafe_allow_html=True
            )
            st.caption(data[fw].get("reasoning",""))

    st.divider()

    # ── Timeline chart ────────────────────────────────────────────────────────
    st.subheader("Approval timeline comparison")
    labels   = [FRAMEWORKS[fw]["label"]  for fw in selected_fws]
    timelines= [get_timeline(data, fw)   for fw in selected_fws]
    colors   = [FRAMEWORKS[fw]["color"]  for fw in selected_fws]

    fig = go.Figure(go.Bar(
        x=labels, y=timelines, marker_color=colors,
        text=[f"{t} mo" for t in timelines], textposition="outside"
    ))
    avg = sum(timelines)/len(timelines) if timelines else 0
    fig.add_hline(y=avg, line_dash="dot", line_color="#888",
                  annotation_text=f"Avg {avg:.0f} mo",
                  annotation_position="top right")
    fig.update_layout(yaxis_title="Months to approval",
                      plot_bgcolor="white", height=380,
                      margin=dict(t=30,b=20),
                      yaxis=dict(gridcolor="#f0f0f0"))
    st.plotly_chart(fig, use_container_width=True)

    sorted_pairs = sorted(zip(labels, timelines), key=lambda x: x[1])
    c1, c2, c3 = st.columns(3)
    c1.success(f"Fastest: **{sorted_pairs[0][0]}** — {sorted_pairs[0][1]} months")
    c2.info(   f"Median:  **{sorted_pairs[len(sorted_pairs)//2][0]}**")
    c3.warning(f"Slowest: **{sorted_pairs[-1][0]}** — {sorted_pairs[-1][1]} months")

    st.divider()

    # ── Tabbed framework details ──────────────────────────────────────────────
    st.subheader("Detailed pathway requirements")
    tab_labels = [FRAMEWORKS[fw]["label"] for fw in selected_fws]
    tabs = st.tabs(tab_labels)

    fw_fields = {
        "cdsco"         : [("License type",      "license_type"),
                            ("Timeline",          "timeline_months"),
                            ("QMS required",      "qms_required"),
                            ("Clinical data",     "clinical_data_required")],
        "fda"           : [("Pathway",            "pathway"),
                            ("Timeline",          "timeline_months"),
                            ("Predicate needed",  "predicate_needed"),
                            ("Clinical trials",   "clinical_trials_required"),
                            ("IDE required",      "ide_required")],
        "eu"            : [("Tech file",          "technical_file_type"),
                            ("Timeline",          "timeline_months"),
                            ("Notified body",     "notified_body_needed"),
                            ("Clinical eval",     "clinical_evaluation_required"),
                            ("PMCF required",     "pmcf_required")],
        "health_canada" : [("Licence type",       "licence_type"),
                            ("Timeline",          "timeline_months"),
                            ("QMS required",      "qms_required"),
                            ("Clinical data",     "clinical_data_required"),
                            ("HPFB review",       "hpfb_review")],
        "japan"         : [("Approval type",      "approval_type"),
                            ("Timeline",          "timeline_months"),
                            ("DMAH required",     "dmah_required"),
                            ("Clinical trial",    "clinical_trial_required"),
                            ("JIS standard",      "jis_standard_required")],
        "australia"     : [("ARTG pathway",       "artg_pathway"),
                            ("Timeline",          "timeline_months"),
                            ("Audited QMS",       "audited_qms_required"),
                            ("Clinical evidence", "clinical_evidence_required"),
                            ("CAB",               "conformity_assessment_body")],
    }

    for tab, fw in zip(tabs, selected_fws):
        with tab:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Key details**")
                for label, field in fw_fields[fw]:
                    val = data[fw].get(field, "—")
                    suffix = " months" if field == "timeline_months" else ""
                    st.markdown(f"- {label}: **{val}{suffix}**")
            with c2:
                st.markdown("**Regulatory reasoning**")
                st.info(data[fw].get("reasoning","—"))
                st.markdown("**Risk class explained**")
                rc  = get_risk(data, fw)
                lvl = RISK_LEVEL.get(rc, "Unknown")
                clr = RISK_COLOR.get(lvl, "#888")
                st.markdown(
                    f"<span style='color:{clr};font-weight:600;font-size:15px'>"
                    f"Class {rc} — {lvl} Risk</span>",
                    unsafe_allow_html=True
                )

    st.divider()

    # ── Summary table ─────────────────────────────────────────────────────────
    st.subheader("Side-by-side summary")
    summary = {"Parameter": ["Risk class","Pathway/Licence","Timeline (months)","QMS required","Clinical data"]}
    pathway_key = {"cdsco":"license_type","fda":"pathway","eu":"technical_file_type",
                   "health_canada":"licence_type","japan":"approval_type","australia":"artg_pathway"}
    qms_key     = {"cdsco":"qms_required","fda":"qms_required","eu":"notified_body_needed",
                   "health_canada":"qms_required","japan":"qms_ordinance_required","australia":"audited_qms_required"}
    clin_key    = {"cdsco":"clinical_data_required","fda":"clinical_trials_required",
                   "eu":"clinical_evaluation_required","health_canada":"clinical_data_required",
                   "japan":"clinical_trial_required","australia":"clinical_evidence_required"}

    for fw in selected_fws:
        summary[FRAMEWORKS[fw]["label"]] = [
            data[fw].get("risk_class","—"),
            data[fw].get(pathway_key[fw],"—"),
            str(data[fw].get("timeline_months","—")),
            data[fw].get(qms_key.get(fw,"qms_required"),"—"),
            data[fw].get(clin_key[fw],"—"),
        ]
    st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)

    st.caption("AI classification based on: CDSCO MDR 2017 | FDA 21 CFR | EU MDR 2017/745 | "
               "Health Canada SOR/98-282 | Japan PMD Act | Australia TGO 2002. "
               "Always verify with a qualified regulatory affairs professional.")

elif analyse and not device_name.strip():
    st.warning("Please enter a device name first.")

else:
    st.markdown("""
    ### How to use
    1. Type any medical device name in the sidebar
    2. Select which markets to analyse
    3. Click **Analyse Device**

    #### 6 frameworks now covered
    | Market | Framework | Classes |
    |--------|-----------|---------|
    | India | CDSCO MDR 2017 | A / B / C / D |
    | USA | FDA 21 CFR | I / II / III |
    | Europe | EU MDR 2017/745 | I / IIa / IIb / III |
    | Canada | Health Canada SOR/98-282 | I / II / III / IV |
    | Japan | PMDA Yakuji Ho | I / II / III / IV |
    | Australia | TGA ARTG | I / IIa / IIb / III |

    #### Try these devices
    - `Smart insulin pen`
    - `AI-powered retinal scanner`
    - `Robotic surgical arm`
    - `Wearable ECG patch`
    - `Neural implant for Parkinson tremor`
    """)
