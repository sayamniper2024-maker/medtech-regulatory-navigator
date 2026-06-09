
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from groq import Groq
from fpdf import FPDF
import fitz
import json, os, io

st.set_page_config(page_title="MedTech Regulatory Navigator", page_icon="🧬", layout="wide")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY)

for _k, _v in {
    "classify_cache"     : {},
    "search_history"     : [],
    "chat_history"       : [],
    "current_device"     : None,
    "chat_input_counter" : 0,
    "_queued_question"   : None,
    "_queued_device"     : None,
    "last_data"          : None,
    "last_data2"         : None,
    "last_fws"           : [],
    "last_compare"       : False,
    "pdf_device_name"    : "",
    "pdf_device_desc"    : "",
    "gap_result"         : None,
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

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
    "cdsco":"license_type","fda":"pathway","eu":"technical_file_type",
    "health_canada":"licence_type","japan":"approval_type",
    "australia":"artg_pathway","russia":"registration_type",
}
CLIN_KEY = {
    "cdsco":"clinical_data_required","fda":"clinical_trials_required",
    "eu":"clinical_evaluation_required","health_canada":"clinical_data_required",
    "japan":"clinical_trial_required","australia":"clinical_evidence_required",
    "russia":"clinical_investigation_required",
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
    "cdsco"        :[("License type","license_type"),("Timeline","timeline_months"),
                     ("QMS required","qms_required"),("Clinical data","clinical_data_required")],
    "fda"          :[("Pathway","pathway"),("Timeline","timeline_months"),
                     ("Predicate needed","predicate_needed"),
                     ("Clinical trials","clinical_trials_required"),
                     ("IDE required","ide_required")],
    "eu"           :[("Tech file","technical_file_type"),("Timeline","timeline_months"),
                     ("Notified body","notified_body_needed"),
                     ("Clinical eval","clinical_evaluation_required"),
                     ("PMCF required","pmcf_required")],
    "health_canada":[("Licence type","licence_type"),("Timeline","timeline_months"),
                     ("QMS required","qms_required"),
                     ("Clinical data","clinical_data_required"),
                     ("HPFB review","hpfb_review")],
    "japan"        :[("Approval type","approval_type"),("Timeline","timeline_months"),
                     ("DMAH required","dmah_required"),
                     ("Clinical trial","clinical_trial_required"),
                     ("JIS standard","jis_standard_required")],
    "australia"    :[("ARTG pathway","artg_pathway"),("Timeline","timeline_months"),
                     ("Audited QMS","audited_qms_required"),
                     ("Clinical evidence","clinical_evidence_required"),
                     ("CAB","conformity_assessment_body")],
    "russia"       :[("Registration type","registration_type"),
                     ("Timeline","timeline_months"),
                     ("ISO 13485 required","iso_13485_required"),
                     ("Local testing","local_testing_required"),
                     ("Clinical investigation","clinical_investigation_required"),
                     ("Site inspection","site_inspection_required"),
                     ("RU REP required","ru_rep_required")],
}

RULE_EXCEPTIONS = """
=== CRITICAL CLASSIFICATION EXCEPTIONS - CHECK THESE FIRST ===
EU MDR 2017/745 Annex VIII Rule 8 - Class III (NOT IIb):
- Coronary stents, cardiac stents, drug-eluting stents -> Class III
- Any implantable device contacting heart or central circulatory system -> Class III
- Total knee replacement (TKR), total hip replacement (THR) -> Class III
- All joint replacement implants -> Class III
- Pacemakers, ICDs -> Class III (Rule 7)
- LVAD, mechanical heart valves -> Class III
FDA 21 CFR - cardiovascular = Part 870 (NOT Part 882):
- Coronary stents -> Class III, PMA, 21 CFR 870.3945
- Joint replacements -> Class III, PMA, 21 CFR 888.3400/888.3320
Russia Roszdravnadzor (Decree No.1684):
- Classes: 1, 2a, 2b, 3. RU REP required for ALL foreign manufacturers.
- Coronary stents, joint replacements, pacemakers -> Class 3
CDSCO: cardiac implants + joint replacements -> Class D
Health Canada: cardiac implants + joint replacements -> Class IV
Japan: cardiac implants + joint replacements -> Class IV, Approval, DMAH required
Australia: cardiac implants + joint replacements -> Class III
"""

KNOWN_CORRECTIONS = [
    {
        "keywords":["coronary stent","cardiac stent","drug-eluting stent",
                    "drug eluting stent","bare metal stent","bare-metal stent",
                    "intravascular stent","coronary artery stent"],
        "corrections":{
            "fda"          :{"risk_class":"III","pathway":"PMA","rule_applied":"21 CFR 870.3945",
                             "clinical_trials_required":"Yes","ide_required":"Yes",
                             "predicate_needed":"No","timeline_months":36},
            "eu"           :{"risk_class":"III","notified_body_needed":"Yes",
                             "rule_applied":"EU MDR Annex VIII Rule 8",
                             "clinical_evaluation_required":"Yes","pmcf_required":"Yes",
                             "technical_file_type":"Full Tech File","timeline_months":24},
            "cdsco"        :{"risk_class":"D","license_type":"MD-14",
                             "rule_applied":"MDR 2017 Schedule 1",
                             "clinical_data_required":"Yes","timeline_months":18},
            "health_canada":{"risk_class":"IV","licence_type":"Device Licence",
                             "rule_applied":"SOR/98-282","timeline_months":18},
            "japan"        :{"risk_class":"IV","approval_type":"Approval",
                             "rule_applied":"PMD Act Class IV",
                             "dmah_required":"Yes","timeline_months":36},
            "australia"    :{"risk_class":"III","artg_pathway":"Conformity assessment",
                             "rule_applied":"TGA Schedule 2","timeline_months":20},
            "russia"       :{"risk_class":"3","registration_type":"Full registration (RZN)",
                             "rule_applied":"Decree No.1684 Class 3",
                             "clinical_investigation_required":"Yes",
                             "iso_13485_required":"Yes","local_testing_required":"Yes",
                             "site_inspection_required":"Yes","ru_rep_required":"Yes",
                             "timeline_months":24},
        },
        "note":"Coronary/cardiac stents contact central circulatory system - "
               "escalated to highest class in all frameworks."
    },
    {
        "keywords":["total knee","tkr","total hip","thr","hip replacement",
                    "knee replacement","joint replacement","femoral stem",
                    "acetabular cup","tibial base plate"],
        "corrections":{
            "fda"          :{"risk_class":"III","pathway":"PMA","predicate_needed":"No",
                             "clinical_trials_required":"Yes","ide_required":"Yes",
                             "rule_applied":"21 CFR 888.3400/888.3320","timeline_months":36},
            "eu"           :{"risk_class":"III","notified_body_needed":"Yes",
                             "rule_applied":"EU MDR Annex VIII Rule 8",
                             "clinical_evaluation_required":"Yes","pmcf_required":"Yes",
                             "technical_file_type":"Full Tech File","timeline_months":24},
            "cdsco"        :{"risk_class":"D","license_type":"MD-14",
                             "rule_applied":"MDR 2017 Schedule 1","timeline_months":18},
            "health_canada":{"risk_class":"IV","licence_type":"Device Licence",
                             "rule_applied":"SOR/98-282","timeline_months":18},
            "japan"        :{"risk_class":"IV","approval_type":"Approval",
                             "rule_applied":"PMD Act Class IV",
                             "dmah_required":"Yes","timeline_months":36},
            "australia"    :{"risk_class":"III","artg_pathway":"Conformity assessment",
                             "rule_applied":"TGA Schedule 2","timeline_months":20},
            "russia"       :{"risk_class":"3","registration_type":"Full registration (RZN)",
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
                    f"**{FRAMEWORKS[fw]['label']}**: corrected {chr(44).join(fw_fixes)}"
                )
        if corrections_made:
            result["_correction_note"] = rule["note"]
            result["_corrections"]     = corrections_made
            result["confidence"]       = "High"
        break
    return result

def ai_classify_device(device_name, device_description=""):
    cache_key = f"{device_name.lower().strip()}|{device_description.lower().strip()}"
    if cache_key in st.session_state.classify_cache:
        return st.session_state.classify_cache[cache_key]
    prompt = f"""You are a senior medical device regulatory affairs expert.
{RULE_EXCEPTIONS}
Classify this device across ALL 7 frameworks. Return ONLY valid JSON.
Device: {device_name}
{f"Description: {device_description}" if device_description else ""}
Return exactly this JSON:
{{
  "device_name":"{device_name}","intended_use":"one line clinical intended use",
  "cdsco":{{"risk_class":"A/B/C/D","license_type":"MD-5/MD-9/MD-14","timeline_months":0,
    "qms_required":"Yes/No","clinical_data_required":"Yes/No",
    "reasoning":"cite MDR 2017 rule","rule_applied":"Schedule rule"}},
  "fda":{{"risk_class":"I/II/III","pathway":"Exempt/510(k)/PMA","predicate_needed":"Yes/No",
    "timeline_months":0,"clinical_trials_required":"Yes/No","ide_required":"Yes/No",
    "reasoning":"cite 21 CFR part","rule_applied":"21 CFR section"}},
  "eu":{{"risk_class":"I/IIa/IIb/III","notified_body_needed":"Yes/No","timeline_months":0,
    "technical_file_type":"Basic UDI-DI/Full Tech File","clinical_evaluation_required":"Yes/No",
    "pmcf_required":"Yes/No","reasoning":"cite Annex VIII rule","rule_applied":"Rule number"}},
  "health_canada":{{"risk_class":"I/II/III/IV","licence_type":"MDEL only/Device Licence",
    "timeline_months":0,"qms_required":"Yes/No","clinical_data_required":"Yes/No",
    "hpfb_review":"Yes/No","reasoning":"cite SOR/98-282","rule_applied":"SOR rule"}},
  "japan":{{"risk_class":"I/II/III/IV","approval_type":"Notification/Certification/Approval",
    "dmah_required":"Yes","timeline_months":0,"clinical_trial_required":"Yes/No",
    "jis_standard_required":"Yes/No","reasoning":"cite PMD Act","rule_applied":"PMD Act"}},
  "australia":{{"risk_class":"I/IIa/IIb/III/AIMD","artg_pathway":"Self-assessment/Conformity assessment",
    "timeline_months":0,"audited_qms_required":"Yes/No","clinical_evidence_required":"Yes/No",
    "conformity_assessment_body":"None/TGA/TGA or Notified Body",
    "reasoning":"cite TGA rule","rule_applied":"TGA rule"}},
  "russia":{{"risk_class":"1/2a/2b/3","registration_type":"Simplified/Full registration (RZN)/EAEU",
    "timeline_months":0,"iso_13485_required":"Yes/No","local_testing_required":"Yes",
    "clinical_investigation_required":"Yes/No","site_inspection_required":"Yes/No",
    "ru_rep_required":"Yes","reasoning":"cite Decree No.1684","rule_applied":"Decree No.1684"}},
  "confidence":"High/Medium/Low","disclaimer":""
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

def regulatory_chat(question, device_data):
    context_lines = [
        f"Device: {device_data.get('device_name','Unknown')}",
        f"Intended use: {device_data.get('intended_use','--')}",
        "Classification results:",
    ]
    for fw in list(FRAMEWORKS.keys()):
        d = device_data.get(fw,{})
        if d:
            context_lines.append(
                f"  {FRAMEWORKS[fw]['label']}: Class {d.get('risk_class','--')} | "
                f"Pathway: {d.get(PATHWAY_KEY.get(fw,''),'--')} | "
                f"{d.get('timeline_months','--')} months | "
                f"Rule: {d.get('rule_applied','--')}"
            )
    system_msg = (
        "You are a senior regulatory affairs expert for global medical devices "
        "with deep knowledge of CDSCO MDR 2017, FDA 21 CFR, EU MDR 2017/745, "
        "Health Canada SOR/98-282, Japan PMD Act, Australia TGA, "
        "Russia Roszdravnadzor Decree No.1684, ISO 13485, ISO 14971, IEC 62304.\n\n"
        "Device context:\n" + "\n".join(context_lines) +
        "\n\nAnswer accurately and concisely. Cite regulatory rules. Max 300 words."
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

def extract_pdf_text(uploaded_file, max_chars=3000):
    try:
        pdf_bytes = uploaded_file.read()
        doc       = fitz.open(stream=pdf_bytes, filetype="pdf")
        text      = ""
        page_count = len(doc)
        for page in doc:
            text += page.get_text()
            if len(text) >= max_chars:
                break
        doc.close()
        return text[:max_chars], page_count, True
    except Exception as e:
        return "", 0, False

def ai_extract_device_info(pdf_text):
    prompt = f"""You are a medical device regulatory expert.
Read this device document and extract key information.
Return ONLY valid JSON, nothing else.

Document text:
{pdf_text}

Return exactly this JSON:
{{
  "device_name": "specific medical device name",
  "intended_use": "one sentence clinical intended use",
  "description": "2-3 sentence technical description for regulatory classification",
  "confidence": "High/Medium/Low"
}}"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":prompt}],
        temperature=0.1,
        max_tokens=400,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    return json.loads(raw.strip())

def build_world_map(data, selected_fws, prefix=""):
    countries, timelines, hover = [], [], []
    for fw in selected_fws:
        c = COUNTRY_MAP.get(fw)
        if not c: continue
        t  = int(data[fw].get("timeline_months",0))
        rc = data[fw].get("risk_class","--")
        pw = data[fw].get(PATHWAY_KEY.get(fw,""),"--")
        rl = data[fw].get("rule_applied","--")
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
        locations=countries,z=timelines,text=hover,
        hovertemplate="%{text}<extra></extra>",
        locationmode="ISO-3",
        colorscale=[[0.0,"#1D9E75"],[0.35,"#BA7517"],
                    [0.65,"#D85A30"],[1.0,"#E24B4A"]],
        zmin=min(timelines),zmax=max(timelines),
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

def safe_pdf(t):
    s = str(t)
    for uc,ac in [
        ("\u2014","-"),("\u2013","-"),("\u2018","'"),("\u2019","'"),
        ("\u201c",'"'),("\u201d",'"'),("\u2026","..."),("\u2192","->"),
        ("\u00ae","(R)"),("\u00a9","(C)"),("\u2122","(TM)"),
    ]:
        s = s.replace(uc,ac)
    return s.encode("latin-1",errors="replace").decode("latin-1")

def show_device_results(data, selected_fws, prefix=""):
    conf        = data.get("confidence","Medium")
    conf_colors = {"High":"green","Medium":"orange","Low":"red"}
    disclaimer  = data.get("disclaimer","").strip() or (
        "AI-generated classification. Always verify with a qualified "
        "regulatory affairs professional before actual submissions."
    )
    st.info(f"**{data['device_name']}** -- {data['intended_use']}")
    st.markdown(
        f"AI confidence: :{conf_colors.get(conf,'orange')}[**{conf}**]  "
        f"|  _{disclaimer}_"
    )
    if data.get("_corrections"):
        with st.expander("Classification corrections applied", expanded=True):
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
    sc1.success(f"Fastest: **{sp[0][0]}** -- {sp[0][1]} months")
    sc2.info(   f"Median: **{sp[len(sp)//2][0]}**")
    sc3.warning(f"Slowest: **{sp[-1][0]}** -- {sp[-1][1]} months")
    st.divider()

    st.subheader("Global market entry map")
    st.caption("Hover over highlighted countries for full pathway details.")
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
                    val    = data[fw].get(field,"--")
                    suffix = " months" if field=="timeline_months" else ""
                    st.markdown(f"- {lbl}: **{val}{suffix}**")
                rule = data[fw].get("rule_applied","")
                if rule: st.markdown(f"- Rule applied: **{rule}**")
            with dc2:
                st.markdown("**Regulatory reasoning**")
                st.info(data[fw].get("reasoning","--"))
                rc  = data[fw].get("risk_class","?")
                lvl = RISK_LEVEL.get(rc,"Unknown")
                clr = RISK_COLOR.get(lvl,"#888")
                st.markdown(
                    f"<span style='color:{clr};font-weight:600;font-size:15px'>"
                    f"Class {rc} -- {lvl} Risk</span>",
                    unsafe_allow_html=True)
    st.divider()

    st.subheader("Side-by-side summary")
    summary = {"Parameter":["Risk class","Pathway / Licence",
                             "Timeline (months)","QMS required",
                             "Clinical data","Rule applied"]}
    for fw in selected_fws:
        summary[FRAMEWORKS[fw]["label"]] = [
            data[fw].get("risk_class","--"),
            data[fw].get(PATHWAY_KEY.get(fw,""),"--"),
            str(data[fw].get("timeline_months","--")),
            data[fw].get("qms_required",
                data[fw].get("iso_13485_required",
                data[fw].get("audited_qms_required","--"))),
            data[fw].get(CLIN_KEY[fw],"--"),
            data[fw].get("rule_applied","--"),
        ]
    st.dataframe(pd.DataFrame(summary),use_container_width=True,hide_index=True)

def generate_pdf(data, selected_fws, data2=None, selected_fws2=None):
    pdf=FPDF(); PAGE_W=180; LABEL_W=55; VALUE_W=PAGE_W-LABEL_W
    pdf.set_margins(15,15,15); pdf.set_auto_page_break(auto=True,margin=15)
    def sh(title,color=(30,158,117)):
        pdf.set_font("Helvetica","B",13); pdf.set_text_color(*color)
        pdf.cell(PAGE_W,9,safe_pdf(title),ln=True); pdf.set_text_color(0,0,0)
    def fr(label,value):
        pdf.set_font("Helvetica","B",9)
        pdf.cell(LABEL_W,6,safe_pdf(f"{label}:"),border=0,ln=0)
        pdf.set_font("Helvetica","",9)
        pdf.multi_cell(VALUE_W,6,safe_pdf(str(value)),border=0); pdf.set_x(15)
    def dv():
        pdf.set_draw_color(220,220,220)
        pdf.line(15,pdf.get_y(),195,pdf.get_y()); pdf.ln(4)
    def write_section(d,fws,label=""):
        pdf.set_font("Helvetica","B",11); pdf.set_text_color(60,60,60)
        if label: pdf.cell(PAGE_W,7,safe_pdf(label),ln=True)
        pdf.set_font("Helvetica","",10); pdf.set_text_color(100,100,100)
        pdf.cell(PAGE_W,6,safe_pdf(f"Device: {d['device_name']}"),ln=True)
        pdf.cell(PAGE_W,6,safe_pdf(f"Intended use: {d['intended_use']}"),ln=True)
        pdf.cell(PAGE_W,6,safe_pdf(f"Confidence: {d.get('confidence','--')}"),ln=True)
        if d.get("_correction_note"):
            pdf.set_font("Helvetica","I",8); pdf.set_text_color(180,80,0)
            pdf.multi_cell(PAGE_W,5,safe_pdf(f"Correction: {d['_correction_note']}"))
        disc=(d.get("disclaimer","").strip()
              or "Verify with a qualified regulatory professional.")
        pdf.set_font("Helvetica","I",8); pdf.set_text_color(120,120,120)
        pdf.multi_cell(PAGE_W,5,safe_pdf(f"Note: {disc}")); pdf.ln(3); dv()
        sh("Risk Classification Summary")
        pdf.set_font("Helvetica","B",9); cw=PAGE_W//4
        for h in ["Framework","Risk Class","Risk Level","Rule Applied"]:
            pdf.cell(cw,6,h,border=1,ln=0)
        pdf.ln(); pdf.set_font("Helvetica","",9)
        for fw in fws:
            rc=d[fw].get("risk_class","--"); lvl=RISK_LEVEL.get(rc,"Unknown")
            rl=d[fw].get("rule_applied","--")
            pdf.cell(cw,6,safe_pdf(FRAMEWORKS[fw]["label"]),border=1,ln=0)
            pdf.cell(cw,6,safe_pdf(rc),border=1,ln=0)
            pdf.cell(cw,6,safe_pdf(lvl),border=1,ln=0)
            pdf.cell(cw,6,safe_pdf(str(rl)[:22]),border=1,ln=True)
        pdf.ln(4); dv()
        sh("Approval Timeline Summary")
        pdf.set_font("Helvetica","B",9); hw=PAGE_W//2
        pdf.cell(hw,6,"Framework",border=1,ln=0)
        pdf.cell(hw,6,"Timeline",border=1,ln=True)
        pdf.set_font("Helvetica","",9); all_t=[]
        for fw in fws:
            t=int(d[fw].get("timeline_months",0))
            all_t.append((FRAMEWORKS[fw]["label"],t))
            pdf.cell(hw,6,safe_pdf(FRAMEWORKS[fw]["label"]),border=1,ln=0)
            pdf.cell(hw,6,safe_pdf(f"{t} months"),border=1,ln=True)
        fast=min(all_t,key=lambda x:x[1]); slow=max(all_t,key=lambda x:x[1])
        pdf.set_font("Helvetica","I",8)
        pdf.set_text_color(30,158,117)
        pdf.cell(PAGE_W,5,safe_pdf(f"Fastest: {fast[0]} - {fast[1]} months"),ln=True)
        pdf.set_text_color(200,80,40)
        pdf.cell(PAGE_W,5,safe_pdf(f"Slowest: {slow[0]} - {slow[1]} months"),ln=True)
        pdf.set_text_color(0,0,0); pdf.ln(3); dv()
        sh("Detailed Framework Analysis"); pdf.ln(2)
        for fw in fws:
            dd=d[fw]
            pdf.set_font("Helvetica","B",11); pdf.set_text_color(50,50,50)
            pdf.cell(PAGE_W,7,safe_pdf(f"  {FRAMEWORKS[fw]['label']}"),ln=True)
            pdf.set_text_color(0,0,0)
            fr("Risk class",dd.get("risk_class","--"))
            fr("Rule applied",dd.get("rule_applied","--"))
            fr("Pathway",dd.get(PATHWAY_KEY.get(fw,""),"--"))
            fr("Timeline",f"{dd.get('timeline_months','--')} months")
            for lbl,key in FW_FIELDS[fw]:
                if key not in ["risk_class","timeline_months"]:
                    fr(lbl,dd.get(key,"--"))
            fr("Reasoning",dd.get("reasoning","--"))
            pdf.ln(3); pdf.set_draw_color(230,230,230)
            pdf.line(15,pdf.get_y(),195,pdf.get_y()); pdf.ln(3)
        dv(); sh("Side-by-Side Summary")
        cw2=PAGE_W//(len(fws)+1); pdf.set_font("Helvetica","B",8)
        pdf.cell(cw2,6,"Parameter",border=1,ln=0)
        for fw in fws:
            pdf.cell(cw2,6,safe_pdf(FRAMEWORKS[fw]["label"][:12]),border=1,ln=0)
        pdf.ln(); pdf.set_font("Helvetica","",8)
        for rl,fn in [
            ("Risk class", lambda fw:d[fw].get("risk_class","--")),
            ("Rule",       lambda fw:d[fw].get("rule_applied","--")),
            ("Pathway",    lambda fw:d[fw].get(PATHWAY_KEY.get(fw,""),"--")),
            ("Timeline",   lambda fw:f"{d[fw].get('timeline_months','--')} mo"),
            ("QMS",        lambda fw:d[fw].get("qms_required",
                           d[fw].get("iso_13485_required",
                           d[fw].get("audited_qms_required","--")))),
            ("Clinical",   lambda fw:d[fw].get(CLIN_KEY[fw],"--")),
        ]:
            pdf.cell(cw2,6,safe_pdf(rl),border=1,ln=0)
            for fw in fws:
                pdf.cell(cw2,6,safe_pdf(str(fn(fw))[:14]),border=1,ln=0)
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


# ── SUBMISSION GAP ANALYSER ───────────────────────────────────────────────────
SUBMISSION_CHECKLISTS = {
    "fda": {
        "510(k)": [
            "Device description and indications for use",
            "Substantial equivalence comparison to predicate device",
            "Performance testing data (bench testing)",
            "Biocompatibility testing (ISO 10993)",
            "Software documentation (if applicable, IEC 62304)",
            "Sterilisation validation (if applicable)",
            "Labeling (21 CFR Part 801)",
            "Quality System documentation (21 CFR Part 820)",
            "Standards compliance summary",
            "Truthful and accuracy statement",
        ],
        "PMA": [
            "Device description and principles of operation",
            "Indications for use and contraindications",
            "Non-clinical laboratory studies (bench, animal)",
            "Clinical investigation data (IDE studies)",
            "Manufacturing information and quality system",
            "Biocompatibility data (ISO 10993 series)",
            "Software documentation (IEC 62304)",
            "Sterilisation data (ISO 11135/11137)",
            "Labeling (21 CFR Part 801)",
            "Post-approval study protocol",
            "Risk analysis (ISO 14971)",
            "Summary of safety and effectiveness (SSED)",
        ],
        "Exempt": [
            "Basic device description",
            "Labeling (21 CFR Part 801)",
            "Good Manufacturing Practice (21 CFR Part 820)",
        ],
    },
    "eu": {
        "Full Tech File": [
            "Device description and specification",
            "Reference to previous generations and similar devices",
            "Design and manufacturing information",
            "General safety and performance requirements (GSPR) checklist",
            "Benefit-risk analysis and risk management (ISO 14971)",
            "Product verification and validation",
            "Clinical evaluation report (CER, MEDDEV 2.7/1 Rev 4)",
            "Post-market surveillance (PMS) plan",
            "Post-market clinical follow-up (PMCF) plan",
            "Instructions for use and labeling (EU MDR Annex I)",
            "UDI assignment and EUDAMED registration",
            "Declaration of conformity",
            "Summary of safety and clinical performance (SSCP) - Class III/IIb implants",
        ],
        "Basic UDI-DI": [
            "Device description",
            "General safety and performance requirements",
            "Labeling and instructions for use",
            "UDI assignment",
            "Declaration of conformity",
        ],
    },
    "cdsco": {
        "MD-14": [
            "Form MD-1 application",
            "Device master file",
            "ISO 13485 quality management certificate",
            "Test reports from NABL/BIS approved laboratory",
            "Free Sale Certificate from country of origin",
            "Clinical performance data",
            "Undertaking from manufacturer",
            "Device description and intended use",
            "Labeling as per MDR 2017 Schedule III",
            "Risk management file (ISO 14971)",
        ],
        "MD-9": [
            "Form MD-1 application",
            "Device master file",
            "ISO 13485 certificate",
            "Test reports from approved laboratory",
            "Device description and intended use",
            "Labeling as per MDR 2017",
            "Risk management summary",
        ],
        "MD-5": [
            "Form MD-1 application",
            "Basic device description",
            "Manufacturing details",
            "Labeling as per MDR 2017",
        ],
    },
    "health_canada": {
        "Device Licence": [
            "Device licence application (Health Canada form)",
            "Device description and intended use",
            "Safety and effectiveness summary",
            "Quality system evidence (ISO 13485)",
            "Manufacturing and quality control information",
            "Risk analysis summary (ISO 14971)",
            "Clinical evidence or literature review",
            "Labeling in English and French",
            "Device identifier information",
        ],
        "MDEL only": [
            "Medical Device Establishment Licence application",
            "Basic device description",
            "Labeling in English and French",
        ],
    },
    "japan": {
        "Approval": [
            "Application form (PMDA approval application)",
            "DMAH appointment and agreement",
            "Device description and intended use",
            "Summary technical documentation (STED)",
            "Non-clinical test data",
            "Clinical data (domestic or foreign)",
            "Manufacturing method and quality control",
            "Risk analysis (ISO 14971)",
            "JIS standard compliance documentation",
            "QMS ordinance compliance (ISO 13485 equivalent)",
            "Foreign manufacturer registration",
        ],
        "Certification": [
            "Application form (third-party certification body)",
            "DMAH appointment",
            "Device description and intended use",
            "Summary technical documentation (STED)",
            "Performance test data",
            "JIS standard compliance",
            "QMS compliance documentation",
        ],
        "Notification": [
            "Notification form submission",
            "Basic device description",
            "Conformity to relevant standards",
        ],
    },
    "australia": {
        "Conformity assessment": [
            "Application to include in ARTG",
            "Conformity assessment evidence (TGA audit or Notified Body)",
            "Device description and intended use",
            "Essential principles checklist (TGA)",
            "Clinical evidence (literature or clinical trials)",
            "Risk management documentation (ISO 14971)",
            "Quality management system evidence (ISO 13485)",
            "Manufacturing information",
            "Labeling (in English, TGA requirements)",
            "Unique device identifier (UDI)",
        ],
        "Self-assessment": [
            "Application to include in ARTG",
            "Device description",
            "Essential principles checklist",
            "Labeling",
            "Declaration of conformity",
        ],
    },
    "russia": {
        "Full registration (RZN)": [
            "Registration application (Roszdravnadzor portal)",
            "Authorised Representative (RU REP) appointment letter",
            "Device description and intended use (in Russian)",
            "Technical documentation",
            "Clinical investigation data or literature review",
            "Safety and effectiveness data",
            "ISO 13485 certificate",
            "Local laboratory testing in accredited Russian lab",
            "Manufacturing site inspection (Class 2b/3)",
            "Labeling in Russian",
            "Instructions for use in Russian",
            "Risk management file (GOST R ISO 14971)",
        ],
        "Simplified registration (RZN)": [
            "Registration application",
            "RU REP appointment",
            "Basic device description (in Russian)",
            "Local laboratory testing",
            "Labeling in Russian",
        ],
    },
}

def ai_gap_analysis(doc_text, device_data, selected_fws):
    """
    Compares uploaded submission document against required checklists.
    Returns per-framework gap analysis with present, missing, and partial items.
    """
    # Build the checklist context for selected frameworks
    checklist_context = []
    for fw in selected_fws:
        pathway = device_data[fw].get(PATHWAY_KEY.get(fw,""),"")
        fw_checklists = SUBMISSION_CHECKLISTS.get(fw,{})
        checklist = fw_checklists.get(pathway, list(fw_checklists.values())[0] if fw_checklists else [])
        if checklist:
            checklist_context.append(
                f"{FRAMEWORKS[fw]['label']} ({pathway}):\n" +
                "\n".join([f"  - {item}" for item in checklist])
            )

    prompt = f"""You are a senior regulatory affairs expert reviewing a medical device submission document.

Device being submitted: {device_data.get('device_name','Unknown')}
Intended use: {device_data.get('intended_use','--')}

SUBMISSION DOCUMENT CONTENT:
{doc_text[:4000]}

REQUIRED CHECKLISTS FOR EACH FRAMEWORK:
{chr(10).join(checklist_context)}

Analyse what is PRESENT, MISSING, or PARTIAL in this document for each framework.

Return ONLY valid JSON in exactly this structure:
{{
  "overall_completeness": "percentage as integer 0-100",
  "summary": "2-3 sentence overall assessment",
  "frameworks": {{
    "framework_key": {{
      "completeness_percent": 0,
      "present": ["items clearly present in document"],
      "missing": ["required items not found in document"],
      "partial": ["items mentioned but incomplete"],
      "priority_gaps": ["top 3 most critical missing items to address first"],
      "recommendation": "one sentence action recommendation"
    }}
  }}
}}

Use only these framework keys that are relevant: {list(selected_fws)}
Be specific - cite actual content from the document when marking items as present.
Return ONLY the JSON."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":prompt}],
        temperature=0.1,
        max_tokens=2000,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    return json.loads(raw.strip())

def show_gap_analysis_ui(device_data, selected_fws):
    """Renders the full gap analysis UI section."""
    st.subheader("Submission document gap analysis")
    st.caption(
        "Upload a draft submission document (510k, technical file, CDSCO dossier etc). "
        "The AI will compare it against the required checklist and show exactly what is missing."
    )

    uploaded_doc = st.file_uploader(
        "Upload submission document (PDF)",
        type=["pdf"],
        key="gap_analysis_uploader",
        help="Upload your draft regulatory submission document for gap analysis."
    )

    if uploaded_doc is not None:
        with st.spinner("Reading document..."):
            doc_text, page_count, success = extract_pdf_text(uploaded_doc, max_chars=4000)

        if not success or not doc_text.strip():
            st.warning("Could not extract text. Please use a text-based PDF.")
            return

        st.info(f"Document loaded: {page_count} pages, {len(doc_text)} characters extracted")

        if st.button("Run gap analysis", type="primary", key="run_gap_btn"):
            with st.spinner("Analysing document against regulatory checklists..."):
                try:
                    gap_result = ai_gap_analysis(doc_text, device_data, selected_fws)
                    st.session_state["gap_result"] = gap_result
                except Exception as e:
                    st.error(f"Gap analysis failed: {e}")
                    return

    # Display results if available
    if st.session_state.get("gap_result"):
        gap = st.session_state["gap_result"]

        # Overall completeness
        overall = int(gap.get("overall_completeness", 0))
        color   = "#1D9E75" if overall >= 70 else "#BA7517" if overall >= 40 else "#E24B4A"
        st.markdown(f"""
        <div style="background:var(--color-background-secondary);
                    border-radius:12px;padding:16px;margin:12px 0;
                    border:0.5px solid var(--color-border-tertiary)">
            <div style="font-size:13px;color:var(--color-text-secondary);margin-bottom:6px">
                Overall document completeness
            </div>
            <div style="font-size:32px;font-weight:500;color:{color}">{overall}%</div>
            <div style="font-size:13px;color:var(--color-text-secondary);margin-top:6px">
                {gap.get("summary","")}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Progress bar
        st.progress(overall / 100)
        st.divider()

        # Per-framework tabs
        fw_results = gap.get("frameworks", {})
        active_fws = [fw for fw in selected_fws if fw in fw_results]

        if active_fws:
            gap_tabs = st.tabs([FRAMEWORKS[fw]["label"] for fw in active_fws])
            for tab, fw in zip(gap_tabs, active_fws):
                with tab:
                    fw_gap = fw_results[fw]
                    pct    = int(fw_gap.get("completeness_percent", 0))
                    clr    = "#1D9E75" if pct >= 70 else "#BA7517" if pct >= 40 else "#E24B4A"

                    st.markdown(
                        f"<span style='color:{clr};font-weight:600;font-size:18px'>"
                        f"{pct}% complete</span>  "
                        f"<span style='color:var(--color-text-secondary);font-size:13px'>"
                        f"{fw_gap.get('recommendation','')}</span>",
                        unsafe_allow_html=True
                    )
                    st.progress(pct / 100)

                    col_a, col_b, col_c = st.columns(3)

                    with col_a:
                        present = fw_gap.get("present", [])
                        st.markdown(f"**Present ({len(present)})**")
                        for item in present:
                            st.markdown(
                                f"<span style='color:#1D9E75'>✓</span> {item}",
                                unsafe_allow_html=True
                            )

                    with col_b:
                        partial = fw_gap.get("partial", [])
                        st.markdown(f"**Partial ({len(partial)})**")
                        for item in partial:
                            st.markdown(
                                f"<span style='color:#BA7517'>~ </span> {item}",
                                unsafe_allow_html=True
                            )

                    with col_c:
                        missing = fw_gap.get("missing", [])
                        st.markdown(f"**Missing ({len(missing)})**")
                        for item in missing:
                            st.markdown(
                                f"<span style='color:#E24B4A'>✗</span> {item}",
                                unsafe_allow_html=True
                            )

                    # Priority gaps
                    priority = fw_gap.get("priority_gaps", [])
                    if priority:
                        st.markdown("---")
                        st.markdown("**Top priority gaps to address first:**")
                        for i, gap_item in enumerate(priority, 1):
                            st.markdown(
                                f"<div style='background:var(--color-background-secondary);"
                                f"border-left:3px solid #E24B4A;padding:6px 10px;"
                                f"border-radius:0 6px 6px 0;margin:4px 0;"
                                f"font-size:13px'>{i}. {gap_item}</div>",
                                unsafe_allow_html=True
                            )

        if st.button("Clear gap analysis", key="clear_gap"):
            st.session_state["gap_result"] = None
            st.rerun()


# ── TRACK 5: COST ESTIMATOR ───────────────────────────────────────────────────
REGULATORY_COSTS = {
    "cdsco": {
        "MD-5"  : {"govt_fees":500,   "testing":3000,  "consultant":5000,  "qms":2000},
        "MD-9"  : {"govt_fees":1500,  "testing":8000,  "consultant":12000, "qms":5000},
        "MD-14" : {"govt_fees":3000,  "testing":15000, "consultant":25000, "qms":10000},
    },
    "fda": {
        "Exempt"  : {"govt_fees":0,      "testing":5000,  "consultant":8000,  "qms":3000},
        "510(k)"  : {"govt_fees":26067,  "testing":40000, "consultant":50000, "qms":15000},
        "PMA"     : {"govt_fees":579272, "testing":250000,"consultant":350000,"qms":60000},
    },
    "eu": {
        "Basic UDI-DI"  : {"govt_fees":3000,  "testing":8000,  "consultant":12000, "qms":5000},
        "Full Tech File": {"govt_fees":25000, "testing":50000, "consultant":80000, "qms":25000},
    },
    "health_canada": {
        "MDEL only"     : {"govt_fees":300,   "testing":2000,  "consultant":4000,  "qms":1000},
        "Device Licence": {"govt_fees":5000,  "testing":20000, "consultant":30000, "qms":10000},
    },
    "japan": {
        "Notification" : {"govt_fees":2000,  "testing":10000, "consultant":15000, "qms":5000},
        "Certification": {"govt_fees":8000,  "testing":25000, "consultant":40000, "qms":12000},
        "Approval"     : {"govt_fees":25000, "testing":80000, "consultant":120000,"qms":30000},
    },
    "australia": {
        "Self-assessment"      : {"govt_fees":900,   "testing":5000,  "consultant":8000,  "qms":3000},
        "Conformity assessment": {"govt_fees":3500,  "testing":20000, "consultant":35000, "qms":12000},
    },
    "russia": {
        "Simplified registration (RZN)": {"govt_fees":2000,  "testing":8000,  "consultant":12000, "qms":3000},
        "Full registration (RZN)"      : {"govt_fees":6000,  "testing":25000, "consultant":40000, "qms":12000},
        "EAEU registration"            : {"govt_fees":8000,  "testing":30000, "consultant":50000, "qms":15000},
    },
}

def show_cost_estimator(data, selected_fws):
    st.subheader("Regulatory cost estimator")
    st.caption(
        "Approximate costs in USD across selected markets. "
        "Includes government fees, laboratory testing, consultant fees, and QMS setup. "
        "Actual costs vary significantly by device complexity and local requirements."
    )

    fw_labels, govt, testing, consult, qms_costs = [], [], [], [], []

    for fw in selected_fws:
        pathway   = data[fw].get(PATHWAY_KEY.get(fw,""),"")
        fw_costs  = REGULATORY_COSTS.get(fw,{})
        costs     = fw_costs.get(pathway, list(fw_costs.values())[0] if fw_costs else {})
        if not costs: continue

        fw_labels.append(FRAMEWORKS[fw]["label"])
        govt.append(costs.get("govt_fees",0))
        testing.append(costs.get("testing",0))
        consult.append(costs.get("consultant",0))
        qms_costs.append(costs.get("qms",0))

    if not fw_labels:
        st.info("No cost data available for selected frameworks.")
        return

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Govt / NB fees", x=fw_labels, y=govt,
                         marker_color="#378ADD"))
    fig.add_trace(go.Bar(name="Laboratory testing", x=fw_labels, y=testing,
                         marker_color="#1D9E75"))
    fig.add_trace(go.Bar(name="Consultant fees", x=fw_labels, y=consult,
                         marker_color="#8E44AD"))
    fig.add_trace(go.Bar(name="QMS setup", x=fw_labels, y=qms_costs,
                         marker_color="#E67E22"))
    fig.update_layout(
        barmode="stack",
        yaxis_title="Estimated cost (USD)",
        plot_bgcolor="white",
        height=400,
        margin=dict(t=30,b=20),
        yaxis=dict(gridcolor="#f0f0f0",tickformat="$,.0f"),
        legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),
    )
    st.plotly_chart(fig, use_container_width=True, key="cost_chart")

    # Summary table
    totals = [g+t+c+q for g,t,c,q in zip(govt,testing,consult,qms_costs)]
    cost_df = pd.DataFrame({
        "Market"           : fw_labels,
        "Govt/NB fees ($)" : [f"${v:,.0f}" for v in govt],
        "Testing ($)"      : [f"${v:,.0f}" for v in testing],
        "Consultant ($)"   : [f"${v:,.0f}" for v in consult],
        "QMS setup ($)"    : [f"${v:,.0f}" for v in qms_costs],
        "Total estimate ($)": [f"${v:,.0f}" for v in totals],
    })
    st.dataframe(cost_df, use_container_width=True, hide_index=True)

    cheapest = fw_labels[totals.index(min(totals))]
    costliest = fw_labels[totals.index(max(totals))]
    c1,c2 = st.columns(2)
    c1.success(f"Most affordable: **{cheapest}** (~${min(totals):,.0f})")
    c2.warning(f"Highest cost:    **{costliest}** (~${max(totals):,.0f})")
    st.warning(
        "**Cost disclaimer:** All figures are approximate indicative ranges for "
        "budget planning only. **FDA government fees are FY2026 standard rates** "
        "($26,067 for 510k; $579,272 for PMA — small businesses may qualify for "
        "75% reduction). **EU figures represent Notified Body fees** (not government "
        "fees — EU has no central regulatory fee). Consultant and testing costs vary "
        "widely by device complexity, geography, and firm. Do not use these figures "
        "for financial commitments. Always obtain formal quotes from regulatory "
        "consultants and testing laboratories.",
        icon="⚠️"
    )

# ── TRACK 5: GANTT CHART ──────────────────────────────────────────────────────
def show_gantt_chart(data, selected_fws):
    import datetime
    st.subheader("Regulatory submission timeline")
    st.caption(
        "Estimated project Gantt chart from submission start to market approval. "
        "Milestones are illustrative — actual timelines depend on agency workload and submission quality."
    )

    start_date = datetime.date.today()
    gantt_rows = []

    MILESTONES = {
        "cdsco": [
            ("Dossier preparation",      0,   3),
            ("CDSCO submission",         3,   1),
            ("Query response",           4,   2),
            ("Approval",                 6,   1),
        ],
        "fda": {
            "Exempt"  : [("Device labeling",0,1),("Registration",1,1),("Approval",2,1)],
            "510(k)"  : [("Dossier prep",0,4),("510k submission",4,1),("FDA review",5,3),("Clearance",8,1)],
            "PMA"     : [("IDE study",0,12),("PMA dossier",12,6),("PMA submission",18,1),("FDA review",19,12),("Approval",31,1)],
        },
        "eu": {
            "Basic UDI-DI"  : [("Tech file",0,2),("UDI registration",2,1),("CE Mark",3,1)],
            "Full Tech File": [("Tech file prep",0,6),("Notified Body audit",6,3),("Review",9,3),("CE Certificate",12,1)],
        },
        "health_canada": [
            ("Application prep",  0,  3),
            ("HC submission",     3,  1),
            ("HC review",         4,  5),
            ("Licence issued",    9,  1),
        ],
        "japan": {
            "Notification" : [("STED prep",0,2),("Notification",2,1),("Registration",3,1)],
            "Certification": [("STED prep",0,3),("Certification body",3,4),("Certificate",7,1)],
            "Approval"     : [("STED prep",0,6),("PMDA consultation",6,3),("Approval application",9,1),("PMDA review",10,12),("Approval",22,1)],
        },
        "australia": {
            "Self-assessment"      : [("Essential principles",0,2),("ARTG application",2,1),("ARTG listing",3,1)],
            "Conformity assessment": [("Tech file",0,4),("TGA audit",4,3),("ARTG inclusion",7,3),("Listed",10,1)],
        },
        "russia": {
            "Simplified registration (RZN)": [("RU REP appointment",0,1),("Local testing",1,3),("RZN application",4,1),("Registration",5,3)],
            "Full registration (RZN)"      : [("RU REP appointment",0,1),("ISO 13485",1,2),("Local testing",3,3),("Clinical data",6,3),("RZN application",9,1),("Roszdravnadzor review",10,6),("RZN certificate",16,1)],
            "EAEU registration"            : [("RU REP appointment",0,1),("Tech dossier",1,3),("EAEU submission",4,1),("Review",5,8),("EAEU certificate",13,1)],
        },
    }

    colors = {
        "cdsco":"#1D9E75","fda":"#378ADD","eu":"#D85A30",
        "health_canada":"#C0392B","japan":"#8E44AD",
        "australia":"#E67E22","russia":"#2C3E8C",
    }

    for fw in selected_fws:
        pathway    = data[fw].get(PATHWAY_KEY.get(fw,""),"")
        ms_data    = MILESTONES.get(fw,[])
        if isinstance(ms_data, dict):
            milestones = ms_data.get(pathway, list(ms_data.values())[0])
        else:
            milestones = ms_data

        for (task, offset_months, duration_months) in milestones:
            s = start_date + datetime.timedelta(days=int(offset_months*30.4))
            e = s + datetime.timedelta(days=max(1,int(duration_months*30.4)))
            gantt_rows.append({
                "Framework": FRAMEWORKS[fw]["label"],
                "Task"     : task,
                "Start"    : s.strftime("%Y-%m-%d"),
                "Finish"   : e.strftime("%Y-%m-%d"),
                "Color"    : colors.get(fw,"#888"),
            })

    if not gantt_rows:
        st.info("No timeline data available.")
        return

    df_gantt = pd.DataFrame(gantt_rows)
    import plotly.express as px
    fig = px.timeline(
        df_gantt,
        x_start="Start",
        x_end="Finish",
        y="Framework",
        color="Framework",
        hover_data=["Task"],
        color_discrete_map={FRAMEWORKS[fw]["label"]:colors[fw] for fw in selected_fws},
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        plot_bgcolor="white",
        height=max(300, len(selected_fws)*80),
        margin=dict(t=30,b=20,l=150),
        xaxis=dict(gridcolor="#f0f0f0"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, key="gantt_chart")

    # Milestone table
    st.markdown("**Key milestones**")
    mil_rows = []
    for fw in selected_fws:
        pathway    = data[fw].get(PATHWAY_KEY.get(fw,""),"")
        ms_data    = MILESTONES.get(fw,[])
        if isinstance(ms_data, dict):
            milestones = ms_data.get(pathway, list(ms_data.values())[0])
        else:
            milestones = ms_data
        for (task, offset, duration) in milestones:
            mil_date = start_date + datetime.timedelta(days=int(offset*30.4))
            mil_rows.append({
                "Market"   : FRAMEWORKS[fw]["label"],
                "Milestone": task,
                "Month"    : f"Month {offset+1}",
                "Est. date": mil_date.strftime("%b %Y"),
            })
    st.dataframe(pd.DataFrame(mil_rows), use_container_width=True, hide_index=True)



# ── TRACK 5: COST ESTIMATOR ───────────────────────────────────────────────────
REGULATORY_COSTS = {
    "cdsco": {
        "MD-5"  : {"govt_fees":500,   "testing":3000,  "consultant":5000,  "qms":2000},
        "MD-9"  : {"govt_fees":1500,  "testing":8000,  "consultant":12000, "qms":5000},
        "MD-14" : {"govt_fees":3000,  "testing":15000, "consultant":25000, "qms":10000},
    },
    "fda": {
        "Exempt"  : {"govt_fees":0,      "testing":5000,  "consultant":8000,  "qms":3000},
        "510(k)"  : {"govt_fees":26067,  "testing":40000, "consultant":50000, "qms":15000},
        "PMA"     : {"govt_fees":579272, "testing":250000,"consultant":350000,"qms":60000},
    },
    "eu": {
        "Basic UDI-DI"  : {"govt_fees":3000,  "testing":8000,  "consultant":12000, "qms":5000},
        "Full Tech File": {"govt_fees":25000, "testing":50000, "consultant":80000, "qms":25000},
    },
    "health_canada": {
        "MDEL only"     : {"govt_fees":300,   "testing":2000,  "consultant":4000,  "qms":1000},
        "Device Licence": {"govt_fees":5000,  "testing":20000, "consultant":30000, "qms":10000},
    },
    "japan": {
        "Notification" : {"govt_fees":2000,  "testing":10000, "consultant":15000, "qms":5000},
        "Certification": {"govt_fees":8000,  "testing":25000, "consultant":40000, "qms":12000},
        "Approval"     : {"govt_fees":25000, "testing":80000, "consultant":120000,"qms":30000},
    },
    "australia": {
        "Self-assessment"      : {"govt_fees":900,   "testing":5000,  "consultant":8000,  "qms":3000},
        "Conformity assessment": {"govt_fees":3500,  "testing":20000, "consultant":35000, "qms":12000},
    },
    "russia": {
        "Simplified registration (RZN)": {"govt_fees":2000,  "testing":8000,  "consultant":12000, "qms":3000},
        "Full registration (RZN)"      : {"govt_fees":6000,  "testing":25000, "consultant":40000, "qms":12000},
        "EAEU registration"            : {"govt_fees":8000,  "testing":30000, "consultant":50000, "qms":15000},
    },
}

def show_cost_estimator(data, selected_fws):
    st.subheader("Regulatory cost estimator")
    st.caption(
        "Approximate costs in USD across selected markets. "
        "Includes government fees, laboratory testing, consultant fees, and QMS setup. "
        "Actual costs vary significantly by device complexity and local requirements."
    )

    fw_labels, govt, testing, consult, qms_costs = [], [], [], [], []

    for fw in selected_fws:
        pathway   = data[fw].get(PATHWAY_KEY.get(fw,""),"")
        fw_costs  = REGULATORY_COSTS.get(fw,{})
        costs     = fw_costs.get(pathway, list(fw_costs.values())[0] if fw_costs else {})
        if not costs: continue

        fw_labels.append(FRAMEWORKS[fw]["label"])
        govt.append(costs.get("govt_fees",0))
        testing.append(costs.get("testing",0))
        consult.append(costs.get("consultant",0))
        qms_costs.append(costs.get("qms",0))

    if not fw_labels:
        st.info("No cost data available for selected frameworks.")
        return

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Govt / NB fees", x=fw_labels, y=govt,
                         marker_color="#378ADD"))
    fig.add_trace(go.Bar(name="Laboratory testing", x=fw_labels, y=testing,
                         marker_color="#1D9E75"))
    fig.add_trace(go.Bar(name="Consultant fees", x=fw_labels, y=consult,
                         marker_color="#8E44AD"))
    fig.add_trace(go.Bar(name="QMS setup", x=fw_labels, y=qms_costs,
                         marker_color="#E67E22"))
    fig.update_layout(
        barmode="stack",
        yaxis_title="Estimated cost (USD)",
        plot_bgcolor="white",
        height=400,
        margin=dict(t=30,b=20),
        yaxis=dict(gridcolor="#f0f0f0",tickformat="$,.0f"),
        legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),
    )
    st.plotly_chart(fig, use_container_width=True, key="cost_chart")

    # Summary table
    totals = [g+t+c+q for g,t,c,q in zip(govt,testing,consult,qms_costs)]
    cost_df = pd.DataFrame({
        "Market"           : fw_labels,
        "Govt/NB fees ($)" : [f"${v:,.0f}" for v in govt],
        "Testing ($)"      : [f"${v:,.0f}" for v in testing],
        "Consultant ($)"   : [f"${v:,.0f}" for v in consult],
        "QMS setup ($)"    : [f"${v:,.0f}" for v in qms_costs],
        "Total estimate ($)": [f"${v:,.0f}" for v in totals],
    })
    st.dataframe(cost_df, use_container_width=True, hide_index=True)

    cheapest = fw_labels[totals.index(min(totals))]
    costliest = fw_labels[totals.index(max(totals))]
    c1,c2 = st.columns(2)
    c1.success(f"Most affordable: **{cheapest}** (~${min(totals):,.0f})")
    c2.warning(f"Highest cost:    **{costliest}** (~${max(totals):,.0f})")
    st.warning(
        "**Cost disclaimer:** All figures are approximate indicative ranges for "
        "budget planning only. **FDA government fees are FY2026 standard rates** "
        "($26,067 for 510k; $579,272 for PMA — small businesses may qualify for "
        "75% reduction). **EU figures represent Notified Body fees** (not government "
        "fees — EU has no central regulatory fee). Consultant and testing costs vary "
        "widely by device complexity, geography, and firm. Do not use these figures "
        "for financial commitments. Always obtain formal quotes from regulatory "
        "consultants and testing laboratories.",
        icon="⚠️"
    )

# ── TRACK 5: GANTT CHART ──────────────────────────────────────────────────────
def show_gantt_chart(data, selected_fws):
    import datetime
    st.subheader("Regulatory submission timeline")
    st.caption(
        "Estimated project Gantt chart from submission start to market approval. "
        "Milestones are illustrative — actual timelines depend on agency workload and submission quality."
    )

    start_date = datetime.date.today()
    gantt_rows = []

    MILESTONES = {
        "cdsco": [
            ("Dossier preparation",      0,   3),
            ("CDSCO submission",         3,   1),
            ("Query response",           4,   2),
            ("Approval",                 6,   1),
        ],
        "fda": {
            "Exempt"  : [("Device labeling",0,1),("Registration",1,1),("Approval",2,1)],
            "510(k)"  : [("Dossier prep",0,4),("510k submission",4,1),("FDA review",5,3),("Clearance",8,1)],
            "PMA"     : [("IDE study",0,12),("PMA dossier",12,6),("PMA submission",18,1),("FDA review",19,12),("Approval",31,1)],
        },
        "eu": {
            "Basic UDI-DI"  : [("Tech file",0,2),("UDI registration",2,1),("CE Mark",3,1)],
            "Full Tech File": [("Tech file prep",0,6),("Notified Body audit",6,3),("Review",9,3),("CE Certificate",12,1)],
        },
        "health_canada": [
            ("Application prep",  0,  3),
            ("HC submission",     3,  1),
            ("HC review",         4,  5),
            ("Licence issued",    9,  1),
        ],
        "japan": {
            "Notification" : [("STED prep",0,2),("Notification",2,1),("Registration",3,1)],
            "Certification": [("STED prep",0,3),("Certification body",3,4),("Certificate",7,1)],
            "Approval"     : [("STED prep",0,6),("PMDA consultation",6,3),("Approval application",9,1),("PMDA review",10,12),("Approval",22,1)],
        },
        "australia": {
            "Self-assessment"      : [("Essential principles",0,2),("ARTG application",2,1),("ARTG listing",3,1)],
            "Conformity assessment": [("Tech file",0,4),("TGA audit",4,3),("ARTG inclusion",7,3),("Listed",10,1)],
        },
        "russia": {
            "Simplified registration (RZN)": [("RU REP appointment",0,1),("Local testing",1,3),("RZN application",4,1),("Registration",5,3)],
            "Full registration (RZN)"      : [("RU REP appointment",0,1),("ISO 13485",1,2),("Local testing",3,3),("Clinical data",6,3),("RZN application",9,1),("Roszdravnadzor review",10,6),("RZN certificate",16,1)],
            "EAEU registration"            : [("RU REP appointment",0,1),("Tech dossier",1,3),("EAEU submission",4,1),("Review",5,8),("EAEU certificate",13,1)],
        },
    }

    colors = {
        "cdsco":"#1D9E75","fda":"#378ADD","eu":"#D85A30",
        "health_canada":"#C0392B","japan":"#8E44AD",
        "australia":"#E67E22","russia":"#2C3E8C",
    }

    for fw in selected_fws:
        pathway    = data[fw].get(PATHWAY_KEY.get(fw,""),"")
        ms_data    = MILESTONES.get(fw,[])
        if isinstance(ms_data, dict):
            milestones = ms_data.get(pathway, list(ms_data.values())[0])
        else:
            milestones = ms_data

        for (task, offset_months, duration_months) in milestones:
            s = start_date + datetime.timedelta(days=int(offset_months*30.4))
            e = s + datetime.timedelta(days=max(1,int(duration_months*30.4)))
            gantt_rows.append({
                "Framework": FRAMEWORKS[fw]["label"],
                "Task"     : task,
                "Start"    : s.strftime("%Y-%m-%d"),
                "Finish"   : e.strftime("%Y-%m-%d"),
                "Color"    : colors.get(fw,"#888"),
            })

    if not gantt_rows:
        st.info("No timeline data available.")
        return

    df_gantt = pd.DataFrame(gantt_rows)
    import plotly.express as px
    fig = px.timeline(
        df_gantt,
        x_start="Start",
        x_end="Finish",
        y="Framework",
        color="Framework",
        hover_data=["Task"],
        color_discrete_map={FRAMEWORKS[fw]["label"]:colors[fw] for fw in selected_fws},
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        plot_bgcolor="white",
        height=max(300, len(selected_fws)*80),
        margin=dict(t=30,b=20,l=150),
        xaxis=dict(gridcolor="#f0f0f0"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, key="gantt_chart")

    # Milestone table
    st.markdown("**Key milestones**")
    mil_rows = []
    for fw in selected_fws:
        pathway    = data[fw].get(PATHWAY_KEY.get(fw,""),"")
        ms_data    = MILESTONES.get(fw,[])
        if isinstance(ms_data, dict):
            milestones = ms_data.get(pathway, list(ms_data.values())[0])
        else:
            milestones = ms_data
        for (task, offset, duration) in milestones:
            mil_date = start_date + datetime.timedelta(days=int(offset*30.4))
            mil_rows.append({
                "Market"   : FRAMEWORKS[fw]["label"],
                "Milestone": task,
                "Month"    : f"Month {offset+1}",
                "Est. date": mil_date.strftime("%b %Y"),
            })
    st.dataframe(pd.DataFrame(mil_rows), use_container_width=True, hide_index=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Regulatory Navigator")
    st.caption("7 global frameworks - Powered by Groq")
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

        # PDF auto-fill expander
        with st.expander("Upload device datasheet PDF (auto-fill)", expanded=False):
            uploaded_pdf = st.file_uploader(
                "Upload PDF", type=["pdf"],
                key="sidebar_pdf_uploader",
                label_visibility="collapsed",
                help="Upload any device spec sheet or IFU. "
                     "AI extracts the device name and description automatically."
            )
            if uploaded_pdf is not None:
                with st.spinner("Reading PDF..."):
                    pdf_text, page_count, success = extract_pdf_text(uploaded_pdf)
                if success and pdf_text.strip():
                    try:
                        extracted = ai_extract_device_info(pdf_text)
                        st.session_state["pdf_device_name"] = extracted.get("device_name","")
                        st.session_state["pdf_device_desc"] = (
                            extracted.get("intended_use","") + " " +
                            extracted.get("description","")
                        ).strip()
                        conf = extracted.get("confidence","Medium")
                        conf_color = {"High":"green","Medium":"orange","Low":"red"}
                        st.success(f"Extracted from {page_count}-page PDF")
                        st.markdown(
                            f"**{extracted.get('device_name','')}**  "
                            f"| :{conf_color.get(conf,'orange')}[{conf} confidence]"
                        )
                        st.caption(extracted.get("intended_use",""))
                    except Exception as e:
                        st.warning(f"Could not parse: {e}")
                else:
                    st.warning("No text found. Use a text-based PDF, not a scanned image.")

        device_name = st.text_input(
            "Device name",
            value=st.session_state.get("pdf_device_name",""),
            placeholder="e.g. Coronary Stent or upload PDF above"
        )
        device_desc = st.text_area(
            "Description (optional)",
            value=st.session_state.get("pdf_device_desc",""),
            height=80
        )
        if st.session_state.get("pdf_device_name"):
            if st.button("Clear PDF data", key="clear_pdf"):
                st.session_state["pdf_device_name"] = ""
                st.session_state["pdf_device_desc"] = ""
                st.rerun()

        if compare_mode:
            device_name2 = st.text_input("Device 2",placeholder="e.g. Pacemaker")
            device_desc2 = st.text_area("Description 2 (optional)",height=60)
        else:
            device_name2 = ""
            device_desc2 = ""

    else:
        device_name  = st.selectbox("Device 1",presets)
        device_desc  = ""
        if compare_mode:
            device_name2 = st.selectbox("Device 2",presets,index=1)
            device_desc2 = ""
        else:
            device_name2 = ""
            device_desc2 = ""

    st.subheader("Target markets")
    cols_sb = st.columns(2)
    checks = {
        "cdsco"        :cols_sb[0].checkbox("India (CDSCO)",   value=True),
        "fda"          :cols_sb[1].checkbox("USA (FDA)",        value=True),
        "eu"           :cols_sb[0].checkbox("Europe (CE Mark)", value=True),
        "health_canada":cols_sb[1].checkbox("Canada",          value=True),
        "japan"        :cols_sb[0].checkbox("Japan (PMDA)",    value=True),
        "australia"    :cols_sb[1].checkbox("Australia (TGA)", value=True),
        "russia"       :cols_sb[0].checkbox("Russia (RZN)",    value=False),
    }
    selected_fws = [fw for fw,checked in checks.items() if checked]
    st.divider()
    analyse = st.button("Analyse Device",type="primary",use_container_width=True)

    if st.session_state.search_history:
        st.divider(); st.subheader("History")
        for i,h in enumerate(reversed(st.session_state.search_history[-5:])):
            if st.button(
                f"{h['device']} - {h['cdsco_class']}/{h['fda_class']}/{h['eu_class']}",
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
st.markdown("## MedTech Regulatory Pathway Navigator")
st.markdown("*AI-powered classification across 7 global regulatory frameworks*")
st.divider()

# ── CHATBOT QUEUE PROCESSOR — pure Python, zero st.* calls ───────────────────
if st.session_state.get("_queued_question") and st.session_state.get("_queued_device"):
    _q   = st.session_state["_queued_question"]
    _ctx = st.session_state["_queued_device"]
    st.session_state["_queued_question"] = None
    st.session_state["_queued_device"]   = None
    try:
        _answer = regulatory_chat(str(_q), _ctx)
    except Exception as _err:
        _answer = f"Error: {str(_err)}"
    st.session_state["chat_history"].append({"question":str(_q),"answer":_answer})
    st.session_state["chat_input_counter"] += 1

# ── Load classification data ──────────────────────────────────────────────────
if "reload_data" in st.session_state:
    data=st.session_state.pop("reload_data"); data2=None; analyse_show=True
    st.session_state["last_data"]=data
    st.session_state["last_data2"]=None
    st.session_state["last_fws"]=selected_fws
    st.session_state["last_compare"]=False
    st.session_state["current_device"]=data
    st.session_state["chat_history"]=[]
elif analyse and device_name.strip():
    analyse_show=True
    with st.spinner(f"Classifying {device_name}..."):
        try:
            data=ai_classify_device(device_name.strip(),device_desc.strip())
        except Exception as e:
            st.error(f"Classification failed: {e}"); st.stop()
    data2=None
    if compare_mode and device_name2.strip():
        with st.spinner(f"Classifying {device_name2}..."):
            try:
                data2=ai_classify_device(device_name2.strip(),device_desc2.strip())
            except Exception as e:
                st.error(f"Device 2 failed: {e}"); data2=None
    st.session_state["chat_history"]=[]
    st.session_state["current_device"]=data
    st.session_state["last_data"]=data
    st.session_state["last_data2"]=data2
    st.session_state["last_fws"]=list(selected_fws)
    st.session_state["last_compare"]=bool(compare_mode and data2 is not None)
    st.session_state.search_history.append({
        "device":data["device_name"],"confidence":data.get("confidence","--"),
        "cdsco_class":data["cdsco"]["risk_class"],
        "fda_class":data["fda"]["risk_class"],
        "eu_class":data["eu"]["risk_class"],"data":data,
    })
elif analyse and not device_name.strip():
    st.warning("Please enter a device name first.")
    data=st.session_state.get("last_data")
    data2=st.session_state.get("last_data2")
    selected_fws=st.session_state.get("last_fws") or selected_fws
    analyse_show=data is not None
else:
    data=st.session_state.get("last_data")
    data2=st.session_state.get("last_data2")
    selected_fws=st.session_state.get("last_fws") or selected_fws
    analyse_show=data is not None

# ── Results ───────────────────────────────────────────────────────────────────
if analyse_show and data:
    if compare_mode and data2:
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
            vals1=[risk_score.get(RISK_LEVEL.get(data[fw].get("risk_class",""),"Unknown"),0)
                   for fw in selected_fws]
            vals2=[risk_score.get(RISK_LEVEL.get(data2[fw].get("risk_class",""),"Unknown"),0)
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
                h2h["D1 class"].append(data[fw].get("risk_class","--"))
                h2h["D1 timeline"].append(f"{t1} mo")
                h2h["D2 class"].append(data2[fw].get("risk_class","--"))
                h2h["D2 timeline"].append(f"{t2} mo")
                h2h["Faster entry"].append(
                    data["device_name"] if t1<=t2 else data2["device_name"])
            st.dataframe(pd.DataFrame(h2h),use_container_width=True,hide_index=True)
        st.divider()
        ex1,ex2=st.columns([1,3])
        with ex1:
            pdf_bytes=generate_pdf(data,selected_fws,data2,selected_fws)
            st.download_button("Download comparison PDF",data=pdf_bytes,
                file_name="comparison_report.pdf",mime="application/pdf",
                type="primary",use_container_width=True)
        with ex2:
            st.caption("Full comparison -- both devices, all frameworks.")
    else:
        show_device_results(data,selected_fws,prefix="single")
        ex1,ex2=st.columns([1,3])
        with ex1:
            pdf_bytes=generate_pdf(data,selected_fws)
            st.download_button("Download PDF",data=pdf_bytes,
                file_name=f"{data['device_name'].replace(' ','_')}_report.pdf",
                mime="application/pdf",type="primary",use_container_width=True)
        with ex2:
            st.caption(f"Full pathway -- {len(selected_fws)} markets, all details.")

    st.divider()

    # ── CHATBOT ───────────────────────────────────────────────────────────────
    st.subheader("Ask the regulatory AI")
    st.caption(f"Context-aware Q&A about **{data['device_name']}**")

    suggestions = [
        "What documents do I need to prepare first?",
        "Which market should I enter first and why?",
        "What is the estimated total regulatory cost?",
        "What clinical evidence is needed?",
        "What ISO standards apply to this device?",
        "Walk me through submission for the fastest market",
    ]
    st.markdown("**Quick questions:**")
    qc1,qc2,qc3 = st.columns(3)
    qcols=[qc1,qc2,qc3]
    for idx,sug in enumerate(suggestions):
        if qcols[idx%3].button(sug,key=f"qbtn_{idx}",use_container_width=True):
            st.session_state["_queued_question"] = sug
            st.session_state["_queued_device"]   = st.session_state.get("current_device")
            st.rerun()

    st.markdown("**Or type your own:**")
    inp_col,btn_col = st.columns([5,1])
    typed_q = inp_col.text_input(
        "q_input",label_visibility="collapsed",
        placeholder="e.g. What authorised rep do I need for Russia?",
        key=f"chat_text_{st.session_state.chat_input_counter}"
    )
    if btn_col.button("Send",key="send_btn",type="primary"):
        if typed_q.strip():
            st.session_state["_queued_question"] = typed_q.strip()
            st.session_state["_queued_device"]   = st.session_state.get("current_device")
            st.rerun()

    if st.session_state.chat_history:
        st.markdown("---")
        for turn in reversed(st.session_state.chat_history):
            with st.chat_message("user"):
                st.markdown(turn["question"])
            with st.chat_message("assistant"):
                st.markdown(turn["answer"])
        if st.button("Clear conversation",key="clear_chat"):
            st.session_state["chat_history"]=[]
            st.session_state["chat_input_counter"]+=1
            st.rerun()
    else:
        st.info("Click a quick question or type your own and press Send.")

    st.divider()

    # ── Gap analysis ──────────────────────────────────────────────────────────
    show_gap_analysis_ui(data, selected_fws)

    st.divider()

    # ── Cost estimator ────────────────────────────────────────────────────────
    show_cost_estimator(data, selected_fws)

    st.divider()

    # ── Gantt chart ───────────────────────────────────────────────────────────
    show_gantt_chart(data, selected_fws)

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
    2. Or upload a device PDF to auto-fill the form
    3. Select your target markets
    4. Click **Analyse Device**
    5. Ask follow-up questions in the Q&A panel below

    #### 7 frameworks covered
    | Market | Framework | Classes |
    |--------|-----------|---------|
    | India | CDSCO MDR 2017 | A / B / C / D |
    | USA | FDA 21 CFR | I / II / III |
    | Europe | EU MDR 2017/745 | I / IIa / IIb / III |
    | Canada | Health Canada SOR/98-282 | I / II / III / IV |
    | Japan | PMDA Yakuji Ho | I / II / III / IV |
    | Australia | TGA ARTG | I / IIa / IIb / III |
    | Russia | Roszdravnadzor Decree No.1684 | 1 / 2a / 2b / 3 |

    #### Try these
    - Coronary Stent - Total Knee Replacement
    - Smart insulin pen - AI retinal scanner
    - Upload a device spec sheet PDF to auto-classify
    """)
