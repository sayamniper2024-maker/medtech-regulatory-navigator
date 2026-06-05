
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from groq import Groq
from fpdf import FPDF
import json, os

st.set_page_config(page_title="MedTech Regulatory Navigator", page_icon="🧬", layout="wide")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY)

if "classify_cache"  not in st.session_state: st.session_state.classify_cache  = {}
if "search_history"  not in st.session_state: st.session_state.search_history  = []
if "chat_history"    not in st.session_state: st.session_state.chat_history    = []
if "current_device"  not in st.session_state: st.session_state.current_device  = None

FRAMEWORKS = {
    "cdsco"         : {"label":"CDSCO (India)",    "color":"#1D9E75"},
    "fda"           : {"label":"FDA (USA)",         "color":"#378ADD"},
    "eu"            : {"label":"CE Mark (EU)",      "color":"#D85A30"},
    "health_canada" : {"label":"Health Canada",     "color":"#C0392B"},
    "japan"         : {"label":"Japan PMDA",        "color":"#8E44AD"},
    "australia"     : {"label":"Australia TGA",     "color":"#E67E22"},
}
RISK_LEVEL = {
    "A":"Low","B":"Medium","C":"High","D":"Critical",
    "I":"Low","II":"Medium","III":"Critical","IV":"Critical",
    "IIa":"Medium","IIb":"High","AIMD":"Critical"
}
RISK_COLOR = {
    "Low":"#1D9E75","Medium":"#BA7517","High":"#D85A30","Critical":"#E24B4A"
}
PATHWAY_KEY = {
    "cdsco":"license_type","fda":"pathway","eu":"technical_file_type",
    "health_canada":"licence_type","japan":"approval_type","australia":"artg_pathway"
}
CLIN_KEY = {
    "cdsco":"clinical_data_required","fda":"clinical_trials_required",
    "eu":"clinical_evaluation_required","health_canada":"clinical_data_required",
    "japan":"clinical_trial_required","australia":"clinical_evidence_required"
}
COUNTRY_MAP = {
    "cdsco"         : {"code":"IND","name":"India"},
    "fda"           : {"code":"USA","name":"United States"},
    "eu"            : {"code":"DEU","name":"Germany (EU proxy)"},
    "health_canada" : {"code":"CAN","name":"Canada"},
    "japan"         : {"code":"JPN","name":"Japan"},
    "australia"     : {"code":"AUS","name":"Australia"},
}
FW_FIELDS = {
    "cdsco"         : [("License type","license_type"),("Timeline","timeline_months"),
                        ("QMS required","qms_required"),("Clinical data","clinical_data_required")],
    "fda"           : [("Pathway","pathway"),("Timeline","timeline_months"),
                        ("Predicate needed","predicate_needed"),
                        ("Clinical trials","clinical_trials_required"),
                        ("IDE required","ide_required")],
    "eu"            : [("Tech file","technical_file_type"),("Timeline","timeline_months"),
                        ("Notified body","notified_body_needed"),
                        ("Clinical eval","clinical_evaluation_required"),
                        ("PMCF required","pmcf_required")],
    "health_canada" : [("Licence type","licence_type"),("Timeline","timeline_months"),
                        ("QMS required","qms_required"),
                        ("Clinical data","clinical_data_required"),
                        ("HPFB review","hpfb_review")],
    "japan"         : [("Approval type","approval_type"),("Timeline","timeline_months"),
                        ("DMAH required","dmah_required"),
                        ("Clinical trial","clinical_trial_required"),
                        ("JIS standard","jis_standard_required")],
    "australia"     : [("ARTG pathway","artg_pathway"),("Timeline","timeline_months"),
                        ("Audited QMS","audited_qms_required"),
                        ("Clinical evidence","clinical_evidence_required"),
                        ("CAB","conformity_assessment_body")],
}

# ── CRITICAL RULE EXCEPTIONS ──────────────────────────────────────────────────
# These override general rules and are injected directly into the AI prompt.
# Add new exceptions here as you discover misclassifications.
RULE_EXCEPTIONS = """
CRITICAL CLASSIFICATION EXCEPTIONS — these override general rules, apply them first:

EU MDR 2017/745 Annex VIII Special Rules (MUST follow exactly):
- Rule 8: ALL joint replacement implants (total knee replacement TKR, total hip
  replacement THR, shoulder replacement, ankle replacement, femoral stem, tibial
  base plate, acetabular cup, femoral component) → Class III NOT IIb.
  These are NOT general long-term implants — they have a specific Rule 8 exception.
- Rule 8: Spinal disc replacement implants → Class III
- Rule 8: Implantable devices that come into contact with the heart, central
  circulatory system or CNS → Class III
- Rule 7: Active implantable devices (pacemakers, ICDs, cochlear implants,
  deep brain stimulators) → Class III
- Rule 9: Diagnostic imaging devices using ionizing radiation → Class IIb
- Rule 22: Software driving Class III devices → Class III
  Software driving Class IIb devices → Class IIb

FDA 21 CFR Special Rules:
- Total knee replacement systems → Class III, PMA required
- Total hip replacement systems → Class III, PMA required
- Spinal fusion devices → Class III, PMA required
- Left ventricular assist devices (LVAD) → Class III, PMA required
- All pacemakers and ICDs → Class III, PMA required

CDSCO MDR 2017 Schedule 1 Special Rules:
- Joint replacement implants (hip, knee) → Class D
- Cardiac implants (pacemakers, stents) → Class D
- Active implantable devices → Class D
- Long-term implantable devices intended to replace bone or joint → Class D

Health Canada SOR/98-282 Special Rules:
- Joint replacement implants → Class IV
- Active implantable devices → Class IV
- Long-term implantable devices with life-sustaining purpose → Class IV

Japan PMD Act Special Rules:
- Joint replacement implants → Class IV (Specially controlled medical devices)
- Approval required (not certification) for Class IV
- DMAH always required for foreign manufacturers

Australia TGA Special Rules:
- Joint replacement implants → Class III (not IIb)
- Active implantable devices → Class AIMD
- Long-term implantable devices replacing joints → Class III
"""

# ── AI classifier with accurate prompt ───────────────────────────────────────
def ai_classify_device(device_name, device_description=""):
    cache_key = f"{device_name.lower().strip()}|{device_description.lower().strip()}"
    if cache_key in st.session_state.classify_cache:
        return st.session_state.classify_cache[cache_key]

    prompt = f"""You are a senior medical device regulatory affairs expert with
15 years of experience in global device classification.

{RULE_EXCEPTIONS}

GENERAL CLASSIFICATION RULES (apply AFTER checking exceptions above):
- CDSCO MDR 2017 Schedule 1: A=lowest risk, D=highest risk
- FDA 21 CFR: Class I=low, II=medium, III=high. Exempt/510(k)/PMA
- EU MDR 2017/745 Annex VIII: I=lowest, IIa, IIb, III=highest
- Health Canada SOR/98-282: I=lowest, II, III, IV=highest
- Japan PMD Act: I=lowest, II, III, IV=highest. Notification/Certification/Approval
- Australia TGA Regulations 2002: I=lowest, IIa, IIb, III=highest, AIMD

Device to classify: {device_name}
{f"Additional description: {device_description}" if device_description else ""}

Return ONLY this exact JSON structure, nothing else before or after:
{{
  "device_name": "{device_name}",
  "intended_use": "one line clinical intended use",
  "cdsco": {{
    "risk_class": "A or B or C or D",
    "license_type": "MD-5 or MD-9 or MD-14",
    "timeline_months": 0,
    "qms_required": "Yes or No",
    "clinical_data_required": "Yes or No",
    "reasoning": "cite exact MDR 2017 Schedule rule applied",
    "rule_applied": "e.g. Schedule 1 Rule 4.3"
  }},
  "fda": {{
    "risk_class": "I or II or III",
    "pathway": "Exempt or 510(k) or PMA",
    "predicate_needed": "Yes or No",
    "timeline_months": 0,
    "clinical_trials_required": "Yes or No",
    "ide_required": "Yes or No",
    "reasoning": "cite exact 21 CFR product code and classification panel",
    "rule_applied": "e.g. 21 CFR 888.3400"
  }},
  "eu": {{
    "risk_class": "I or IIa or IIb or III",
    "notified_body_needed": "Yes or No",
    "timeline_months": 0,
    "technical_file_type": "Basic UDI-DI or Full Tech File",
    "clinical_evaluation_required": "Yes or No",
    "pmcf_required": "Yes or No",
    "reasoning": "cite exact EU MDR Annex VIII Rule number",
    "rule_applied": "e.g. Annex VIII Rule 8"
  }},
  "health_canada": {{
    "risk_class": "I or II or III or IV",
    "licence_type": "MDEL only or Device Licence",
    "timeline_months": 0,
    "qms_required": "Yes or No",
    "clinical_data_required": "Yes or No",
    "hpfb_review": "Yes or No",
    "reasoning": "cite exact Canadian MDR SOR/98-282 rule",
    "rule_applied": "e.g. Schedule 1 Rule 3.2"
  }},
  "japan": {{
    "risk_class": "I or II or III or IV",
    "approval_type": "Notification or Certification or Approval",
    "dmah_required": "Yes",
    "timeline_months": 0,
    "clinical_trial_required": "Yes or No",
    "jis_standard_required": "Yes or No",
    "reasoning": "cite exact Yakuji Ho / PMD Act classification rule",
    "rule_applied": "e.g. PMD Act Article 2 Class IV"
  }},
  "australia": {{
    "risk_class": "I or IIa or IIb or III or AIMD",
    "artg_pathway": "Self-assessment or Conformity assessment",
    "timeline_months": 0,
    "audited_qms_required": "Yes or No",
    "clinical_evidence_required": "Yes or No",
    "conformity_assessment_body": "None or TGA or TGA or Notified Body",
    "reasoning": "cite exact TGA Therapeutic Goods Regulations 2002 rule",
    "rule_applied": "e.g. Schedule 2 Part 1 Rule 2.6"
  }},
  "confidence": "High or Medium or Low",
  "disclaimer": "note any edge cases or where expert verification is especially important"
}}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":prompt}],
        temperature=0.1
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    result = json.loads(raw.strip())
    st.session_state.classify_cache[cache_key] = result
    return result

# ── Track 3: Regulatory Q&A chatbot ──────────────────────────────────────────
def regulatory_chat(user_question, device_data):
    """
    Context-aware regulatory Q&A.
    Knows the current device classification and answers follow-up questions.
    """
    # Build system context from the classified device
    context_parts = [
        f"Device: {device_data['device_name']}",
        f"Intended use: {device_data['intended_use']}",
    ]
    for fw in ["cdsco","fda","eu","health_canada","japan","australia"]:
        d = device_data.get(fw,{})
        context_parts.append(
            f"{FRAMEWORKS[fw]['label']}: Class {d.get('risk_class','—')} | "
            f"Pathway: {d.get(PATHWAY_KEY.get(fw,''),'—')} | "
            f"Timeline: {d.get('timeline_months','—')} months | "
            f"Rule: {d.get('rule_applied','—')}"
        )
    device_context = "\n".join(context_parts)

    system_prompt = f"""You are a senior regulatory affairs expert specialising in
global medical device regulations. You have deep knowledge of:
- CDSCO MDR 2017 (India) including Schedule 1 classification rules
- FDA 21 CFR Parts 862-892, 510(k) and PMA pathways
- EU MDR 2017/745 including all Annex VIII classification rules
- Health Canada SOR/98-282
- Japan PMD Act (Yakuji Ho) and DMAH requirements
- Australia TGA Therapeutic Goods Regulations 2002
- ISO 13485, ISO 14971, IEC 62304
- Clinical evaluation, PMCF, post-market surveillance

You are currently advising on this specific device that has already been classified:

{device_context}

Answer the user's question concisely and accurately. Always cite the specific
regulatory rule or article when relevant. If the question is outside your
regulatory expertise, say so clearly. Keep answers under 200 words unless
a detailed explanation is genuinely needed."""

    # Build conversation history for context
    messages = [{"role":"system","content":system_prompt}]
    for turn in st.session_state.chat_history[-6:]:  # last 3 exchanges
        messages.append({"role":"user",      "content":turn["question"]})
        messages.append({"role":"assistant", "content":turn["answer"]})
    messages.append({"role":"user","content":user_question})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.2
    )
    return response.choices[0].message.content.strip()

# ── Reusable single-device results block ─────────────────────────────────────
def show_device_results(data, selected_fws, prefix=""):
    conf        = data.get("confidence","Medium")
    conf_colors = {"High":"green","Medium":"orange","Low":"red"}
    disclaimer  = data.get("disclaimer","").strip() or (
        "AI-generated classification. Always verify with a qualified "
        "regulatory affairs professional before use in actual submissions."
    )
    st.info(f"**{data['device_name']}** — {data['intended_use']}")
    st.markdown(
        f"AI confidence: :{conf_colors.get(conf,'orange')}[**{conf}**]  |  _{disclaimer}_"
    )
    st.divider()

    # Risk classification grid with rule cited
    st.subheader("Risk classification")
    risk_cols = st.columns(len(selected_fws))
    for i, fw in enumerate(selected_fws):
        rc  = data[fw].get("risk_class","?")
        lvl = RISK_LEVEL.get(rc,"Unknown")
        clr = RISK_COLOR.get(lvl,"#888")
        with risk_cols[i]:
            st.metric(FRAMEWORKS[fw]["label"], rc)
            st.markdown(
                f"<span style='color:{clr};font-weight:600'>{lvl} Risk</span>",
                unsafe_allow_html=True)
            rule = data[fw].get("rule_applied","")
            if rule:
                st.caption(f"Rule: {rule}")
            st.caption(data[fw].get("reasoning",""))
    st.divider()

    # Timeline bar chart
    st.subheader("Approval timeline comparison")
    b_labels    = [FRAMEWORKS[fw]["label"] for fw in selected_fws]
    b_timelines = [int(data[fw].get("timeline_months",0)) for fw in selected_fws]
    b_colors    = [FRAMEWORKS[fw]["color"] for fw in selected_fws]
    fig_bar = go.Figure(go.Bar(
        x=b_labels, y=b_timelines, marker_color=b_colors,
        text=[f"{t} mo" for t in b_timelines], textposition="outside"
    ))
    avg = sum(b_timelines)/len(b_timelines) if b_timelines else 0
    fig_bar.add_hline(y=avg, line_dash="dot", line_color="#888",
                      annotation_text=f"Avg {avg:.0f} mo",
                      annotation_position="top right")
    fig_bar.update_layout(
        yaxis_title="Months to approval", plot_bgcolor="white",
        height=360, margin=dict(t=30,b=20),
        yaxis=dict(gridcolor="#f0f0f0")
    )
    st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_{prefix}")
    sp = sorted(zip(b_labels, b_timelines), key=lambda x: x[1])
    sc1,sc2,sc3 = st.columns(3)
    sc1.success(f"Fastest: **{sp[0][0]}** — {sp[0][1]} months")
    sc2.info(   f"Median: **{sp[len(sp)//2][0]}**")
    sc3.warning(f"Slowest: **{sp[-1][0]}** — {sp[-1][1]} months")
    st.divider()

    # World map
    st.subheader("Global market entry map")
    st.caption("Colour = approval timeline. Green = fast · Red = long.")
    countries, timelines, hover = [], [], []
    for fw in selected_fws:
        c = COUNTRY_MAP.get(fw)
        if not c: continue
        t  = int(data[fw].get("timeline_months",0))
        rc = data[fw].get("risk_class","—")
        pw = data[fw].get(PATHWAY_KEY.get(fw,""),"—")
        rl = data[fw].get("rule_applied","")
        countries.append(c["code"])
        timelines.append(t)
        hover.append(
            f"<b>{c['name']}</b><br>"
            f"Framework: {FRAMEWORKS[fw]['label']}<br>"
            f"Risk class: {rc}<br>"
            f"Pathway: {pw}<br>"
            f"Rule: {rl}<br>"
            f"Timeline: <b>{t} months</b>"
        )
    if countries:
        fig_map = go.Figure(go.Choropleth(
            locations=countries, z=timelines, text=hover,
            hovertemplate="%{text}<extra></extra>",
            locationmode="ISO-3",
            colorscale=[[0.0,"#1D9E75"],[0.35,"#BA7517"],
                        [0.65,"#D85A30"],[1.0,"#E24B4A"]],
            zmin=min(timelines), zmax=max(timelines),
            colorbar=dict(title=dict(text="Months",font=dict(size=11)),
                          thickness=14,len=0.55,x=1.0),
            marker_line_color="white", marker_line_width=0.8,
        ))
        fig_map.update_layout(
            geo=dict(showframe=False,showcoastlines=True,coastlinecolor="#cccccc",
                     showland=True,landcolor="#f0ede8",showocean=True,
                     oceancolor="#ddeef8",showlakes=True,lakecolor="#ddeef8",
                     showcountries=True,countrycolor="#dddddd",
                     projection_type="natural earth",
                     lataxis_range=[-60,85],lonaxis_range=[-170,180]),
            margin=dict(l=0,r=60,t=20,b=0), height=400,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_map, use_container_width=True, key=f"map_{prefix}")
    st.divider()

    # Tabbed framework details
    st.subheader("Detailed pathway requirements")
    detail_tabs = st.tabs([FRAMEWORKS[fw]["label"] for fw in selected_fws])
    for tab, fw in zip(detail_tabs, selected_fws):
        with tab:
            dc1, dc2 = st.columns(2)
            with dc1:
                st.markdown("**Key details**")
                for lbl, field in FW_FIELDS[fw]:
                    val    = data[fw].get(field,"—")
                    suffix = " months" if field == "timeline_months" else ""
                    st.markdown(f"- {lbl}: **{val}{suffix}**")
                rule = data[fw].get("rule_applied","")
                if rule:
                    st.markdown(f"- Rule applied: **{rule}**")
            with dc2:
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

    # Summary table
    st.subheader("Side-by-side summary")
    summary = {"Parameter":["Risk class","Pathway / Licence",
                             "Timeline (months)","QMS required",
                             "Clinical data","Rule applied"]}
    for fw in selected_fws:
        summary[FRAMEWORKS[fw]["label"]] = [
            data[fw].get("risk_class","—"),
            data[fw].get(PATHWAY_KEY.get(fw,""),"—"),
            str(data[fw].get("timeline_months","—")),
            data[fw].get("qms_required",
            data[fw].get("audited_qms_required","—")),
            data[fw].get(CLIN_KEY[fw],"—"),
            data[fw].get("rule_applied","—"),
        ]
    st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)

# ── Comprehensive PDF ─────────────────────────────────────────────────────────
def generate_pdf(data, selected_fws, data2=None, selected_fws2=None):
    pdf     = FPDF()
    PAGE_W  = 180
    LABEL_W = 55
    VALUE_W = PAGE_W - LABEL_W
    pdf.set_margins(15,15,15)
    pdf.set_auto_page_break(auto=True, margin=15)

    def safe(t):
        return str(t).encode("latin-1",errors="replace").decode("latin-1")

    def section_header(title, color=(30,158,117)):
        pdf.set_font("Helvetica","B",13)
        pdf.set_text_color(*color)
        pdf.cell(PAGE_W,9,safe(title),ln=True)
        pdf.set_text_color(0,0,0)

    def field_row(label, value):
        pdf.set_font("Helvetica","B",9)
        pdf.cell(LABEL_W,6,safe(f"{label}:"),border=0,ln=0)
        pdf.set_font("Helvetica","",9)
        pdf.multi_cell(VALUE_W,6,safe(str(value)),border=0)
        pdf.set_x(15)

    def divider():
        pdf.set_draw_color(220,220,220)
        pdf.line(15,pdf.get_y(),195,pdf.get_y())
        pdf.ln(4)

    def write_device_section(d, fws, device_label=""):
        pdf.set_font("Helvetica","B",11)
        pdf.set_text_color(60,60,60)
        if device_label:
            pdf.cell(PAGE_W,7,safe(device_label),ln=True)
        pdf.set_font("Helvetica","",10)
        pdf.set_text_color(100,100,100)
        pdf.cell(PAGE_W,6,safe(f"Device: {d['device_name']}"),ln=True)
        pdf.cell(PAGE_W,6,safe(f"Intended use: {d['intended_use']}"),ln=True)
        pdf.cell(PAGE_W,6,safe(f"AI Confidence: {d.get('confidence','—')}"),ln=True)
        disc = d.get("disclaimer","").strip() or                "Always verify with a qualified regulatory professional."
        pdf.set_font("Helvetica","I",8)
        pdf.multi_cell(PAGE_W,5,safe(f"Note: {disc}"))
        pdf.ln(3)
        divider()

        # Risk summary table
        section_header("Risk Classification Summary")
        pdf.set_font("Helvetica","B",9)
        col = PAGE_W//4
        pdf.cell(col,6,"Framework",border=1,ln=0)
        pdf.cell(col,6,"Risk Class",border=1,ln=0)
        pdf.cell(col,6,"Risk Level",border=1,ln=0)
        pdf.cell(col,6,"Rule Applied",border=1,ln=True)
        pdf.set_font("Helvetica","",9)
        for fw in fws:
            rc  = d[fw].get("risk_class","—")
            lvl = RISK_LEVEL.get(rc,"Unknown")
            rl  = d[fw].get("rule_applied","—")
            pdf.cell(col,6,safe(FRAMEWORKS[fw]["label"]),border=1,ln=0)
            pdf.cell(col,6,safe(rc),border=1,ln=0)
            pdf.cell(col,6,safe(lvl),border=1,ln=0)
            pdf.cell(col,6,safe(str(rl)[:20]),border=1,ln=True)
        pdf.ln(4)
        divider()

        # Timeline table
        section_header("Approval Timeline Summary")
        pdf.set_font("Helvetica","B",9)
        pdf.cell(PAGE_W//2,6,"Framework",border=1,ln=0)
        pdf.cell(PAGE_W//2,6,"Timeline (months)",border=1,ln=True)
        pdf.set_font("Helvetica","",9)
        all_times = []
        for fw in fws:
            t = int(d[fw].get("timeline_months",0))
            all_times.append((FRAMEWORKS[fw]["label"],t))
            pdf.cell(PAGE_W//2,6,safe(FRAMEWORKS[fw]["label"]),border=1,ln=0)
            pdf.cell(PAGE_W//2,6,safe(f"{t} months"),border=1,ln=True)
        fastest = min(all_times,key=lambda x:x[1])
        slowest = max(all_times,key=lambda x:x[1])
        pdf.set_font("Helvetica","I",8)
        pdf.set_text_color(30,158,117)
        pdf.cell(PAGE_W,5,safe(f"Fastest: {fastest[0]} at {fastest[1]} months"),ln=True)
        pdf.set_text_color(200,80,40)
        pdf.cell(PAGE_W,5,safe(f"Slowest: {slowest[0]} at {slowest[1]} months"),ln=True)
        pdf.set_text_color(0,0,0)
        pdf.ln(3)
        divider()

        # Detailed per-framework
        section_header("Detailed Framework Analysis")
        pdf.ln(2)
        for fw in fws:
            dd = d[fw]
            pdf.set_font("Helvetica","B",11)
            pdf.set_text_color(50,50,50)
            pdf.cell(PAGE_W,7,safe(f"  {FRAMEWORKS[fw]['label']}"),ln=True)
            pdf.set_text_color(0,0,0)
            field_row("Risk class",  dd.get("risk_class","—"))
            field_row("Rule applied",dd.get("rule_applied","—"))
            field_row("Pathway",     dd.get(PATHWAY_KEY.get(fw,""),"—"))
            field_row("Timeline",    f"{dd.get('timeline_months','—')} months")
            for lbl,key in FW_FIELDS[fw]:
                if key not in ["risk_class","timeline_months"]:
                    field_row(lbl, dd.get(key,"—"))
            field_row("Reasoning",   dd.get("reasoning","—"))
            pdf.ln(3)
            pdf.set_draw_color(230,230,230)
            pdf.line(15,pdf.get_y(),195,pdf.get_y())
            pdf.ln(3)

        # Summary table
        divider()
        section_header("Side-by-Side Comparison Table")
        col_w = PAGE_W//(len(fws)+1)
        pdf.set_font("Helvetica","B",8)
        pdf.cell(col_w,6,"Parameter",border=1,ln=0)
        for fw in fws:
            pdf.cell(col_w,6,safe(FRAMEWORKS[fw]["label"][:12]),border=1,ln=0)
        pdf.ln()
        pdf.set_font("Helvetica","",8)
        rows = [
            ("Risk class",   lambda fw: d[fw].get("risk_class","—")),
            ("Rule",         lambda fw: d[fw].get("rule_applied","—")),
            ("Pathway",      lambda fw: d[fw].get(PATHWAY_KEY.get(fw,""),"—")),
            ("Timeline",     lambda fw: f"{d[fw].get('timeline_months','—')} mo"),
            ("QMS",          lambda fw: d[fw].get("qms_required",
                             d[fw].get("audited_qms_required","—"))),
            ("Clinical",     lambda fw: d[fw].get(CLIN_KEY[fw],"—")),
        ]
        for row_label,row_fn in rows:
            pdf.cell(col_w,6,safe(row_label),border=1,ln=0)
            for fw in fws:
                pdf.cell(col_w,6,safe(str(row_fn(fw))[:14]),border=1,ln=0)
            pdf.ln()
        pdf.ln(4)

    # Build PDF
    pdf.add_page()
    pdf.set_font("Helvetica","B",18)
    pdf.cell(PAGE_W,12,"MedTech Regulatory Pathway Report",ln=True,align="C")
    pdf.set_font("Helvetica","",10)
    pdf.set_text_color(120,120,120)
    pdf.cell(PAGE_W,6,"AI-powered analysis across global regulatory frameworks",
             ln=True,align="C")
    pdf.set_text_color(0,0,0)
    pdf.ln(4)
    pdf.set_draw_color(30,158,117)
    pdf.set_line_width(0.8)
    pdf.line(15,pdf.get_y(),195,pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(6)

    if data2 and selected_fws2:
        pdf.set_font("Helvetica","B",14)
        pdf.set_text_color(30,158,117)
        pdf.cell(PAGE_W,8,"DEVICE COMPARISON REPORT",ln=True,align="C")
        pdf.set_text_color(0,0,0)
        pdf.ln(4)
        write_device_section(data,  selected_fws,  "DEVICE 1")
        pdf.add_page()
        write_device_section(data2, selected_fws2, "DEVICE 2")
    else:
        write_device_section(data, selected_fws)

    pdf.set_font("Helvetica","I",8)
    pdf.set_text_color(150,150,150)
    pdf.multi_cell(PAGE_W,5,
        "DISCLAIMER: For educational and preliminary scoping only. "
        "AI-generated based on CDSCO MDR 2017 | FDA 21 CFR | EU MDR 2017/745 | "
        "Health Canada SOR/98-282 | Japan PMD Act | Australia TGO 2002. "
        "Always verify with a qualified regulatory affairs professional.",
        align="C")
    return bytes(pdf.output())

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧬 Navigator")
    st.caption("6 global frameworks · Powered by Groq")
    st.divider()

    compare_mode = st.checkbox("Compare two devices", value=False)
    input_mode   = st.radio("Input method",
                            ["Type any device name","Choose from preset list"])
    presets = sorted(["Pacemaker","Thermometer","Blood Pressure Monitor",
               "Pulse Oximeter","ECG Machine","Ventilator","Surgical Scissors",
               "Infusion Pump","MRI Scanner","HIV Test Kit","Glucose Meter",
               "Bone Implant","Total Knee Replacement","Total Hip Replacement"])

    if input_mode == "Type any device name":
        device_name  = st.text_input("Device name",
                                     placeholder="e.g. Total Knee Replacement")
        device_desc  = st.text_area("Description (optional)", height=60)
        device_name2 = st.text_input("Device 2",
                                     placeholder="e.g. Total Hip Replacement")                         if compare_mode else ""
        device_desc2 = st.text_area("Description 2 (optional)",
                                    height=60) if compare_mode else ""
    else:
        device_name  = st.selectbox("Device 1", presets)
        device_desc  = ""
        device_name2 = st.selectbox("Device 2", presets, index=1)                         if compare_mode else ""
        device_desc2 = ""

    st.subheader("Target markets")
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

    if st.session_state.search_history:
        st.divider()
        st.subheader("History")
        for i,h in enumerate(reversed(st.session_state.search_history[-5:])):
            if st.button(
                f"{h['device']} · {h['cdsco_class']}/{h['fda_class']}/{h['eu_class']}",
                key=f"hist_{i}", use_container_width=True
            ):
                st.session_state["reload_data"] = h["data"]
                st.rerun()
        hist_df   = pd.DataFrame([{k:v for k,v in h.items() if k!="data"}
                                   for h in st.session_state.search_history])
        csv_bytes = hist_df.to_csv(index=False).encode("utf-8")
        st.download_button("Export history CSV", data=csv_bytes,
                           file_name="regulatory_history.csv",
                           mime="text/csv", use_container_width=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 🧬 MedTech Regulatory Pathway Navigator")
st.markdown("*AI-powered classification across 6 global regulatory frameworks*")
st.divider()

# ── Load data ─────────────────────────────────────────────────────────────────
if "reload_data" in st.session_state:
    data         = st.session_state.pop("reload_data")
    data2        = None
    analyse_show = True
elif analyse and device_name.strip():
    analyse_show = True
    with st.spinner(f"Classifying **{device_name}** across 6 frameworks..."):
        try:
            data = ai_classify_device(device_name.strip(), device_desc.strip())
        except Exception as e:
            st.error(f"Classification failed: {e}")
            st.stop()
    data2 = None
    if compare_mode and device_name2.strip():
        with st.spinner(f"Classifying **{device_name2}**..."):
            try:
                data2 = ai_classify_device(device_name2.strip(), device_desc2.strip())
            except Exception as e:
                st.error(f"Device 2 classification failed: {e}")
                data2 = None
    # Clear chat when new device is analysed
    st.session_state.chat_history   = []
    st.session_state.current_device = data
    st.session_state.search_history.append({
        "device"      : data["device_name"],
        "confidence"  : data.get("confidence","—"),
        "cdsco_class" : data["cdsco"]["risk_class"],
        "fda_class"   : data["fda"]["risk_class"],
        "eu_class"    : data["eu"]["risk_class"],
        "data"        : data,
    })
elif analyse and not device_name.strip():
    st.warning("Please enter a device name first.")
    analyse_show = False
    data,data2   = None, None
else:
    analyse_show = False
    data,data2   = None, None

# ── Results ───────────────────────────────────────────────────────────────────
if analyse_show and data:

    if compare_mode and data2:
        st.subheader("Device Comparison")
        dev_tab1, dev_tab2, radar_tab = st.tabs([
            f"Device 1: {data['device_name']}",
            f"Device 2: {data2['device_name']}",
            "Radar comparison"
        ])
        with dev_tab1:
            show_device_results(data, selected_fws, prefix="d1")
        with dev_tab2:
            show_device_results(data2, selected_fws, prefix="d2")
        with radar_tab:
            st.subheader("Risk burden radar chart")
            risk_score = {"Low":1,"Medium":2,"High":3,"Critical":4,"Unknown":0}
            categories = [FRAMEWORKS[fw]["label"] for fw in selected_fws]
            cat_closed = categories + [categories[0]]
            vals1 = [risk_score.get(RISK_LEVEL.get(
                        data[fw].get("risk_class",""),"Unknown"),0)
                     for fw in selected_fws]
            vals2 = [risk_score.get(RISK_LEVEL.get(
                        data2[fw].get("risk_class",""),"Unknown"),0)
                     for fw in selected_fws]
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=vals1+[vals1[0]], theta=cat_closed, fill="toself",
                name=data["device_name"], line_color="#1D9E75",
                fillcolor="rgba(29,158,117,0.2)"
            ))
            fig_radar.add_trace(go.Scatterpolar(
                r=vals2+[vals2[0]], theta=cat_closed, fill="toself",
                name=data2["device_name"], line_color="#378ADD",
                fillcolor="rgba(55,138,221,0.2)"
            ))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True,range=[0,4],
                    tickvals=[1,2,3,4],ticktext=["Low","Med","High","Crit"])),
                showlegend=True,height=450,
                margin=dict(t=50,b=50),
                paper_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_radar,use_container_width=True,key="radar_main")
            st.divider()
            st.subheader("Head-to-head summary")
            h2h = {"Framework":[],"D1 class":[],"D1 timeline":[],
                   "D2 class":[],"D2 timeline":[],"Faster entry":[]}
            for fw in selected_fws:
                t1 = int(data[fw].get("timeline_months",0))
                t2 = int(data2[fw].get("timeline_months",0))
                h2h["Framework"].append(FRAMEWORKS[fw]["label"])
                h2h["D1 class"].append(data[fw].get("risk_class","—"))
                h2h["D1 timeline"].append(f"{t1} mo")
                h2h["D2 class"].append(data2[fw].get("risk_class","—"))
                h2h["D2 timeline"].append(f"{t2} mo")
                h2h["Faster entry"].append(
                    data["device_name"] if t1<=t2 else data2["device_name"])
            st.dataframe(pd.DataFrame(h2h),use_container_width=True,hide_index=True)

        st.divider()
        ex1,ex2 = st.columns([1,3])
        with ex1:
            pdf_bytes = generate_pdf(data,selected_fws,data2,selected_fws)
            st.download_button(
                "Download comparison PDF", data=pdf_bytes,
                file_name=f"comparison_{data['device_name'].replace(' ','_')}_vs_"
                          f"{data2['device_name'].replace(' ','_')}.pdf",
                mime="application/pdf", type="primary",
                use_container_width=True
            )
        with ex2:
            st.caption("Full comparison — both devices, all frameworks, all details.")

    else:
        # Single device results
        show_device_results(data, selected_fws, prefix="single")
        ex1,ex2 = st.columns([1,3])
        with ex1:
            pdf_bytes = generate_pdf(data, selected_fws)
            st.download_button(
                "Download PDF", data=pdf_bytes,
                file_name=f"{data['device_name'].replace(' ','_')}_regulatory_report.pdf",
                mime="application/pdf", type="primary",
                use_container_width=True
            )
        with ex2:
            st.caption(f"Full pathway analysis — {len(selected_fws)} markets, all details.")

    st.divider()

    # ── Track 3: Regulatory Q&A Chatbot ──────────────────────────────────────
    st.subheader("Ask the regulatory AI")
    st.caption(f"Context-aware Q&A about **{data['device_name']}** — "
               "ask any follow-up regulatory question")

    # Suggested questions
    suggestions = [
        "What documents do I need to prepare first?",
        "Which market should I enter first and why?",
        "What is the estimated total regulatory cost?",
        "What clinical evidence is needed for this device?",
        "What are the ISO standards I need to comply with?",
        "Explain the submission process step by step for the fastest market",
    ]
    st.markdown("**Quick questions:**")
    sug_cols = st.columns(3)
    for idx, sug in enumerate(suggestions):
        if sug_cols[idx % 3].button(sug, key=f"sug_{idx}",
                                     use_container_width=True):
            st.session_state["pending_question"] = sug

    # Chat input
    user_q = st.chat_input("Ask a regulatory question about this device...")

    # Handle suggested question click
    if "pending_question" in st.session_state:
        user_q = st.session_state.pop("pending_question")

    # Process question
    if user_q and st.session_state.current_device:
        with st.spinner("Consulting regulatory knowledge base..."):
            try:
                answer = regulatory_chat(user_q, st.session_state.current_device)
                st.session_state.chat_history.append({
                    "question": user_q,
                    "answer"  : answer
                })
            except Exception as e:
                st.error(f"Chat error: {e}")

    # Display chat history — most recent first
    if st.session_state.chat_history:
        for turn in reversed(st.session_state.chat_history):
            with st.chat_message("user"):
                st.write(turn["question"])
            with st.chat_message("assistant"):
                st.write(turn["answer"])

        if st.button("Clear chat", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()

    st.divider()
    st.warning(
        "**Disclaimer:** For educational and preliminary scoping purposes only. "
        "AI-generated based on CDSCO MDR 2017 | FDA 21 CFR | EU MDR 2017/745 | "
        "Health Canada SOR/98-282 | Japan PMD Act | Australia TGO 2002. "
        "Always verify with a qualified regulatory affairs professional.",
        icon="⚠️"
    )

else:
    st.markdown("""
    ### How to use
    1. Type any medical device name in the sidebar
    2. Select your target markets
    3. Click **Analyse Device**
    4. Ask follow-up questions in the Q&A panel below results

    #### 6 frameworks covered
    | Market | Framework | Classes |
    |--------|-----------|---------|
    | 🇮🇳 India | CDSCO MDR 2017 | A / B / C / D |
    | 🇺🇸 USA | FDA 21 CFR | I / II / III |
    | 🇪🇺 Europe | EU MDR 2017/745 | I / IIa / IIb / III |
    | 🇨🇦 Canada | Health Canada SOR/98-282 | I / II / III / IV |
    | 🇯🇵 Japan | PMDA Yakuji Ho | I / II / III / IV |
    | 🇦🇺 Australia | TGA ARTG | I / IIa / IIb / III |

    #### Try these devices
    - Total Knee Replacement · Total Hip Replacement
    - Smart insulin pen · AI retinal scanner
    - Robotic surgical arm · Neural implant for Parkinson tremor
    """)
