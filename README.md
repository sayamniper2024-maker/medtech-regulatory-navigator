# 🧬 MedTech Regulatory Pathway Navigator

> AI-powered decision-support tool that classifies any medical device across
> **7 major global regulatory frameworks** — from typing a device name to a
> full pathway recommendation in under 10 seconds.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://medtech-regulatory-navigator-e7khygzx9hreudkxtfdk2x.streamlit.app/)
![Version](https://img.shields.io/badge/version-2.0-blue)
![Frameworks](https://img.shields.io/badge/frameworks-7-green)
![AI](https://img.shields.io/badge/AI-Groq%20LLaMA%203.3-purple)

---

## What it does

Medical device companies spend hours manually researching regulatory pathways.
This tool encodes **7 major regulatory frameworks** into a single AI-powered
interface — for **any medical device ever made**.

---

## Live demo

**[medtech-regulatory-navigator.streamlit.app](https://medtech-regulatory-navigator-e7khygzx9hreudkxtfdk2x.streamlit.app/)**

Try: `Coronary Stent` · `Total Knee Replacement` · `AI retinal scanner` · `Drug-Eluting Stent`

---

## 7 regulatory frameworks

| Flag | Market | Framework | Classes |
|------|--------|-----------|---------|
| 🇮🇳 | India | CDSCO MDR 2017 | A / B / C / D |
| 🇺🇸 | USA | FDA 21 CFR Parts 862-892 | I / II / III + 510(k) / PMA |
| 🇪🇺 | Europe | EU MDR 2017/745 | I / IIa / IIb / III |
| 🇨🇦 | Canada | Health Canada SOR/98-282 | I / II / III / IV |
| 🇯🇵 | Japan | PMDA Yakuji Ho (PMD Act) | I / II / III / IV |
| 🇦🇺 | Australia | TGA ARTG (TGO 2002) | I / IIa / IIb / III |
| 🇷🇺 | Russia | Roszdravnadzor Decree No.1684 | 1 / 2a / 2b / 3 |

---

## Full feature list

| Track | Feature | Status |
|-------|---------|--------|
| 1 | 7 global regulatory frameworks | ✅ |
| 2 | PDF export with full analysis | ✅ |
| 2 | World map heatmap (Plotly choropleth) | ✅ |
| 2 | Device comparison mode + radar chart | ✅ |
| 2 | Search history + CSV export | ✅ |
| 3 | Regulatory Q&A chatbot (context-aware) | ✅ |
| 3 | RULE_EXCEPTIONS accuracy layer | ✅ |
| 3 | KNOWN_CORRECTIONS post-classification validator | ✅ |
| 4 | PDF datasheet upload with auto-fill | ✅ |
| 4 | Submission gap analysis (7 frameworks) | ✅ |
| 5 | Regulatory cost estimator (stacked bar) | ✅ |
| 5 | Gantt chart — submission milestones | ✅ |
| 6 | Accuracy feedback loop | ✅ |
| 6 | Regulatory news feed | ✅ |

---

## Classification accuracy

The app uses a two-layer accuracy system:

1. **RULE_EXCEPTIONS** — injected into every AI prompt. Explicitly maps high-risk
   devices (coronary stents, joint replacements) to correct classes before the AI
   applies general rules. Prevents the most common misclassifications.

2. **KNOWN_CORRECTIONS** — post-classification validator. After the AI responds,
   a Python dictionary of hard-coded correct answers is compared. If the AI got
   it wrong, the validator corrects it and shows exactly what was changed and why.

Examples:
- Coronary stent → FDA Class III PMA (21 CFR 870.3945), EU Class III (Rule 8)
- Total knee replacement → EU Class III (Annex VIII Rule 8), not IIb
- Russia cardiac implants → Class 3, Decree No.1684

---

## Tech stack

| Tool | Purpose |
|------|---------|
| Python 3.11 | Core language |
| Streamlit | Web UI |
| Pandas | Data handling |
| Plotly | Interactive charts, world map, Gantt, radar |
| Groq API (LLaMA 3.3 70B) | Classification, chatbot, gap analysis, news |
| PyMuPDF (fitz) | PDF text extraction |
| fpdf2 | PDF report generation |
| openpyxl | Excel rule sets |

---

## Run locally

```bash
git clone https://github.com/sayamniper2024-maker/medtech-regulatory-navigator
cd medtech-regulatory-navigator
pip install -r requirements.txt
streamlit run app.py
```

Set your Groq API key:
```bash
export GROQ_API_KEY="your-key-here"
```

Get a free key at [console.groq.com](https://console.groq.com)

---

## Project structure
## Project structure
medtech-regulatory-navigator/
├── app.py                      # Main Streamlit application (~1700 lines)
├── requirements.txt            # Dependencies
├── README.md                   # This file
└── data/
└── regulatory_rules.xlsx  # Rule sets (7 sheets, fallback data)

---

## Disclaimer

For educational and preliminary scoping purposes only. Always verify with a
qualified regulatory affairs professional before use in actual device submissions.

---

## Author

Built by **Sayam** — MedTech regulatory affairs portfolio project.

Demonstrates: MDR 2017 · ISO 13485 · FDA 510(k)/PMA · EU MDR 2017/745 ·
Health Canada SOR/98-282 · Japan PMD Act · Australia TGO 2002 ·
Russia Roszdravnadzor Decree No.1684
'''

with open("README.md","w") as f:
    f.write(readme)

from google.colab import files
files.download("README.md")
print("✅ README updated — upload to GitHub")
