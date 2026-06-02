# medtech-regulatory-navigator
AI-powered medical device regulatory pathway tool (CDSCO, FDA, CE Mark)
readme = '''# 🧬 MedTech Regulatory Pathway Navigator

> AI-powered decision-support tool that recommends the optimal regulatory pathway
> for any medical device across **CDSCO (India)**, **FDA 510(k)/PMA (USA)**, and **CE Mark (EU MDR)**.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://medtech-regulatory-navigator-e7khygzx9hreudkxtfdk2x.streamlit.app/)

---

## What it does

Medical device companies spend hours manually researching regulatory pathways
before starting any market entry project. This tool encodes 3 major regulatory
frameworks into a single AI-powered interface that returns a full pathway
recommendation in under 10 seconds.

**Input:** Any medical device name + optional description
**Output:**
- Risk classification under CDSCO, FDA, and EU MDR
- Recommended pathway (e.g. 510k, PMA, MD-9, CE Mark IIb)
- Estimated approval timeline per market
- Submission document checklist per framework
- Fastest market entry recommendation
- Side-by-side comparison table

---

## Live Demo

Try it here: **[medtech-navigator.streamlit.app](https://medtech-regulatory-navigator-e7khygzx9hreudkxtfdk2x.streamlit.app/)**

Example devices to try:
- `Smart insulin pen with dose tracking`
- `AI-powered retinal screening camera`
- `Robotic surgical assistant arm`
- `Wearable continuous glucose monitor`
- `Neural implant for Parkinson tremor`

---

## Regulatory Frameworks Encoded

| Framework | Region | Classification System |
|-----------|--------|-----------------------|
| CDSCO MDR 2017 | India | Class A / B / C / D |
| FDA 21 CFR Parts 862-892 | USA | Class I / II / III + 510(k) / PMA |
| EU MDR 2017/745 | Europe | Class I / IIa / IIb / III |

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python | Core language |
| Streamlit | Web UI (no HTML/CSS needed) |
| Pandas | Data handling and Excel rule sets |
| Plotly | Interactive timeline comparison charts |
| Google Gemini API | AI-powered device classification |
| Excel (openpyxl) | Structured regulatory rule sets |

---

## Run Locally

```bash
git clone[ https://github.com/sayamniper2024-maker/medtech-regulatory-navigator]
cd medtech-regulatory-navigator
pip install -r requirements.txt
streamlit run app.py
```

Set your Gemini API key as an environment variable:
```bash
export GEMINI_API_KEY="your-key-here"   # Mac/Linux
set GEMINI_API_KEY="your-key-here"      # Windows
```

---

## Project Structure

---

## Disclaimer

This tool is intended for educational and preliminary scoping purposes only.
All classifications should be verified by a qualified regulatory affairs
professional before use in actual device submissions.

---

## Author

Built by **Sayam** as part of a MedTech regulatory affairs portfolio project.
Demonstrates end-to-end knowledge of MDR 2017, ISO 13485, FDA 510(k)/PMA,
and EU MDR 2017/745 classification rules.
'''
