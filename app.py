
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from groq import Groq
import json, os

st.set_page_config(page_title="MedTech Regulatory Navigator", page_icon="🧬", layout="wide")

# ── Groq client ──────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY)

# ── Session cache — same device never calls API twice ────────────────────────
if "classify_cache" not in st.session_state:
    st.session_state.classify_cache = {}
if "search_history" not in st.session_state:
    st.session_state.search_history = []

# ── Framework config ─────────────────────────────────────────────────────────
FRAMEWORKS = {
    "cdsco"         : {"label": "CDSCO (India)",    "color": "#1D9E75"},
    "fda"           : {"label": "FDA (USA)",         "color": "#378ADD"},
    "eu"            : {"label": "CE Mark (EU)",      "color": "#D85A30"},
    "health_canada" : {"label": "Health Canada",     "color": "#C0392B"},
    "japan"         : {"label": "Japan PMDA",        "color": "#8E44AD"},
    "australia"     : {"label": "Australia TGA",     "color": "#E67E22"},
}

RISK_LEVEL = {
    "A":"Low","B":"Medium","C":"High","D":"Critical",
    "I":"Low","II":"Medium","III":"Critical","IV":"Critical",
    "IIa":"Medium","IIb":"High","AIMD":"Critical"
}
RISK_COLOR = {
    "Low":"#1D9E75","Medium":"#BA7517","High":"#D85A30","Critical":"#E24B4A"
}

# ── AI Classifier ─────────────────────────────────────────────────────────────
def ai_classify_device(device_name, device_description=""):
    cache_key = f"{device_name.lower().strip()}|{device_description.lower().strip()}"
    if cache_key in st.session_state.classify_cache:
        return st.session_state.classify_cache[cache_key]

    prompt = f"""You are a senior medical device regulatory affairs expert.
Classify this device across all 6 frameworks. Return ONLY valid JSON, nothing else.

Device: {device_name}
{f"Description: {device_description}" if device_description else ""}

Return exactly this JSON:
{{
  "device_name": "{device_name}",
  "intended_use": "one line intended use",
  "cdsco": {{
    "risk_class": "A or B or C or D",
    "license_type": "MD-5 or MD-9 or MD-14",
    "timeline_months": 0,
    "qms_required": "Yes or No",
    "clinical_data_required": "Yes or No",
    "reasoning": "cite MDR 2017 schedule rule"
  }},
  "fda": {{
    "risk_class": "I or II or III",
    "pathway": "Exempt or 510(k) or PMA",
    "predicate_needed": "Yes or No",
    "timeline_months": 0,
    "clinical_trials_required": "Yes or No",
    "ide_required": "Yes or No",
    "reasoning": "cite 21 CFR product code"
  }},
  "eu": {{
    "risk_class": "I or IIa or IIb or III",
    "notified_body_needed": "Yes or No",
    "timeline_months": 0,
    "technical_file_type": "Basic UDI-DI or Full Tech File",
    "clinical_evaluation_required": "Yes or No",
    "pmcf_required": "Yes or No",
    "reasoning": "cite EU MDR Annex VIII rule number"
  }},
  "health_canada": {{
    "risk_class": "I or II or III or IV",
    "licence_type": "MDEL only or Device Licence",
    "timeline_months": 0,
    "qms_required": "Yes or No",
    "clinical_data_required": "Yes or No",
    "hpfb_review": "Yes or No",
    "reasoning": "cite Canadian MDR SOR/98-282 rule"
  }},
  "japan": {{
    "risk_class": "I or II or III or IV",
    "approval_type": "Notification or Certification or Approval",
    "dmah_required": "Yes",
    "timeline_months": 0,
    "clinical_trial_required": "Yes or No",
    "jis_standard_required": "Yes or No",
    "reasoning": "cite Yakuji Ho PMD Act rule"
  }},
  "australia": {{
    "risk_class": "I or IIa or IIb or III or AIMD",
    "artg_pathway": "Self-assessment or Conformity assessment",
    "timeline_months": 0,
    "audited_qms_required": "Yes or No",
    "clinical_evidence_required": "Yes or No",
    "conformity_assessment_body": "None or TGA or TGA or Notified Body",
    "reasoning": "cite TGA Therapeutic Goods Regulations 2002 rule"
  }},
  "confidence": "High or Medium or Low",
  "disclaimer": ""
}}

Rules to follow strictly:
- CDSCO: MDR 2017 Schedule 1 (India)
- FDA: 21 CFR Parts 862-892
- EU MDR: Annex VIII Rules 1-22
- Health Canada: SOR/98-282
- Japan: PMD Act classification
- Australia: TGA Regulations 2002
Return ONLY the JSON. No text before or after."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    result = json.loads(raw.strip())
    st.session_state.classify_cache[cache_key] = result
    return result
from fpdf import FPDF
import io

def generate_pdf(data, selected_fws):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    # ── Header ───────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "MedTech Regulatory Pathway Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, f"Device: {data['device_name']}", ln=True, align="C")
    pdf.cell(0, 8, f"Intended use: {data['intended_use']}", ln=True, align="C")
    pdf.cell(0, 6, f"AI Confidence: {data.get('confidence','—')}", ln=True, align="C")
    pdf.ln(6)

    # ── Divider ───────────────────────────────────────────────────────────────
    pdf.set_draw_color(200, 200, 200)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(6)

    fw_labels = {
        "cdsco":"CDSCO (India)", "fda":"FDA (USA)",
        "eu":"CE Mark (EU)", "health_canada":"Health Canada",
        "japan":"Japan PMDA", "australia":"Australia TGA"
    }
    pathway_key = {
        "cdsco":"license_type", "fda":"pathway",
        "eu":"technical_file_type", "health_canada":"licence_type",
        "japan":"approval_type", "australia":"artg_pathway"
    }

    for fw in selected_fws:
        d = data[fw]
        label = fw_labels.get(fw, fw.upper())

        # Framework heading
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(30, 158, 117)
        pdf.cell(0, 9, label, ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 10)

        # Key details table
        fields = [
            ("Risk class",    d.get("risk_class", "—")),
            ("Pathway",       d.get(pathway_key.get(fw,""), "—")),
            ("Timeline",      f"{d.get('timeline_months','—')} months"),
            ("Reasoning",     d.get("reasoning", "—")),
        ]
        for label_f, value in fields:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(45, 7, f"{label_f}:", border=0)
            pdf.set_font("Helvetica", "", 10)
            # Handle long text wrapping
            pdf.multi_cell(0, 7, str(value), border=0)

        pdf.ln(4)
        pdf.set_draw_color(220, 220, 220)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(4)

    # ── Footer ────────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 6,
        "Disclaimer: For educational and scoping purposes only. "
        "Verify with a qualified regulatory affairs professional.",
        ln=True, align="C")

    # Return as bytes
    return bytes(pdf.output())
# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧬 Navigator")
    st.caption("6 global regulatory frameworks · Powered by Groq")
    st.divider()

    # ── Comparison mode toggle ────────────────────────────────────────────────
    compare_mode = st.checkbox("Compare two devices", value=False)

    input_mode = st.radio("Input method",
                          ["Type any device name", "Choose from preset list"])
    if input_mode == "Type any device name":
        device_name = st.text_input("Device 1",
                                    placeholder="e.g. Pacemaker")
        device_desc = st.text_area("Description 1 (optional)", height=60)
        if compare_mode:
            device_name2 = st.text_input("Device 2",
                                         placeholder="e.g. AED Defibrillator")
            device_desc2 = st.text_area("Description 2 (optional)", height=60)
        else:
            device_name2, device_desc2 = "", ""
    else:
        presets = sorted(["Pacemaker","Thermometer","Blood Pressure Monitor",
                   "Pulse Oximeter","ECG Machine","Ventilator",
                   "Surgical Scissors","Infusion Pump","MRI Scanner",
                   "HIV Test Kit","Glucose Meter","Bone Implant"])
        device_name  = st.selectbox("Device 1", presets)
        device_desc  = ""
        device_name2 = st.selectbox("Device 2", presets, index=1) if compare_mode else ""
        device_desc2 = ""

    st.subheader("Target markets")
    cols_sb = st.columns(2)
    checks = {
        "cdsco"         : cols_sb[0].checkbox("IN India",      value=True),
        "fda"           : cols_sb[1].checkbox("US USA",        value=True),
        "eu"            : cols_sb[0].checkbox("EU Europe",     value=True),
        "health_canada" : cols_sb[1].checkbox("CA Canada",     value=True),
        "japan"         : cols_sb[0].checkbox("JP Japan",      value=True),
        "australia"     : cols_sb[1].checkbox("AU Australia",  value=True),
    }
    selected_fws = [fw for fw, checked in checks.items() if checked]

    st.divider()
    analyse = st.button("Analyse Device", type="primary", use_container_width=True)

    # ── Search history ────────────────────────────────────────────────────────
    if st.session_state.search_history:
        st.divider()
        st.subheader("History")
        for i, h in enumerate(reversed(st.session_state.search_history[-5:])):
            if st.button(
                f"{h['device']} — {h['cdsco_class']} / {h['fda_class']} / {h['eu_class']}",
                key=f"hist_{i}",
                use_container_width=True
            ):
                # Reload result from cache — zero API calls
                st.session_state["reload_device"] = h["device"]
                st.rerun()

        # CSV export
        st.divider()
        if len(st.session_state.search_history) > 0:
            import pandas as pd, io
            hist_df = pd.DataFrame([
                {k: v for k, v in h.items() if k != "data"}
                for h in st.session_state.search_history
            ])
            csv = hist_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Export history CSV",
                data=csv,
                file_name="regulatory_history.csv",
                mime="text/csv",
                use_container_width=True
            )

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 🧬 MedTech Regulatory Pathway Navigator")
st.markdown("*AI-powered classification across 6 global regulatory frameworks*")
st.divider()

if analyse and device_name.strip():
    with st.spinner(f"Classifying **{device_name}** across 6 frameworks..."):
        try:
            data = ai_classify_device(device_name.strip(), device_desc.strip())
            # Save to history
        st.session_state.search_history.append({
            "device"     : data["device_name"],
            "confidence" : data.get("confidence","—"),
            "cdsco_class": data["cdsco"]["risk_class"],
            "fda_class"  : data["fda"]["risk_class"],
            "eu_class"   : data["eu"]["risk_class"],
            "fastest"    : sorted_pairs[0][0] if markets else "—",
            "data"       : data
        })
        except Exception as e:
            st.error(f"Classification failed: {e}")
            st.stop()

    # ── Intended use + confidence ────────────────────────────────────────────
    st.info(f"**{data['device_name']}** — {data['intended_use']}")
    conf_colors = {"High":"green","Medium":"orange","Low":"red"}
    conf = data.get("confidence","Medium")
    st.markdown(f"AI confidence: :{conf_colors.get(conf,'orange')}[**{conf}**]"
                + (f"  |  _{data.get('disclaimer')}_" if data.get("disclaimer") else ""))

    # ── Risk classification grid ─────────────────────────────────────────────
    st.subheader("Risk classification")
    cols = st.columns(len(selected_fws))
    for i, fw in enumerate(selected_fws):
        rc  = data[fw].get("risk_class","?")
        lvl = RISK_LEVEL.get(rc,"Unknown")
        clr = RISK_COLOR.get(lvl,"#888")
        with cols[i]:
            st.metric(FRAMEWORKS[fw]["label"], rc)
            st.markdown(
                f"<span style='color:{clr};font-weight:600'>{lvl} Risk</span>",
                unsafe_allow_html=True)
            st.caption(data[fw].get("reasoning",""))

    st.divider()
# ── Radar chart (only in compare mode) ──────────────────────────────────
    if compare_mode and device_name2.strip():
        with st.spinner(f"Classifying {device_name2}..."):
            data2 = ai_classify_device(device_name2.strip(), device_desc2.strip())

        st.subheader("Device Comparison")
        col_a, col_b = st.columns(2)
        col_a.markdown(f"### Device 1: {data['device_name']}")
        col_b.markdown(f"### Device 2: {data2['device_name']}")

        # Radar chart
        risk_score = {"Low":1,"Medium":2,"High":3,"Critical":4,"Unknown":0}
        categories = [FRAMEWORKS[fw]["label"] for fw in selected_fws]
        categories += [categories[0]]  # close the loop

        vals1 = [risk_score.get(RISK_LEVEL.get(data[fw].get("risk_class",""),  "Unknown"), 0) for fw in selected_fws]
        vals2 = [risk_score.get(RISK_LEVEL.get(data2[fw].get("risk_class",""), "Unknown"), 0) for fw in selected_fws]
        vals1 += [vals1[0]]
        vals2 += [vals2[0]]

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=vals1, theta=categories,
            fill="toself", name=data["device_name"],
            line_color="#1D9E75", fillcolor="rgba(29,158,117,0.15)"
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=vals2, theta=categories,
            fill="toself", name=data2["device_name"],
            line_color="#378ADD", fillcolor="rgba(55,138,221,0.15)"
        ))
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True, range=[0,4],
                    tickvals=[1,2,3,4],
                    ticktext=["Low","Med","High","Crit"]
                )
            ),
            showlegend=True,
            height=380,
            margin=dict(t=30,b=30),
            paper_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_radar, use_container_width=True)
        st.caption("Radar chart shows risk level per framework. Larger area = higher overall regulatory burden.")
    # ── Timeline chart ────────────────────────────────────────────────────────
    st.subheader("Approval timeline comparison")
    labels    = [FRAMEWORKS[fw]["label"] for fw in selected_fws]
    timelines = [int(data[fw].get("timeline_months", 0)) for fw in selected_fws]
    colors    = [FRAMEWORKS[fw]["color"]  for fw in selected_fws]

    fig = go.Figure(go.Bar(
        x=labels, y=timelines, marker_color=colors,
        text=[f"{t} mo" for t in timelines], textposition="outside"
    ))
    avg = sum(timelines)/len(timelines) if timelines else 0
    fig.add_hline(y=avg, line_dash="dot", line_color="#888",
                  annotation_text=f"Avg {avg:.0f} mo",
                  annotation_position="top right")
    fig.update_layout(
        yaxis_title="Months to approval",
        plot_bgcolor="white", height=380,
        margin=dict(t=30,b=20),
        yaxis=dict(gridcolor="#f0f0f0")
    )
    st.plotly_chart(fig, use_container_width=True)

    sorted_pairs = sorted(zip(labels, timelines), key=lambda x: x[1])
    c1, c2, c3 = st.columns(3)
    c1.success(f"Fastest: **{sorted_pairs[0][0]}** — {sorted_pairs[0][1]} months")
    c2.info(   f"Median: **{sorted_pairs[len(sorted_pairs)//2][0]}**")
    c3.warning(f"Slowest: **{sorted_pairs[-1][0]}** — {sorted_pairs[-1][1]} months")

    st.divider()
    def show_world_map(data, selected_fws):
    # ISO country codes mapped to our frameworks
    country_map = {
        "cdsco"         : {"code": "IND", "name": "India"},
        "fda"           : {"code": "USA", "name": "USA"},
        "eu"            : {"code": "DEU", "name": "Germany"},  # proxy for EU
        "health_canada" : {"code": "CAN", "name": "Canada"},
        "japan"         : {"code": "JPN", "name": "Japan"},
        "australia"     : {"code": "AUS", "name": "Australia"},
    }

    countries, timelines, labels, texts = [], [], [], []

    for fw in selected_fws:
        c = country_map.get(fw)
        if c:
            t = int(data[fw].get("timeline_months", 0))
            countries.append(c["code"])
            timelines.append(t)
            labels.append(c["name"])
            texts.append(
                f"<b>{c['name']}</b><br>"
                f"Framework: {FRAMEWORKS[fw]['label']}<br>"
                f"Risk class: {data[fw].get('risk_class','—')}<br>"
                f"Timeline: {t} months<br>"
                f"Pathway: {data[fw].get(pathway_key.get(fw,''),'—')}"
            )

    fig = go.Figure(go.Choropleth(
        locations=countries,
        z=timelines,
        text=texts,
        hovertemplate="%{text}<extra></extra>",
        colorscale=[
            [0.0,  "#1D9E75"],
            [0.33, "#BA7517"],
            [0.66, "#D85A30"],
            [1.0,  "#E24B4A"]
        ],
        colorbar=dict(
            title=dict(text="Months", font=dict(size=12)),
            thickness=12,
            len=0.5
        ),
        marker_line_color="white",
        marker_line_width=0.5,
    ))

    fig.update_layout(
        geo=dict(
            showframe=False,
            showcoastlines=True,
            coastlinecolor="#e0e0e0",
            showland=True,
            landcolor="#f5f5f5",
            showocean=True,
            oceancolor="#eaf4fb",
            showlakes=False,
            projection_type="natural earth",
        ),
        margin=dict(l=0, r=0, t=10, b=0),
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig
    # ── World map ─────────────────────────────────────────────────────────────
    st.subheader("Global Market Entry Map")
    st.caption("Colour = approval timeline. Green = fast, Red = long.")
    st.plotly_chart(show_world_map(data, selected_fws),
                    use_container_width=True)

    # ── Tabbed framework details ──────────────────────────────────────────────
    st.subheader("Detailed pathway requirements")
    tabs = st.tabs([FRAMEWORKS[fw]["label"] for fw in selected_fws])

    fw_fields = {
        "cdsco"         : [("License type","license_type"),("Timeline","timeline_months"),
                            ("QMS required","qms_required"),("Clinical data","clinical_data_required")],
        "fda"           : [("Pathway","pathway"),("Timeline","timeline_months"),
                            ("Predicate needed","predicate_needed"),("Clinical trials","clinical_trials_required"),
                            ("IDE required","ide_required")],
        "eu"            : [("Tech file","technical_file_type"),("Timeline","timeline_months"),
                            ("Notified body","notified_body_needed"),("Clinical eval","clinical_evaluation_required"),
                            ("PMCF required","pmcf_required")],
        "health_canada" : [("Licence type","licence_type"),("Timeline","timeline_months"),
                            ("QMS required","qms_required"),("Clinical data","clinical_data_required"),
                            ("HPFB review","hpfb_review")],
        "japan"         : [("Approval type","approval_type"),("Timeline","timeline_months"),
                            ("DMAH required","dmah_required"),("Clinical trial","clinical_trial_required"),
                            ("JIS standard","jis_standard_required")],
        "australia"     : [("ARTG pathway","artg_pathway"),("Timeline","timeline_months"),
                            ("Audited QMS","audited_qms_required"),("Clinical evidence","clinical_evidence_required"),
                            ("CAB","conformity_assessment_body")],
    }

    for tab, fw in zip(tabs, selected_fws):
        with tab:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Key details**")
                for label, field in fw_fields[fw]:
                    val = data[fw].get(field,"—")
                    suffix = " months" if field == "timeline_months" else ""
                    st.markdown(f"- {label}: **{val}{suffix}**")
            with c2:
                st.markdown("**Regulatory reasoning**")
                st.info(data[fw].get("reasoning","—"))
                rc  = data[fw].get("risk_class","?")
                lvl = RISK_LEVEL.get(rc,"Unknown")
                clr = RISK_COLOR.get(lvl,"#888")
                st.markdown(
                    f"<span style='color:{clr};font-weight:600;font-size:15px'>"
                    f"Class {rc} — {lvl} Risk</span>",
                    unsafe_allow_html=True)

    st.divider()

    # ── Summary table ─────────────────────────────────────────────────────────
    st.subheader("Side-by-side summary")
    pathway_key = {"cdsco":"license_type","fda":"pathway","eu":"technical_file_type",
                   "health_canada":"licence_type","japan":"approval_type","australia":"artg_pathway"}
    clin_key    = {"cdsco":"clinical_data_required","fda":"clinical_trials_required",
                   "eu":"clinical_evaluation_required","health_canada":"clinical_data_required",
                   "japan":"clinical_trial_required","australia":"clinical_evidence_required"}

    summary = {"Parameter":["Risk class","Pathway/Licence","Timeline (months)","Clinical data"]}
    for fw in selected_fws:
        summary[FRAMEWORKS[fw]["label"]] = [
            data[fw].get("risk_class","—"),
            data[fw].get(pathway_key[fw],"—"),
            str(data[fw].get("timeline_months","—")),
            data[fw].get(clin_key[fw],"—"),
        ]
    st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)

    st.caption("AI classification: CDSCO MDR 2017 | FDA 21 CFR | EU MDR 2017/745 | "
               "Health Canada SOR/98-282 | Japan PMD Act | Australia TGO 2002. "
               "Verify with a qualified regulatory affairs professional.")

elif analyse and not device_name.strip():
    st.warning("Please enter a device name first.")
else:
    st.markdown("""
    ### How to use
    1. Type any medical device name in the sidebar
    2. Select target markets
    3. Click **Analyse Device**
# ── PDF download button ───────────────────────────────────────────────────
    st.divider()
    st.subheader("Export Report")
    col1, col2 = st.columns([1, 3])
    with col1:
        pdf_bytes = generate_pdf(data, selected_fws)
        st.download_button(
            label="Download PDF Report",
            data=pdf_bytes,
            file_name=f"{data['device_name'].replace(' ','_')}_regulatory_report.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
    with col2:
        st.caption(f"Includes full pathway analysis for {len(selected_fws)} markets. "
                   "Generated instantly from AI classification results.")

    #### 6 frameworks covered
    | Market | Framework | Classes |
    |--------|-----------|---------|
    | India | CDSCO MDR 2017 | A / B / C / D |
    | USA | FDA 21 CFR | I / II / III |
    | Europe | EU MDR 2017/745 | I / IIa / IIb / III |
    | Canada | Health Canada SOR/98-282 | I / II / III / IV |
    | Japan | PMDA Yakuji Ho | I / II / III / IV |
    | Australia | TGA ARTG | I / IIa / IIb / III |

    #### Try these devices
    - Smart insulin pen
    - AI-powered retinal scanner
    - Robotic surgical arm
    - Wearable ECG patch
    - Neural implant for Parkinson tremor
    """)
