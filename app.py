
import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

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

# ── Load data ────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    path = "data/regulatory_rules.xlsx"
    if not os.path.exists(path):
        st.error(f"Data file not found: {path}. Please add the Excel workbook to the `data/` folder.")
        st.stop()
    try:
        df_cdsco = pd.read_excel(path, sheet_name="CDSCO")
        df_fda = pd.read_excel(path, sheet_name="FDA")
        df_eu = pd.read_excel(path, sheet_name="EU_MDR")
    except Exception as e:
        st.error(f"Failed to read Excel file: {e}")
        st.stop()

    # Ensure a `device_type` column exists (fallback: use first column)
    for df in (df_cdsco, df_fda, df_eu):
        if "device_type" not in df.columns and len(df.columns) > 0:
            df.rename(columns={df.columns[0]: "device_type"}, inplace=True)

    return df_cdsco, df_fda, df_eu

df_cdsco, df_fda, df_eu = load_data()

# ── Helpers ──────────────────────────────────────────────────────────────────
def classify_device(device_name):
    def get_row(df):
        if df is None or df.empty:
            return pd.Series()
        matches = df.loc[df["device_type"] == device_name]
        if not matches.empty:
            return matches.iloc[0]
        # fallback to first row with a warning
        st.warning(f"Device '{device_name}' not found in dataset; using first available row as fallback.")
        return df.iloc[0]

    return get_row(df_cdsco), get_row(df_fda), get_row(df_eu)


def get_val(row, key, default="N/A"):
    try:
        if hasattr(row, 'get'):
            return row.get(key, default)
        return default
    except Exception:
        return default


def to_int(val, default=0):
    try:
        return int(val)
    except Exception:
        try:
            return int(float(val))
        except Exception:
            return default

def get_risk_level(risk_class):
    return {"A":"Low","B":"Medium","C":"High","D":"Critical",
            "I":"Low","II":"Medium","III":"Critical",
            "IIa":"Medium","IIb":"High"}.get(risk_class,"Unknown")

def get_risk_color(level):
    return {"Low":"#1D9E75","Medium":"#BA7517",
            "High":"#D85A30","Critical":"#E24B4A"}.get(level,"#888")

def build_requirements(row, framework):
    if framework == "CDSCO":
        reqs = ["Form MD-1 application","Device Master File",
                "ISO 13485 certificate" if row["qms_required"]=="Yes" else "Basic QMS docs",
                "NABL/BIS lab test reports"]
        if row["clinical_data_required"]=="Yes": reqs.append("Clinical performance data")
        if row["risk_class"] in ["C","D"]:
            reqs += ["Free Sale Certificate","Manufacturer undertaking"]
    elif framework == "FDA":
        reqs = ["Device description & intended use",
                "Predicate comparison" if row["predicate_needed"]=="Yes" else "Safety & effectiveness data",
                "Performance testing","Labeling (21 CFR Part 801)","QSR (21 CFR Part 820)"]
        if row["clinical_trials_required"]=="Yes": reqs.append("Clinical trial data + IDE")
        if row["pathway"]=="PMA": reqs.append("Full PMA safety dossier")
    else:
        reqs = ["Technical documentation (Annex II/III)",
                "Declaration of Conformity","UDI in EUDAMED","PMS plan"]
        if row["notified_body_needed"]=="Yes":
            reqs += ["Notified Body assessment","ISO 13485 audit"]
        if row["clinical_evaluation_required"]=="Yes": reqs.append("Clinical Evaluation Report (CER)")
        if row["pmcf_required"]=="Yes": reqs.append("PMCF plan")
    return reqs


def normalize_text(text):
    return (text or "").strip().lower()


def build_ai_response(question, selected_device, cdsco_row, fda_row, eu_row):
    question = normalize_text(question)
    if not question:
        return "Please ask a question about risk class, approval timeline, pathway choice, or submission requirements."

    device_info = f"Device: {selected_device}. "
    cdsco_risk = get_val(cdsco_row, "risk_class", "unknown")
    fda_risk = get_val(fda_row, "risk_class", "unknown")
    eu_risk = get_val(eu_row, "risk_class", "unknown")
    cdsco_timeline = get_val(cdsco_row, "timeline_months", "unknown")
    fda_timeline = get_val(fda_row, "timeline_months", "unknown")
    eu_timeline = get_val(eu_row, "timeline_months", "unknown")

    if any(term in question for term in ["risk", "classification", "class"]):
        return (
            f"For {selected_device}, the CDSCO risk class is {cdsco_risk}, FDA class is {fda_risk}, "
            f"and EU MDR class is {eu_risk}. "
            "Use this to compare safety, clinical data, and regulatory oversight requirements."
        )

    if any(term in question for term in ["timeline", "months", "approval time", "duration"]):
        return (
            f"Expected review timelines are: CDSCO {cdsco_timeline} months, FDA {fda_timeline} months, "
            f"CE Mark {eu_timeline} months. "
            "The shortest path is usually the most predictable but depends on your chosen market and submission type."
        )

    if any(term in question for term in ["checklist", "documents", "submission", "requirements"]):
        cdsco_reqs = build_requirements(cdsco_row, "CDSCO") if get_val(cdsco_row, "device_type", None) else []
        fda_reqs = build_requirements(fda_row, "FDA") if get_val(fda_row, "device_type", None) else []
        eu_reqs = build_requirements(eu_row, "EU") if get_val(eu_row, "device_type", None) else []
        return (
            f"CDSCO checklist: {', '.join(cdsco_reqs[:4])}. "
            f"FDA checklist: {', '.join(fda_reqs[:4])}. "
            f"EU MDR checklist: {', '.join(eu_reqs[:4])}. "
            "Ask for more detail on any specific market if needed."
        )

    if any(term in question for term in ["pathway", "510(k)", "pma", "md-1", "ce mark", "ce"]):
        return (
            f"Recommended pathways for {selected_device}: CDSCO license type {get_val(cdsco_row, 'license_type', 'N/A')}, "
            f"FDA pathway {get_val(fda_row, 'pathway', 'N/A')}, EU technical file {get_val(eu_row, 'technical_file_type', 'N/A')}. "
            "Select the market where your device and claims best align to minimize approval risk."
        )

    return (
        f"{device_info} I can help you compare risk class, timeline, and required documentation across CDSCO, FDA, and EU MDR. "
        "Try asking: 'What is the approval timeline?', 'What documents do I need?', or 'What is the risk class?'"
    )


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/dna-helix.png", width=60)
    st.title("Navigator")
    st.caption("MDR 2017 · FDA 21 CFR · EU MDR 2017/745")
    st.divider()

    all_devices = sorted(list(pd.Series(df_cdsco.get("device_type", [])).dropna().unique())) if not df_cdsco.empty else []
    if not all_devices:
        all_devices = ["(No devices available)"]
    default_index = 5 if len(all_devices) > 5 else max(0, len(all_devices) - 1)
    selected_device = st.selectbox("Device Type", all_devices, index=default_index)

    st.subheader("Target Markets")
    show_cdsco = st.checkbox("🇮🇳 India (CDSCO)", value=True)
    show_fda   = st.checkbox("🇺🇸 USA (FDA)",     value=True)
    show_eu    = st.checkbox("🇪🇺 Europe (CE Mark)",value=True)

    st.divider()
    st.subheader("About this tool")
    st.caption("""
    Encodes 3 major regulatory frameworks
    into a single decision-support tool.
    Reduces pathway scoping from hours to
    minutes. Built with Python + Streamlit.
    """)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("## 🧬 MedTech Regulatory Pathway Navigator")
st.markdown(
    "Instantly identify the optimal regulatory pathway for any medical device "
    "across **CDSCO (India)**, **FDA 510(k)/PMA (USA)**, and **CE Mark (EU MDR)**."
)
st.divider()

cdsco_row, fda_row, eu_row = classify_device(selected_device)

# ── UPGRADE 1: Intended use info box ─────────────────────────────────────────
st.info(f"**{selected_device}** — Intended use: *{get_val(cdsco_row, 'intended_use', '—')}*")

# ── Risk classification ───────────────────────────────────────────────────────
st.subheader("Risk Classification")
col1, col2, col3 = st.columns(3)

for col, row, label, framework in [
    (col1, cdsco_row, "CDSCO (India)", "CDSCO"),
    (col2, fda_row,   "FDA (USA)",     "FDA"),
    (col3, eu_row,    "EU MDR (Europe)","EU")
]:
    lvl   = get_risk_level(get_val(row, "risk_class", "Unknown"))
    color = get_risk_color(lvl)
    with col:
        st.metric(label, get_val(row, "risk_class", "Unknown"))
        st.markdown(
            f"<span class='risk-badge' style='background:{color}22;color:{color}'>{lvl} Risk</span>",
            unsafe_allow_html=True
        )

st.divider()

# ── UPGRADE 2: Timeline chart with reference line ─────────────────────────────
st.subheader("Approval Timeline Comparison")

markets, months, colors = [], [], []
cmap = {"CDSCO (India)":"#1D9E75","FDA (USA)":"#378ADD","CE Mark (EU)":"#D85A30"}

if show_cdsco:
    markets.append("CDSCO (India)")
    months.append(to_int(get_val(cdsco_row, "timeline_months", 0)))
    colors.append(cmap["CDSCO (India)"])
if show_fda:
    markets.append("FDA (USA)")
    months.append(to_int(get_val(fda_row, "timeline_months", 0)))
    colors.append(cmap["FDA (USA)"])
if show_eu:
    markets.append("CE Mark (EU)")
    months.append(to_int(get_val(eu_row, "timeline_months", 0)))
    colors.append(cmap["CE Mark (EU)"])

if markets:
    fig = go.Figure(go.Bar(
        x=markets, y=months,
        marker_color=colors,
        text=[f"{m} months" for m in months],
        textposition="outside"
    ))
    # UPGRADE 2: Add average reference line
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

# ── UPGRADE 3: Tabbed pathway details ────────────────────────────────────────
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
                st.markdown("**Key Details**")
                st.markdown(f"- License type: `{get_val(cdsco_row, 'license_type', 'N/A')}`")
                st.markdown(f"- Timeline: **{get_val(cdsco_row, 'timeline_months', 'N/A')} months**")
                st.markdown(f"- QMS required: {get_val(cdsco_row, 'qms_required', 'N/A')}")
                st.markdown(f"- Clinical data: {get_val(cdsco_row, 'clinical_data_required', 'N/A')}")
            with c2:
                st.markdown("**Submission Checklist**")
                for req in build_requirements(cdsco_row, "CDSCO"):
                    st.markdown(f"☐ {req}")
        tab_idx += 1

    if show_fda:
        with tabs[tab_idx]:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Key Details**")
                st.markdown(f"- Pathway: `{get_val(fda_row, 'pathway', 'N/A')}`")
                st.markdown(f"- Timeline: **{get_val(fda_row, 'timeline_months', 'N/A')} months**")
                st.markdown(f"- Predicate needed: {get_val(fda_row, 'predicate_needed', 'N/A')}")
                st.markdown(f"- Clinical trials: {get_val(fda_row, 'clinical_trials_required', 'N/A')}")
                st.markdown(f"- IDE required: {get_val(fda_row, 'ide_required', 'N/A')}")
            with c2:
                st.markdown("**Submission Checklist**")
                for req in build_requirements(fda_row, "FDA"):
                    st.markdown(f"☐ {req}")
        tab_idx += 1

    if show_eu:
        with tabs[tab_idx]:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Key Details**")
                st.markdown(f"- Tech file: `{get_val(eu_row, 'technical_file_type', 'N/A')}`")
                st.markdown(f"- Timeline: **{get_val(eu_row, 'timeline_months', 'N/A')} months**")
                st.markdown(f"- Notified body: {get_val(eu_row, 'notified_body_needed', 'N/A')}")
                st.markdown(f"- Clinical eval: {get_val(eu_row, 'clinical_evaluation_required', 'N/A')}")
                st.markdown(f"- PMCF required: {get_val(eu_row, 'pmcf_required', 'N/A')}")
            with c2:
                st.markdown("**Submission Checklist**")
                for req in build_requirements(eu_row, "EU"):
                    st.markdown(f"☐ {req}")

st.divider()

# ── UPGRADE 4: Full comparison summary table ──────────────────────────────────
st.subheader("Side-by-Side Summary")

summary_data = {
    "Parameter"      : ["Risk Class","Pathway/License","Timeline (months)",
                         "QMS / ISO 13485","Clinical Data","Notified Body / IDE"],
    "CDSCO (India)"  : [get_val(cdsco_row, "risk_class", "N/A"), get_val(cdsco_row, "license_type", "N/A"),
                         get_val(cdsco_row, "timeline_months", "N/A"), get_val(cdsco_row, "qms_required", "N/A"),
                         get_val(cdsco_row, "clinical_data_required", "N/A"), "N/A"],
    "FDA (USA)"      : [get_val(fda_row, "risk_class", "N/A"), get_val(fda_row, "pathway", "N/A"),
                         get_val(fda_row, "timeline_months", "N/A"), "Yes (21 CFR 820)",
                         get_val(fda_row, "clinical_trials_required", "N/A"), get_val(fda_row, "ide_required", "N/A")],
    "CE Mark (EU)"   : [get_val(eu_row, "risk_class", "N/A"), get_val(eu_row, "technical_file_type", "N/A"),
                         get_val(eu_row, "timeline_months", "N/A"), "Yes (ISO 13485)",
                         get_val(eu_row, "clinical_evaluation_required", "N/A"), get_val(eu_row, "notified_body_needed", "N/A")]
}
st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

# ── Chatbot ──────────────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "role": "assistant",
            "content": (
                "Hello! I am the MedTech Regulatory Navigator. Ask me about risk class, approval timeline, "
                "submission requirements, or the best pathway for the selected device."
            )
        }
    ]

with st.expander("Chat with the Navigator", expanded=True):
    message_fn = getattr(st, "chat_message", None)
    for message in st.session_state.chat_history:
        if message_fn is not None:
            message_fn(message["role"]).write(message["content"])
        else:
            st.markdown(f"**{message['role'].title()}:** {message['content']}")

    if hasattr(st, "chat_input"):
        user_input = st.chat_input("Ask a question about this device")
        input_key = None
    else:
        input_key = "chat_text_input"
        user_input = st.text_input("Ask a question about this device", key=input_key)

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        answer = build_ai_response(user_input, selected_device, cdsco_row, fda_row, eu_row)
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
        if input_key:
            st.session_state[input_key] = ""
        st.experimental_rerun()

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    "<div class='footer'>Data sources: CDSCO MDR 2017 | FDA 21 CFR | "
    "EU MDR 2017/745 | ISO 13485 | Built with Python + Streamlit + Plotly</div>",
    unsafe_allow_html=True
)
