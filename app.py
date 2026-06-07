
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from groq import Groq
from fpdf import FPDF
import json, os

st.set_page_config(page_title="MedTech Regulatory Navigator", page_icon="🧬", layout="wide")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY)

# ── Session state ─────────────────────────────────────────────────────────────
for _k, _v in {
    "classify_cache"     : {},
    "search_history"     : [],
    "chat_history"       : [],
    "current_device"     : None,
    "chat_input_counter" : 0,
    "_queued_question"   : None,
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Constants ─────────────────────────────────────────────────────────────────
FRAMEWORKS = {
    "cdsco"         : {"label":"CDSCO (India)",          "color":"#1D9E75"},
    "fda"           : {"label":"FDA (USA)",               "color":"#378ADD"},
    "eu"            : {"label":"CE Mark (EU)",            "color":"#D85A30"},
    "health_canada" : {"label":"Health Canada",           "color":"#C0392B"},
    "japan"         : {"label":"Japan PMDA",              "color":"#8E44AD"},
    "australia"     : {"label":"Australia TGA",           "color":"#E67E22"},
    "russia"        : {"label":"Russia Roszdravnadzor",   "color":"#2C3E8C"},
}
RISK_LEVEL = {
    "A":"Low","B":"Medium","C":"High","D":"Critical",
    "I":"Low","II":"Medium","III":"Critical","IV":"Critical",
    "IIa":"Medium","IIb":"High","AIMD":"Critical",
    "1":"Low","2a":"Medium","2b":"High","3":"Critical",
}
RISK_COLOR = {
    "Low":"#1D9E75","Medium":"#BA7517","High":"#D85A30","Critical":"#E24B4A"
}
PATHWAY_KEY = {
    "cdsco"         : "license_type",
    "fda"           : "pathway",
    "eu"            : "technical_file_type",
    "health_canada" : "licence_type",
    "japan"         : "approval_type",
    "australia"     : "artg_pathway",
    "russia"        : "registration_type",
}
CLIN_KEY = {
    "cdsco"         : "clinical_data_required",
    "fda"           : "clinical_trials_required",
    "eu"            : "clinical_evaluation_required",
    "health_canada" : "clinical_data_required",
    "japan"         : "clinical_trial_required",
    "australia"     : "clinical_evidence_required",
    "russia"        : "clinical_investigation_required",
}
COUNTRY_MAP = {
    "cdsco"         : {"code":"IND","name":"India"},
    "fda"           : {"code":"USA","name":"United States"},
    "eu"            : {"code":"DEU","name":"Germany (EU proxy)"},
    "health_canada" : {"code":"CAN","name":"Canada"},
    "japan"         : {"code":"JPN","name":"Japan"},
    "australia"     : {"code":"AUS","name":"Australia"},
    "russia"        : {"code":"RUS","name":"Russia"},
}
FW_FIELDS = {
    "cdsco"         : [("License type","license_type"),("Timeline","timeline_months"),
                        ("QMS required","qms_required"),
                        ("Clinical data","clinical_data_required")],
    "fda"           : [("Pathway","pathway"),("Timeline","timeline_months"),
                        ("Predicate needed","predicate_needed"),
                        ("Clinical trials","clinical_trials_required"),
                        ("IDE required","ide_required")],
    "eu"            : [("Tech file","technical_file_type"),
                        ("Timeline","timeline_months"),
                        ("Notified body","notified_body_needed"),
                        ("Clinical eval","clinical_evaluation_required"),
                        ("PMCF required","pmcf_required")],
    "health_canada" : [("Licence type","licence_type"),
                        ("Timeline","timeline_months"),
                        ("QMS required","qms_required"),
                        ("Clinical data","clinical_data_required"),
                        ("HPFB review","hpfb_review")],
    "japan"         : [("Approval type","approval_type"),
                        ("Timeline","timeline_months"),
                        ("DMAH required","dmah_required"),
                        ("Clinical trial","clinical_trial_required"),
                        ("JIS standard","jis_standard_required")],
    "australia"     : [("ARTG pathway","artg_pathway"),
                        ("Timeline","timeline_months"),
                        ("Audited QMS","audited_qms_required"),
                        ("Clinical evidence","clinical_evidence_required"),
                        ("CAB","conformity_assessment_body")],
    "russia"        : [("Registration type","registration_type"),
                        ("Timeline","timeline_months"),
                        ("ISO 13485 required","iso_13485_required"),
                        ("Local testing required","local_testing_required"),
                        ("Clinical investigation","clinical_investigation_required"),
                        ("Site inspection","site_inspection_required"),
                        ("RU REP required","ru_rep_required")],
}

RULE_EXCEPTIONS = """
=== CRITICAL CLASSIFICATION EXCEPTIONS — CHECK THESE FIRST ===

EU MDR 2017/745 Annex VIII Rule 8 → Class III (NOT IIb):
- Coronary stents, cardiac stents, drug-eluting stents → Class III
- Any implantable device contacting heart or central circulatory system → Class III
- Total knee replacement (TKR), total hip replacement (THR) → Class III
- All joint replacement implants → Class III
- Pacemakers, ICDs → Class III (Rule 7 active implantable)
- LVAD, mechanical heart valves → Class III

FDA 21 CFR correct citations:
- Cardiovascular = Part 870 (NOT Part 882 which is neurology)
- Coronary stents → Class III, PMA, 21 CFR 870.3945
- Joint replacements → Class III, PMA, 21 CFR 888.3400/888.3320

Russia Roszdravnadzor (Government Decree No.1684, in force March 2025):
- Classes: 1 (lowest), 2a, 2b, 3 (highest)
- All devices need RU REP (Authorised Representative in Russia)
- All devices need local laboratory testing in accredited Russian labs
- Class 1 and 2a: simplified review, up to 90 working days
- Class 2b and 3: full review, up to 160 working days, clinical investigation required
- From Jan 2024: mandatory site inspection for Class 2a sterile, 2b and 3
- From Jan 2027: registration only via EAEU system
- Registration certificate (RZN number) issued by Roszdravnadzor
- ISO 13485 mandatory for Class 2a sterile, 2b and 3
- Coronary stents → Class 3
- Joint replacements → Class 3
- Pacemakers → Class 3
- Active implantables → Class 3

CDSCO: cardiac implants + joint replacements → Class D
Health Canada: cardiac implants + joint replacements → Class IV
Japan: cardiac implants + joint replacements → Class IV, Approval, DMAH required
Australia: cardiac implants + joint replacements → Class III
"""

KNOWN_CORRECTIONS = [
    {
        "keywords":["coronary stent","cardiac stent","drug-eluting stent",
                    "drug eluting stent","bare metal stent","bare-metal stent",
                    "intravascular stent","coronary artery stent"],
        "corrections":{
            "fda"  :{"risk_class":"III","pathway":"PMA",
                     "rule_applied":"21 CFR 870.3945",
                     "clinical_trials_required":"Yes","ide_required":"Yes",
                     "predicate_needed":"No","timeline_months":36},
            "eu"   :{"risk_class":"III","notified_body_needed":"Yes",
                     "rule_applied":"EU MDR Annex VIII Rule 8",
                     "clinical_evaluation_required":"Yes","pmcf_required":"Yes",
                     "technical_file_type":"Full Tech File","timeline_months":24},
            "cdsco":{"risk_class":"D","license_type":"MD-14",
                     "rule_applied":"MDR 2017 Schedule 1",
                     "clinical_data_required":"Yes","timeline_months":18},
            "health_canada":{"risk_class":"IV","licence_type":"Device Licence",
                             "rule_applied":"SOR/98-282","timeline_months":18},
            "japan":{"risk_class":"IV","approval_type":"Approval",
                     "rule_applied":"PMD Act Class IV",
                     "dmah_required":"Yes","timeline_months":36},
            "australia":{"risk_class":"III","artg_pathway":"Conformity assessment",
                         "rule_applied":"TGA Schedule 2","timeline_months":20},
            "russia":{"risk_class":"3","registration_type":"Full registration (RZN)",
                      "rule_applied":"Decree No.1684 Class 3",
                      "clinical_investigation_required":"Yes",
                      "iso_13485_required":"Yes","local_testing_required":"Yes",
                      "site_inspection_required":"Yes","ru_rep_required":"Yes",
                      "timeline_months":24},
        },
        "note":"Coronary/cardiac stents contact central circulatory system — "
               "escalated to highest class in all frameworks."
    },
    {
        "keywords":["total knee","tkr","total hip","thr","hip replacement",
                    "knee replacement","joint replacement","femoral stem",
                    "acetabular cup","tibial base plate"],
        "corrections":{
            "fda"  :{"risk_class":"III","pathway":"PMA","predicate_needed":"No",
                     "clinical_trials_required":"Yes","ide_required":"Yes",
                     "rule_applied":"21 CFR 888.3400/888.3320","timeline_months":36},
            "eu"   :{"risk_class":"III","notified_body_needed":"Yes",
                     "rule_applied":"EU MDR Annex VIII Rule 8",
                     "clinical_evaluation_required":"Yes","pmcf_required":"Yes",
                     "technical_file_type":"Full Tech File","timeline_months":24},
            "cdsco":{"risk_class":"D","license_type":"MD-14",
                     "rule_applied":"MDR 2017 Schedule 1","timeline_months":18},
            "health_canada":{"risk_class":"IV","licence_type":"Device Licence",
                             "rule_applied":"SOR/98-282","timeline_months":18},
            "japan":{"risk_class":"IV","approval_type":"Approval",
                     "rule_applied":"PMD Act Class IV",
                     "dmah_required":"Yes","timeline_months":36},
            "australia":{"risk_class":"III","artg_pathway":"Conformity assessment",
                         "rule_applied":"TGA Schedule 2","timeline_months":20},
            "russia":{"risk_class":"3","registration_type":"Full registration (RZN)",
                      "rule_applied":"Decree No.1684 Class 3",
                      "clinical_investigation_required":"Yes",
                      "iso_13485_required":"Yes","local_testing_required":"Yes",
                      "site_inspection_required":"Yes","ru_rep_required":"Yes",
                      "timeline_months":24},
        },
        "note":"Joint replacements are Class III/3 in all major frameworks."
    },
]

def validate_and_correct(result):
    device_lower = result.get("device_name","").lower()
    corrections_made = []
    for rule in KNOWN_CORRECTIONS:
        if not any(kw in device_lower for kw in rule["keywords"]):
            continue
        for fw, overrides in rule["corrections"].items():
            if fw not in result: continue
            fw_fixes = []
            for field, correct_val in overrides.items():
                if str(result[fw].get(field,"")) != str(correct_val):
                    result[fw][field] = correct_val
                    fw_fixes.append(field)
            if fw_fixes:
                corrections_made.append(
                    f"**{FRAMEWORKS[fw]['label']}**: corrected {', '.join(fw_fixes)}"
                )
        if corrections_made:
            result["_correction_note"] = rule["note"]
            result["_corrections"]     = corrections_made
            result["confidence"]       = "High"
        break
    return result

# ── AI classifier ─────────────────────────────────────────────────────────────
def ai_classify_device(device_name, device_description=""):
    cache_key = f"{device_name.lower().strip()}|{device_description.lower().strip()}"
    if cache_key in st.session_state.classify_cache:
        return st.session_state.classify_cache[cache_key]

    prompt = f"""You are a senior medical device regulatory affairs expert.
{RULE_EXCEPTIONS}
Classify this device across ALL 7 frameworks. Return ONLY valid JSON, nothing else.
Device: {device_name}
{f"Description: {device_description}" if device_description else ""}

Return exactly this JSON structure:
{{
  "device_name":"{device_name}",
  "intended_use":"one line clinical intended use",
  "cdsco":{{"risk_class":"A/B/C/D","license_type":"MD-5/MD-9/MD-14",
    "timeline_months":0,"qms_required":"Yes/No","clinical_data_required":"Yes/No",
    "reasoning":"cite MDR 2017 rule","rule_applied":"Schedule rule"}},
  "fda":{{"risk_class":"I/II/III","pathway":"Exempt/510(k)/PMA",
    "predicate_needed":"Yes/No","timeline_months":0,
    "clinical_trials_required":"Yes/No","ide_required":"Yes/No",
    "reasoning":"cite 21 CFR part","rule_applied":"21 CFR section"}},
  "eu":{{"risk_class":"I/IIa/IIb/III","notified_body_needed":"Yes/No",
    "timeline_months":0,"technical_file_type":"Basic UDI-DI/Full Tech File",
    "clinical_evaluation_required":"Yes/No","pmcf_required":"Yes/No",
    "reasoning":"cite Annex VIII rule","rule_applied":"Rule number"}},
  "health_canada":{{"risk_class":"I/II/III/IV",
    "licence_type":"MDEL only/Device Licence",
    "timeline_months":0,"qms_required":"Yes/No","clinical_data_required":"Yes/No",
    "hpfb_review":"Yes/No","reasoning":"cite SOR/98-282","rule_applied":"SOR rule"}},
  "japan":{{"risk_class":"I/II/III/IV",
    "approval_type":"Notification/Certification/Approval",
    "dmah_required":"Yes","timeline_months":0,
    "clinical_trial_required":"Yes/No","jis_standard_required":"Yes/No",
    "reasoning":"cite PMD Act","rule_applied":"PMD Act class"}},
  "australia":{{"risk_class":"I/IIa/IIb/III/AIMD",
    "artg_pathway":"Self-assessment/Conformity assessment",
    "timeline_months":0,"audited_qms_required":"Yes/No",
    "clinical_evidence_required":"Yes/No",
    "conformity_assessment_body":"None/TGA/TGA or Notified Body",
    "reasoning":"cite TGA rule","rule_applied":"TGA Schedule rule"}},
  "russia":{{"risk_class":"1/2a/2b/3",
    "registration_type":"Simplified registration (RZN)/Full registration (RZN)/EAEU registration",
    "timeline_months":0,
    "iso_13485_required":"Yes/No",
    "local_testing_required":"Yes",
    "clinical_investigation_required":"Yes/No",
    "site_inspection_required":"Yes/No",
    "ru_rep_required":"Yes",
    "reasoning":"cite Decree No.1684 or Federal Law 323 rule",
    "rule_applied":"Decree No.1684 class"}},
  "confidence":"High/Medium/Low",
  "disclaimer":""
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
    result = validate_and_correct(result)
    st.session_state.classify_cache[cache_key] = result
    return result

# ── Chatbot ───────────────────────────────────────────────────────────────────
def regulatory_chat(question, device_data):
    context_lines = [
        f"Device: {device_data.get('device_name','Unknown')}",
        f"Intended use: {device_data.get('intended_use','—')}",
        "Classification results:",
    ]
    for fw in list(FRAMEWORKS.keys()):
        d = device_data.get(fw,{})
        if d:
            context_lines.append(
                f"  {FRAMEWORKS[fw]['label']}: "
                f"Class {d.get('risk_class','—')} | "
                f"Pathway: {d.get(PATHWAY_KEY.get(fw,''),'—')} | "
                f"{d.get('timeline_months','—')} months | "
                f"Rule: {d.get('rule_applied','—')}"
            )
    system_msg = (
        "You are a senior regulatory affairs expert for global medical devices "
        "with deep knowledge of CDSCO MDR 2017, FDA 21 CFR, EU MDR 2017/745, "
        "Health Canada SOR/98-282, Japan PMD Act, Australia TGA, "
        "Russia Roszdravnadzor (Decree No.1684 / Federal Law 323), "
        "ISO 13485, ISO 14971, IEC 62304, EAEU regulations.\n\n"
        "Device classification context:\n"
        + "\n".join(context_lines)
        + "\n\nAnswer accurately and concisely. "
        "Always cite specific regulatory rules and article numbers. "
        "Keep answers under 300 words unless a step-by-step is needed."
    )
    messages = [{"role":"system","content":system_msg}]
    for turn in st.session_state.chat_history[-6:]:
        messages.append({"role":"user",      "content":turn["question"]})
        messages.append({"role":"assistant", "content":turn["answer"]})
    messages.append({"role":"user","content":question})
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.2,
        max_tokens=700,
    )
    return response.choices[0].message.content.strip()

# ── World map ─────────────────────────────────────────────────────────────────
def build_world_map(data, selected_fws, prefix=""):
    countries, timelines, hover = [], [], []
    for fw in selected_fws:
        c = COUNTRY_MAP.get(fw)
        if not c: continue
        t  = int(data[fw].get("timeline_months",0))
        rc = data[fw].get("risk_class","—")
        pw = data[fw].get(PATHWAY_KEY.get(fw,""),"—")
        rl = data[fw].get("rule_applied","—")
        countries.append(c["code"])
        timelines.append(t)
        hover.append(
            f"<b>{c['name']}</b><br>"
            f"Framework: {FRAMEWORKS[fw]['label']}<br>"
            f"Risk class: {rc}<br>Pathway: {pw}<br>"
            f"Rule: {rl}<br>Timeline: <b>{t} months</b>"
        )
    if not countries: return None
    fig = go.Figure(go.Choropleth(
        locations=countries, z=timelines, text=hover,
        hovertemplate="%{text}<extra></extra>",
        locationmode="ISO-3",
        colorscale=[[0.0,"#1D9E75"],[0.35,"#BA7517"],
                    [0.65,"#D85A30"],[1.0,"#E24B4A"]],
        zmin=min(timelines), zmax=max(timelines),
        colorbar=dict(title=dict(text="Months",font=dict(size=11)),
                      thickness=15,len=0.6,x=1.0),
        marker_line_color="white",marker_line_width=0.8,
    ))
    fig.update_layout(
        geo=dict(showframe=False,showcoastlines=True,coastlinecolor="#bbbbbb",
                 showland=True,landcolor="#f5f3ef",showocean=True,
                 oceancolor="#d0e8f5",showlakes=True,lakecolor="#d0e8f5",
                 showcountries=True,countrycolor="#cccccc",
                 projection_type="natural earth",bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=0,r=90,t=20,b=10),height=440,
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        dragmode="pan",
    )
    return fig

# ── Single device results ─────────────────────────────────────────────────────
def show_device_results(data, selected_fws, prefix=""):
    conf        = data.get("confidence","Medium")
    conf_colors = {"High":"green","Medium":"orange","Low":"red"}
    disclaimer  = data.get("disclaimer","").strip() or (
        "AI-generated classification. Always verify with a qualified "
        "regulatory affairs professional before actual submissions."
    )
    st.info(f"**{data['device_name']}** — {data['intended_use']}")
    st.markdown(
        f"AI confidence: :{conf_colors.get(conf,'orange')}[**{conf}**]  "
        f"|  _{disclaimer}_"
    )
    if data.get("_corrections"):
        with st.expander("⚠️ Classification corrections applied", expanded=True):
            st.warning(data.get("_correction_note",""))
            for c in data["_corrections"]:
                st.markdown(f"- {c}")
    st.divider()

    st.subheader("Risk classification")
    risk_cols = st.columns(len(selected_fws))
    for i,fw in enumerate(selected_fws):
        rc  = data[fw].get("risk_class","?")
        lvl = RISK_LEVEL.get(rc,"Unknown")
        clr = RISK_COLOR.get(lvl,"#888")
        with risk_cols[i]:
            st.metric(FRAMEWORKS[fw]["label"],rc)
            st.markdown(
                f"<span style='color:{clr};font-weight:600'>{lvl} Risk</span>",
                unsafe_allow_html=True)
            rule = data[fw].get("rule_applied","")
            if rule: st.caption(f"Rule: {rule}")
            st.caption(data[fw].get("reasoning",""))
    st.divider()

    st.subheader("Approval timeline comparison")
    b_labels    = [FRAMEWORKS[fw]["label"] for fw in selected_fws]
    b_timelines = [int(data[fw].get("timeline_months",0)) for fw in selected_fws]
    b_colors    = [FRAMEWORKS[fw]["color"] for fw in selected_fws]
    fig_bar = go.Figure(go.Bar(
        x=b_labels,y=b_timelines,marker_color=b_colors,
        text=[f"{t} mo" for t in b_timelines],textposition="outside"
    ))
    avg = sum(b_timelines)/len(b_timelines) if b_timelines else 0
    fig_bar.add_hline(y=avg,line_dash="dot",line_color="#888",
                      annotation_text=f"Avg {avg:.0f} mo",
                      annotation_position="top right")
    fig_bar.update_layout(
        yaxis_title="Months to approval",plot_bgcolor="white",
        height=380,margin=dict(t=30,b=20),
        yaxis=dict(gridcolor="#f0f0f0")
    )
    st.plotly_chart(fig_bar,use_container_width=True,key=f"bar_{prefix}")
    sp = sorted(zip(b_labels,b_timelines),key=lambda x:x[1])
    sc1,sc2,sc3 = st.columns(3)
    sc1.success(f"Fastest: **{sp[0][0]}** — {sp[0][1]} months")
    sc2.info(   f"Median: **{sp[len(sp)//2][0]}**")
    sc3.warning(f"Slowest: **{sp[-1][0]}** — {sp[-1][1]} months")
    st.divider()

    st.subheader("Global market entry map")
    st.caption("Hover over highlighted countries for full details. Green = fast · Red = long.")
    fig_map = build_world_map(data,selected_fws,prefix=prefix)
    if fig_map:
        st.plotly_chart(fig_map,use_container_width=True,key=f"map_{prefix}",
                        config={"scrollZoom":True,"displayModeBar":True,
                                "modeBarButtonsToAdd":["pan2d","zoomIn2d","zoomOut2d"],
                                "displaylogo":False})
    else:
        st.info("Select at least one market to show the map.")
    st.divider()

    st.subheader("Detailed pathway requirements")
    detail_tabs = st.tabs([FRAMEWORKS[fw]["label"] for fw in selected_fws])
    for tab,fw in zip(detail_tabs,selected_fws):
        with tab:
            dc1,dc2 = st.columns(2)
            with dc1:
                st.markdown("**Key details**")
                for lbl,field in FW_FIELDS[fw]:
                    val    = data[fw].get(field,"—")
                    suffix = " months" if field=="timeline_months" else ""
                    st.markdown(f"- {lbl}: **{val}{suffix}**")
                rule = data[fw].get("rule_applied","")
                if rule: st.markdown(f"- Rule applied: **{rule}**")
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
                data[fw].get("iso_13485_required",
                data[fw].get("audited_qms_required","—"))),
            data[fw].get(CLIN_KEY[fw],"—"),
            data[fw].get("rule_applied","—"),
        ]
    st.dataframe(pd.DataFrame(summary),use_container_width=True,hide_index=True)

# ── PDF generator ─────────────────────────────────────────────────────────────
def generate_pdf(data, selected_fws, data2=None, selected_fws2=None):
    pdf=FPDF(); PAGE_W=180; LABEL_W=55; VALUE_W=PAGE_W-LABEL_W
    pdf.set_margins(15,15,15); pdf.set_auto_page_break(auto=True,margin=15)
    def safe(t):
        """Convert any string to FPDF-safe Latin-1, replacing all unicode chars."""
        s = str(t)
        # Replace common unicode characters with ASCII equivalents
        replacements = {
            "\u2014": "-",   # em dash —
            "\u2013": "-",   # en dash –
            "\u2012": "-",   # figure dash
            "\u2010": "-",   # hyphen
            "\u2018": "'",   # left single quote
            "\u2019": "'",   # right single quote
            "\u201c": '"',   # left double quote
            "\u201d": '"',   # right double quote
            "\u2026": "...", # ellipsis
            "\u2192": "->",  # right arrow
            "\u2190": "<-",  # left arrow
            "\u00b0": "deg", # degree sign
            "\u00b5": "u",   # micro sign
            "\u00d7": "x",   # multiplication sign
            "\u00f7": "/",   # division sign
            "\u2264": "<=",  # less than or equal
            "\u2265": ">=",  # greater than or equal
            "\u00ae": "(R)", # registered trademark
            "\u00a9": "(C)", # copyright
            "\u2122": "(TM)",# trademark
        }
        for unicode_char, ascii_equiv in replacements.items():
            s = s.replace(unicode_char, ascii_equiv)
        # Final fallback: encode to latin-1, replacing anything still not supported
        return s.encode("latin-1", errors="replace").decode("latin-1")
    def sh(title,color=(30,158,117)):
        pdf.set_font("Helvetica","B",13); pdf.set_text_color(*color)
        pdf.cell(PAGE_W,9,safe(title),ln=True); pdf.set_text_color(0,0,0)
    def fr(label,value):
        pdf.set_font("Helvetica","B",9)
        pdf.cell(LABEL_W,6,safe(f"{label}:"),border=0,ln=0)
        pdf.set_font("Helvetica","",9)
        pdf.multi_cell(VALUE_W,6,safe(str(value)),border=0); pdf.set_x(15)
    def dv():
        pdf.set_draw_color(220,220,220)
        pdf.line(15,pdf.get_y(),195,pdf.get_y()); pdf.ln(4)
    def write_section(d,fws,label=""):
        pdf.set_font("Helvetica","B",11); pdf.set_text_color(60,60,60)
        if label: pdf.cell(PAGE_W,7,safe(label),ln=True)
        pdf.set_font("Helvetica","",10); pdf.set_text_color(100,100,100)
        pdf.cell(PAGE_W,6,safe(f"Device: {d['device_name']}"),ln=True)
        pdf.cell(PAGE_W,6,safe(f"Intended use: {d['intended_use']}"),ln=True)
        pdf.cell(PAGE_W,6,safe(f"Confidence: {d.get('confidence','—')}"),ln=True)
        if d.get("_correction_note"):
            pdf.set_font("Helvetica","I",8); pdf.set_text_color(180,80,0)
            pdf.multi_cell(PAGE_W,5,safe(f"Correction: {d['_correction_note']}"))
        disc = (d.get("disclaimer","").strip()
                or "Verify with a qualified regulatory professional.")
        pdf.set_font("Helvetica","I",8); pdf.set_text_color(120,120,120)
        pdf.multi_cell(PAGE_W,5,safe(f"Note: {disc}")); pdf.ln(3); dv()
        sh("Risk Classification Summary")
        pdf.set_font("Helvetica","B",9); cw=PAGE_W//4
        for h in ["Framework","Risk Class","Risk Level","Rule Applied"]:
            pdf.cell(cw,6,h,border=1,ln=0)
        pdf.ln(); pdf.set_font("Helvetica","",9)
        for fw in fws:
            rc=d[fw].get("risk_class","—"); lvl=RISK_LEVEL.get(rc,"Unknown")
            rl=d[fw].get("rule_applied","—")
            pdf.cell(cw,6,safe(FRAMEWORKS[fw]["label"]),border=1,ln=0)
            pdf.cell(cw,6,safe(rc),border=1,ln=0)
            pdf.cell(cw,6,safe(lvl),border=1,ln=0)
            pdf.cell(cw,6,safe(str(rl)[:22]),border=1,ln=True)
        pdf.ln(4); dv()
        sh("Approval Timeline Summary")
        pdf.set_font("Helvetica","B",9); hw=PAGE_W//2
        pdf.cell(hw,6,"Framework",border=1,ln=0)
        pdf.cell(hw,6,"Timeline",border=1,ln=True)
        pdf.set_font("Helvetica","",9); all_t=[]
        for fw in fws:
            t=int(d[fw].get("timeline_months",0))
            all_t.append((FRAMEWORKS[fw]["label"],t))
            pdf.cell(hw,6,safe(FRAMEWORKS[fw]["label"]),border=1,ln=0)
            pdf.cell(hw,6,safe(f"{t} months"),border=1,ln=True)
        fast=min(all_t,key=lambda x:x[1]); slow=max(all_t,key=lambda x:x[1])
        pdf.set_font("Helvetica","I",8)
        pdf.set_text_color(30,158,117)
        pdf.cell(PAGE_W,5,safe(f"Fastest: {fast[0]} — {fast[1]} months"),ln=True)
        pdf.set_text_color(200,80,40)
        pdf.cell(PAGE_W,5,safe(f"Slowest: {slow[0]} — {slow[1]} months"),ln=True)
        pdf.set_text_color(0,0,0); pdf.ln(3); dv()
        sh("Detailed Framework Analysis"); pdf.ln(2)
        for fw in fws:
            dd=d[fw]
            pdf.set_font("Helvetica","B",11); pdf.set_text_color(50,50,50)
            pdf.cell(PAGE_W,7,safe(f"  {FRAMEWORKS[fw]['label']}"),ln=True)
            pdf.set_text_color(0,0,0)
            fr("Risk class",dd.get("risk_class","—"))
            fr("Rule applied",dd.get("rule_applied","—"))
            fr("Pathway",dd.get(PATHWAY_KEY.get(fw,""),"—"))
            fr("Timeline",f"{dd.get('timeline_months','—')} months")
            for lbl,key in FW_FIELDS[fw]:
                if key not in ["risk_class","timeline_months"]:
                    fr(lbl,dd.get(key,"—"))
            fr("Reasoning",dd.get("reasoning","—"))
            pdf.ln(3); pdf.set_draw_color(230,230,230)
            pdf.line(15,pdf.get_y(),195,pdf.get_y()); pdf.ln(3)
        dv(); sh("Side-by-Side Summary")
        cw2=PAGE_W//(len(fws)+1); pdf.set_font("Helvetica","B",8)
        pdf.cell(cw2,6,"Parameter",border=1,ln=0)
        for fw in fws:
            pdf.cell(cw2,6,safe(FRAMEWORKS[fw]["label"][:12]),border=1,ln=0)
        pdf.ln(); pdf.set_font("Helvetica","",8)
        for rl,fn in [
            ("Risk class",  lambda fw:d[fw].get("risk_class","—")),
            ("Rule",        lambda fw:d[fw].get("rule_applied","—")),
            ("Pathway",     lambda fw:d[fw].get(PATHWAY_KEY.get(fw,""),"—")),
            ("Timeline",    lambda fw:f"{d[fw].get('timeline_months','—')} mo"),
            ("QMS",         lambda fw:d[fw].get("qms_required",
                            d[fw].get("iso_13485_required",
                            d[fw].get("audited_qms_required","—")))),
            ("Clinical",    lambda fw:d[fw].get(CLIN_KEY[fw],"—")),
        ]:
            pdf.cell(cw2,6,safe(rl),border=1,ln=0)
            for fw in fws:
                pdf.cell(cw2,6,safe(str(fn(fw))[:14]),border=1,ln=0)
            pdf.ln()
        pdf.ln(4)
    pdf.add_page()
    pdf.set_font("Helvetica","B",18)
    pdf.cell(PAGE_W,12,"MedTech Regulatory Pathway Report",ln=True,align="C")
    pdf.set_font("Helvetica","",10); pdf.set_text_color(120,120,120)
    pdf.cell(PAGE_W,6,"AI-powered global regulatory analysis - 7 frameworks",
             ln=True,align="C")
    pdf.set_text_color(0,0,0); pdf.ln(4)
    pdf.set_draw_color(30,158,117); pdf.set_line_width(0.8)
    pdf.line(15,pdf.get_y(),195,pdf.get_y()); pdf.set_line_width(0.2); pdf.ln(6)
    if data2 and selected_fws2:
        pdf.set_font("Helvetica","B",14); pdf.set_text_color(30,158,117)
        pdf.cell(PAGE_W,8,"DEVICE COMPARISON REPORT",ln=True,align="C")
        pdf.set_text_color(0,0,0); pdf.ln(4)
        write_section(data,selected_fws,"DEVICE 1")
        pdf.add_page(); write_section(data2,selected_fws2,"DEVICE 2")
    else:
        write_section(data,selected_fws)
    pdf.set_font("Helvetica","I",8); pdf.set_text_color(150,150,150)
    pdf.multi_cell(PAGE_W,5,
        "DISCLAIMER: For educational and preliminary scoping only. "
        "AI-generated based on CDSCO MDR 2017 | FDA 21 CFR | EU MDR 2017/745 | "
        "Health Canada SOR/98-282 | Japan PMD Act | Australia TGO 2002 | "
        "Russia Roszdravnadzor Decree No.1684. "
        "Verify with a qualified regulatory affairs professional.",align="C")
    return bytes(pdf.output())

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧬 Navigator")
    st.caption("7 global frameworks · Powered by Groq")
    st.divider()
    compare_mode = st.checkbox("Compare two devices",value=False)
    input_mode   = st.radio("Input method",
                            ["Type any device name","Choose from preset list"])
    presets = sorted(["Pacemaker","Thermometer","Blood Pressure Monitor",
               "Pulse Oximeter","ECG Machine","Ventilator","Surgical Scissors",
               "Infusion Pump","MRI Scanner","HIV Test Kit","Glucose Meter",
               "Bone Implant","Total Knee Replacement","Total Hip Replacement",
               "Coronary Stent","Drug-Eluting Stent"])
    if input_mode == "Type any device name":
        device_name  = st.text_input("Device name",
                                     placeholder="e.g. Coronary Stent")
        device_desc  = st.text_area("Description (optional)",height=60)
        device_name2 = st.text_input("Device 2",
                                     placeholder="e.g. Drug-Eluting Stent")                         if compare_mode else ""
        device_desc2 = st.text_area("Description 2 (optional)",height=60)                         if compare_mode else ""
    else:
        device_name  = st.selectbox("Device 1",presets)
        device_desc  = ""
        device_name2 = st.selectbox("Device 2",presets,index=1)                         if compare_mode else ""
        device_desc2 = ""
    st.subheader("Target markets")
    cols_sb = st.columns(2)
    checks = {
        "cdsco"         : cols_sb[0].checkbox("🇮🇳 India",      value=True),
        "fda"           : cols_sb[1].checkbox("🇺🇸 USA",         value=True),
        "eu"            : cols_sb[0].checkbox("🇪🇺 Europe",      value=True),
        "health_canada" : cols_sb[1].checkbox("🇨🇦 Canada",      value=True),
        "japan"         : cols_sb[0].checkbox("🇯🇵 Japan",       value=True),
        "australia"     : cols_sb[1].checkbox("🇦🇺 Australia",   value=True),
        "russia"        : cols_sb[0].checkbox("🇷🇺 Russia",      value=False),
    }
    selected_fws = [fw for fw,checked in checks.items() if checked]
    st.divider()
    analyse = st.button("Analyse Device",type="primary",use_container_width=True)
    if st.session_state.search_history:
        st.divider(); st.subheader("History")
        for i,h in enumerate(reversed(st.session_state.search_history[-5:])):
            if st.button(
                f"{h['device']} · {h['cdsco_class']}/{h['fda_class']}/{h['eu_class']}",
                key=f"hist_{i}",use_container_width=True
            ):
                st.session_state["reload_data"]=h["data"]; st.rerun()
        hist_df   = pd.DataFrame([{k:v for k,v in h.items() if k!="data"}
                                   for h in st.session_state.search_history])
        csv_bytes = hist_df.to_csv(index=False).encode("utf-8")
        st.download_button("Export CSV",data=csv_bytes,
                           file_name="regulatory_history.csv",
                           mime="text/csv",use_container_width=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 🧬 MedTech Regulatory Pathway Navigator")
st.markdown("*AI-powered classification across 7 global regulatory frameworks*")
st.divider()

# ── CHATBOT QUEUE PROCESSOR — MUST be at top before any widget ───────────────
# This is the architectural fix for the chatbot.
# On every rerun, this block runs FIRST before any widget is drawn.
# If a question was queued (by a button click or send), it is processed
# here and the answer stored in chat_history before anything renders.
if st.session_state.get("_queued_question"):
    _q = st.session_state["_queued_question"]
    st.session_state["_queued_question"] = None
    if st.session_state.current_device and _q.strip():
        with st.spinner("Consulting regulatory knowledge base..."):
            try:
                _ans = regulatory_chat(_q, st.session_state.current_device)
            except Exception as _e:
                _ans = f"Sorry, there was an error: {_e}"
        st.session_state.chat_history.append({"question":_q,"answer":_ans})
        st.session_state.chat_input_counter += 1

# ── Load classification data ──────────────────────────────────────────────────
if "reload_data" in st.session_state:
    data=st.session_state.pop("reload_data"); data2=None; analyse_show=True
elif analyse and device_name.strip():
    analyse_show=True
    with st.spinner(f"Classifying **{device_name}** across 7 frameworks..."):
        try:
            data=ai_classify_device(device_name.strip(),device_desc.strip())
        except Exception as e:
            st.error(f"Classification failed: {e}"); st.stop()
    data2=None
    if compare_mode and device_name2.strip():
        with st.spinner(f"Classifying **{device_name2}**..."):
            try:
                data2=ai_classify_device(device_name2.strip(),device_desc2.strip())
            except Exception as e:
                st.error(f"Device 2 failed: {e}"); data2=None
    st.session_state.chat_history=[]
    st.session_state.current_device=data
    st.session_state.search_history.append({
        "device":data["device_name"],"confidence":data.get("confidence","—"),
        "cdsco_class":data["cdsco"]["risk_class"],
        "fda_class":data["fda"]["risk_class"],
        "eu_class":data["eu"]["risk_class"],"data":data,
    })
elif analyse and not device_name.strip():
    st.warning("Please enter a device name first.")
    analyse_show=False; data=None; data2=None
else:
    analyse_show=False; data=None; data2=None

# ── Results ───────────────────────────────────────────────────────────────────
if analyse_show and data:
    if compare_mode and data2:
        st.subheader("Device Comparison")
        dev_tab1,dev_tab2,radar_tab = st.tabs([
            f"Device 1: {data['device_name']}",
            f"Device 2: {data2['device_name']}",
            "Radar comparison"
        ])
        with dev_tab1:
            show_device_results(data,selected_fws,prefix="d1")
        with dev_tab2:
            show_device_results(data2,selected_fws,prefix="d2")
        with radar_tab:
            st.subheader("Risk burden radar")
            risk_score={"Low":1,"Medium":2,"High":3,"Critical":4,"Unknown":0}
            categories=[FRAMEWORKS[fw]["label"] for fw in selected_fws]
            cat_closed=categories+[categories[0]]
            vals1=[risk_score.get(RISK_LEVEL.get(
                        data[fw].get("risk_class",""),"Unknown"),0)
                   for fw in selected_fws]
            vals2=[risk_score.get(RISK_LEVEL.get(
                        data2[fw].get("risk_class",""),"Unknown"),0)
                   for fw in selected_fws]
            fig_r=go.Figure()
            fig_r.add_trace(go.Scatterpolar(
                r=vals1+[vals1[0]],theta=cat_closed,fill="toself",
                name=data["device_name"],line_color="#1D9E75",
                fillcolor="rgba(29,158,117,0.2)"))
            fig_r.add_trace(go.Scatterpolar(
                r=vals2+[vals2[0]],theta=cat_closed,fill="toself",
                name=data2["device_name"],line_color="#378ADD",
                fillcolor="rgba(55,138,221,0.2)"))
            fig_r.update_layout(
                polar=dict(radialaxis=dict(visible=True,range=[0,4],
                    tickvals=[1,2,3,4],ticktext=["Low","Med","High","Crit"])),
                showlegend=True,height=450,margin=dict(t=50,b=50),
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_r,use_container_width=True,key="radar_main")
            st.divider(); st.subheader("Head-to-head summary")
            h2h={"Framework":[],"D1 class":[],"D1 timeline":[],
                 "D2 class":[],"D2 timeline":[],"Faster entry":[]}
            for fw in selected_fws:
                t1=int(data[fw].get("timeline_months",0))
                t2=int(data2[fw].get("timeline_months",0))
                h2h["Framework"].append(FRAMEWORKS[fw]["label"])
                h2h["D1 class"].append(data[fw].get("risk_class","—"))
                h2h["D1 timeline"].append(f"{t1} mo")
                h2h["D2 class"].append(data2[fw].get("risk_class","—"))
                h2h["D2 timeline"].append(f"{t2} mo")
                h2h["Faster entry"].append(
                    data["device_name"] if t1<=t2 else data2["device_name"])
            st.dataframe(pd.DataFrame(h2h),use_container_width=True,hide_index=True)
        st.divider()
        ex1,ex2=st.columns([1,3])
        with ex1:
            pdf_bytes=generate_pdf(data,selected_fws,data2,selected_fws)
            st.download_button("Download comparison PDF",data=pdf_bytes,
                file_name="comparison_report.pdf",
                mime="application/pdf",type="primary",use_container_width=True)
        with ex2:
            st.caption("Full comparison — both devices, all frameworks.")
    else:
        show_device_results(data,selected_fws,prefix="single")
        ex1,ex2=st.columns([1,3])
        with ex1:
            pdf_bytes=generate_pdf(data,selected_fws)
            st.download_button("Download PDF",data=pdf_bytes,
                file_name=f"{data['device_name'].replace(' ','_')}_report.pdf",
                mime="application/pdf",type="primary",use_container_width=True)
        with ex2:
            st.caption(f"Full pathway — {len(selected_fws)} markets, all details.")

    st.divider()

    # ── CHATBOT ───────────────────────────────────────────────────────────────
    st.subheader("💬 Ask the regulatory AI")
    st.caption(
        f"Context-aware Q&A about **{data['device_name']}**. "
        "Knows the full classification above including Russia."
    )

    suggestions = [
        "What documents do I need to prepare first?",
        "Which market should I enter first and why?",
        "What is the estimated total regulatory cost?",
        "What clinical evidence is needed?",
        "What ISO standards apply to this device?",
        "Walk me through submission for the fastest market",
    ]
    st.markdown("**Quick questions — click any:**")
    qc1,qc2,qc3 = st.columns(3)
    qcols = [qc1,qc2,qc3]
    for idx,sug in enumerate(suggestions):
        if qcols[idx%3].button(sug,key=f"qbtn_{idx}",use_container_width=True):
            st.session_state["_queued_question"] = sug
            st.rerun()

    st.markdown("**Or type your own:**")
    inp_col,btn_col = st.columns([5,1])
    typed_q = inp_col.text_input(
        "q_input",label_visibility="collapsed",
        placeholder="e.g. What Russian authorised rep documents do I need?",
        key=f"chat_text_{st.session_state.chat_input_counter}"
    )
    if btn_col.button("Send ➤",key="send_btn",type="primary"):
        if typed_q.strip():
            st.session_state["_queued_question"] = typed_q.strip()
            st.rerun()

    if st.session_state.chat_history:
        st.markdown("---")
        for turn in reversed(st.session_state.chat_history):
            with st.chat_message("user"):
                st.markdown(turn["question"])
            with st.chat_message("assistant"):
                st.markdown(turn["answer"])
        if st.button("🗑️ Clear conversation",key="clear_chat"):
            st.session_state.chat_history=[]
            st.session_state.chat_input_counter+=1
            st.rerun()
    else:
        st.info("Click a quick question or type your own and press Send ➤")

    st.divider()
    st.warning(
        "**Disclaimer:** For educational and preliminary scoping purposes only. "
        "AI-generated based on CDSCO MDR 2017 | FDA 21 CFR | EU MDR 2017/745 | "
        "Health Canada SOR/98-282 | Japan PMD Act | Australia TGO 2002 | "
        "Russia Roszdravnadzor Decree No.1684. "
        "Always verify with a qualified regulatory affairs professional.",
        icon="⚠️"
    )

else:
    st.markdown("""
    ### How to use
    1. Type any medical device name in the sidebar
    2. Select your target markets (Russia now available)
    3. Click **Analyse Device**
    4. Ask follow-up questions in the Q&A panel below

    #### 7 frameworks covered
    | Market | Framework | Classes |
    |--------|-----------|---------|
    | 🇮🇳 India | CDSCO MDR 2017 | A / B / C / D |
    | 🇺🇸 USA | FDA 21 CFR | I / II / III |
    | 🇪🇺 Europe | EU MDR 2017/745 | I / IIa / IIb / III |
    | 🇨🇦 Canada | Health Canada SOR/98-282 | I / II / III / IV |
    | 🇯🇵 Japan | PMDA Yakuji Ho | I / II / III / IV |
    | 🇦🇺 Australia | TGA ARTG | I / IIa / IIb / III |
    | 🇷🇺 Russia | Roszdravnadzor Decree No.1684 | 1 / 2a / 2b / 3 |

    #### Try these devices
    - Coronary Stent · Drug-Eluting Stent
    - Total Knee Replacement · Total Hip Replacement
    - Smart insulin pen · AI retinal scanner
    - Robotic surgical arm · Neural implant
    """)
