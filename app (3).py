
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
    df_cdsco = pd.read_excel("data/regulatory_rules.xlsx", sheet_name="CDSCO")
    df_fda   = pd.read_excel("data/regulatory_rules.xlsx", sheet_name="FDA")
    df_eu    = pd.read_excel("data/regulatory_rules.xlsx", sheet_name="EU_MDR")
    return df_cdsco, df_fda, df_eu

df_cdsco, df_fda, df_eu = load_data()

# ── Helpers ──────────────────────────────────────────────────────────────────
def classify_device(device_name):
    return (df_cdsco.loc[df_cdsco["device_type"]==device_name].iloc[0],
            df_fda.loc[df_fda["device_type"]==device_name].iloc[0],
            df_eu.loc[df_eu["device_type"]==device_name].iloc[0])

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

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/dna-helix.png", width=60)
    st.title("Navigator")
    st.caption("MDR 2017 · FDA 21 CFR · EU MDR 2017/745")
    st.divider()

    all_devices = sorted(df_cdsco["device_type"].tolist())
    selected_device = st.selectbox("Device Type", all_devices, index=5)

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
st.info(f"**{selected_device}** — Intended use: *{cdsco_row['intended_use']}*")

# ── Risk classification ───────────────────────────────────────────────────────
st.subheader("Risk Classification")
col1, col2, col3 = st.columns(3)

for col, row, label, framework in [
    (col1, cdsco_row, "CDSCO (India)", "CDSCO"),
    (col2, fda_row,   "FDA (USA)",     "FDA"),
    (col3, eu_row,    "EU MDR (Europe)","EU")
]:
    lvl   = get_risk_level(row["risk_class"])
    color = get_risk_color(lvl)
    with col:
        st.metric(label, row["risk_class"])
        st.markdown(
            f"<span class='risk-badge' style='background:{color}22;color:{color}'>{lvl} Risk</span>",
            unsafe_allow_html=True
        )

st.divider()

# ── UPGRADE 2: Timeline chart with reference line ─────────────────────────────
st.subheader("Approval Timeline Comparison")

markets, months, colors = [], [], []
cmap = {"CDSCO (India)":"#1D9E75","FDA (USA)":"#378ADD","CE Mark (EU)":"#D85A30"}

if show_cdsco: markets.append("CDSCO (India)"); months.append(int(cdsco_row["timeline_months"])); colors.append(cmap["CDSCO (India)"])
if show_fda:   markets.append("FDA (USA)");     months.append(int(fda_row["timeline_months"]));   colors.append(cmap["FDA (USA)"])
if show_eu:    markets.append("CE Mark (EU)");  months.append(int(eu_row["timeline_months"]));    colors.append(cmap["CE Mark (EU)"])

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
                st.markdown(f"- License type: `{cdsco_row['license_type']}`")
                st.markdown(f"- Timeline: **{cdsco_row['timeline_months']} months**")
                st.markdown(f"- QMS required: {cdsco_row['qms_required']}")
                st.markdown(f"- Clinical data: {cdsco_row['clinical_data_required']}")
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
                st.markdown(f"- Pathway: `{fda_row['pathway']}`")
                st.markdown(f"- Timeline: **{fda_row['timeline_months']} months**")
                st.markdown(f"- Predicate needed: {fda_row['predicate_needed']}")
                st.markdown(f"- Clinical trials: {fda_row['clinical_trials_required']}")
                st.markdown(f"- IDE required: {fda_row['ide_required']}")
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
                st.markdown(f"- Tech file: `{eu_row['technical_file_type']}`")
                st.markdown(f"- Timeline: **{eu_row['timeline_months']} months**")
                st.markdown(f"- Notified body: {eu_row['notified_body_needed']}")
                st.markdown(f"- Clinical eval: {eu_row['clinical_evaluation_required']}")
                st.markdown(f"- PMCF required: {eu_row['pmcf_required']}")
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
    "CDSCO (India)"  : [cdsco_row["risk_class"], cdsco_row["license_type"],
                         cdsco_row["timeline_months"], cdsco_row["qms_required"],
                         cdsco_row["clinical_data_required"], "N/A"],
    "FDA (USA)"      : [fda_row["risk_class"], fda_row["pathway"],
                         fda_row["timeline_months"], "Yes (21 CFR 820)",
                         fda_row["clinical_trials_required"], fda_row["ide_required"]],
    "CE Mark (EU)"   : [eu_row["risk_class"], eu_row["technical_file_type"],
                         eu_row["timeline_months"], "Yes (ISO 13485)",
                         eu_row["clinical_evaluation_required"], eu_row["notified_body_needed"]]
}
st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    "<div class=\'footer\'>Data sources: CDSCO MDR 2017 | FDA 21 CFR | "
    "EU MDR 2017/745 | ISO 13485 | Built with Python + Streamlit + Plotly</div>",
    unsafe_allow_html=True
)
