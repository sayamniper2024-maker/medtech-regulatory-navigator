import requests


def test_homepage_serves():
    """Simple smoke test: homepage returns 200 and contains app title."""
    url = "http://localhost:8501/"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    assert "MedTech Regulatory Pathway Navigator" in resp.text or "Streamlit" in resp.text
