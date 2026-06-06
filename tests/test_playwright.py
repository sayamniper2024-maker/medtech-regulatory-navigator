import pytest

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
def test_streamlit_ui_playwright():
    """Playwright scaffold: launches a headless browser and checks for root element.

    Requires: `pip install playwright pytest-playwright` and `playwright install`.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("http://localhost:8501/", timeout=10000)
        # wait for Streamlit root
        page.wait_for_selector("#root", timeout=5000)
        assert page.query_selector_all("#root")
        browser.close()
