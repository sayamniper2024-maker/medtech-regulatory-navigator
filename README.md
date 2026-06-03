# 🧬 MedTech Regulatory Pathway Navigator

> AI-powered decision-support tool that recommends the optimal regulatory pathway
> for **any medical device in the world** across **6 major global regulatory frameworks**.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://medtech-regulatory-navigator-e7khygzx9hreudkxtfdk2x.streamlit.app/)
![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-red?logo=streamlit)
![AI Powered](https://img.shields.io/badge/AI-Groq%20LLaMA%203.3-purple)
![License]

---

## What it does

Medical device companies spend hours manually researching regulatory pathways
before starting any market entry project. This tool encodes **6 major regulatory
frameworks** into a single AI-powered interface that returns a full pathway
recommendation in under 10 seconds — for **any medical device ever invented**.

**Input:** Any medical device name + optional description  
**Output:**
- Risk classification across all 6 global frameworks simultaneously
- Recommended pathway (e.g. 510k, PMA, MD-9, CE Mark IIb, ARTG, DMAH)
- Estimated approval timeline per market with visual comparison chart
- Submission document checklist per framework
- Fastest vs slowest market entry recommendation
- Side-by-side comparison table across all selected markets

---

## 🌐 Live Demo

**Try it here → [medtech-regulatory-navigator.streamlit.app](https://medtech-regulatory-navigator-e7khygzx9hreudkxtfdk2x.streamlit.app/)**

Example devices to try:
- `Smart insulin pen with dose tracking`
- `AI-powered retinal screening camera`
- `Robotic surgical assistant arm`
- `Wearable continuous glucose monitor`
- `Neural implant for Parkinson tremor`
- `Biodegradable bone scaffold`
- `AI-powered ECG arrhythmia detector`

---

## 🌍 6 Regulatory Frameworks Covered

| Flag | Market | Framework | Classification System |
|------|--------|-----------|----------------------|
| 🇮🇳 | India | CDSCO MDR 2017 | Class A / B / C / D |
| 🇺🇸 | USA | FDA 21 CFR Parts 862-892 | Class I / II / III + Exempt / 510(k) / PMA |
| 🇪🇺 | Europe | EU MDR 2017/745 | Class I / IIa / IIb / III |
| 🇨🇦 | Canada | Health Canada SOR/98-282 | Class I / II / III / IV + MDEL |
| 🇯🇵 | Japan | PMDA Yakuji Ho (PMD Act) | Class I / II / III / IV + DMAH |
| 🇦🇺 | Australia | TGA ARTG (TGO 2002) | Class I / IIa / IIb / III / AIMD |

---

## ⚙️ Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.11 | Core language |
| Streamlit | Web UI — no HTML/CSS needed |
| Pandas | Data handling and Excel rule sets |
| Plotly | Interactive timeline comparison charts |
| Groq API (LLaMA 3.3 70B) | AI-powered device classification engine |
| Excel (openpyxl) | Structured regulatory rule sets — 6 frameworks |

---

## 🏗️ Project Structure

```
medtech-regulatory-navigator/
├── app.py                      # Main Streamlit application
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation
└── data/
    └── regulatory_rules.xlsx  # Encoded regulatory rule sets (6 sheets)
```

---

## 🚀 Run Locally

```bash
git clone https://github.com/sayamniper2024-maker/medtech-regulatory-navigator
cd medtech-regulatory-navigator
pip install -r requirements.txt
streamlit run app.py
```

Set your Groq API key as an environment variable:

```bash
# Mac/Linux
export GROQ_API_KEY="your-groq-key-here"

# Windows
set GROQ_API_KEY="your-groq-key-here"
```

Get your **free** Groq API key at → [console.groq.com](https://console.groq.com)

---

## 📦 Requirements

```
streamlit
pandas
plotly
openpyxl
groq
```

---

## 💡 How it works

```
User types device name
        ↓
Groq LLaMA 3.3 70B reasons using regulatory knowledge
        ↓
Returns structured JSON with 6 framework classifications
        ↓
Streamlit renders risk badges, timeline chart, checklists
```

The AI classifies any device by reasoning from:
- **CDSCO**: Schedule 1 of MDR 2017
- **FDA**: 21 CFR Parts 862–892 product codes
- **EU MDR**: Annex VIII Classification Rules 1–22
- **Health Canada**: Canadian MDR SOR/98-282
- **Japan PMDA**: PMD Act classification rules
- **Australia TGA**: Therapeutic Goods Regulations 2002

---

## 📊 Key Features

- **Any device** — not limited to a fixed list; type any medical device ever made
- **AI reasoning** — each classification includes a cited regulatory rule
- **Confidence scoring** — High / Medium / Low with disclaimer for edge cases
- **Smart caching** — same device never makes two API calls in a session
- **Market selector** — toggle any combination of 6 markets
- **Timeline chart** — Plotly bar chart with average reference line
- **Comparison table** — side-by-side summary across all selected frameworks

---

## ⚠️ Disclaimer

This tool is intended for **educational and preliminary scoping purposes only**.
All classifications should be verified by a qualified regulatory affairs
professional before use in actual device submissions. The AI may occasionally
misclassify novel or highly specialised devices — always cross-reference with
official regulatory guidance documents.

---

## 👤 Author

Built by **Sayam** as part of a MedTech regulatory affairs portfolio project.

Demonstrates end-to-end knowledge of:
- MDR 2017 (India) & ISO 13485 requirements
- FDA 510(k) / PMA pathways & 21 CFR
- EU MDR 2017/745 & Annex VIII classification rules
- Health Canada SOR/98-282 MDEL licensing
- Japan PMD Act & DMAH requirements
- Australia TGA ARTG conformity assessment

---

## 📈 Impact

| Metric | Value |
|--------|-------|
| Frameworks encoded | 6 |
| Regulatory rules mapped | 72+ |
| Device types pre-loaded | 12 |
| Custom devices supported | Unlimited (AI-powered) |
| Pathway scoping time | Hours → Under 10 seconds |
