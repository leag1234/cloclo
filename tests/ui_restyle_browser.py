"""Capture the owner reference chat through the real Open WebUI browser shell."""

import os
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


URL = os.environ["ATLAS_RENDER_CHAT_URL"]
OUTPUT = Path("reports/ui-restyle")


def capture(page: Page, name: str, style: str, theme: str) -> None:
    page.evaluate(
        """([style, theme]) => {
            localStorage.setItem('atlas-ui', JSON.stringify({style, mode: theme, accent: 'green', size: '16'}));
            localStorage.setItem('theme', theme);
        }""",
        [style, theme],
    )
    page.reload(wait_until="networkidle")
    page.locator(".chat-assistant").wait_for()
    page.screenshot(path=OUTPUT / name, full_page=True)


OUTPUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1280, "height": 1200})
    page.goto(URL, wait_until="networkidle")
    try:
        page.get_by_text("Okay, Let's Go!", exact=True).click(timeout=1000)
    except Exception:
        pass
    page.locator(".chat-assistant").wait_for()
    assert page.locator(".user-message").count() == 1
    assert page.locator("#atlas-ui-selector").count() == 1
    capture(page, "arrondi-light.png", "arrondi", "light")
    capture(page, "arrondi-dark.png", "arrondi", "dark")
    capture(page, "dense-light.png", "dense", "light")
    capture(page, "document-light.png", "document", "light")
    page.locator("#atlas-ui-toggle").click()
    assert page.locator("#atlas-ui-popover").is_visible()
    page.screenshot(path=OUTPUT / "popover.png", full_page=True)
    page.evaluate("localStorage.setItem('locale', 'fr-FR')")
    page.reload(wait_until="networkidle")
    page.locator("#atlas-ui-toggle").click()
    assert page.get_by_text("Paramètres d’affichage", exact=True).is_visible()
    page.screenshot(path=OUTPUT / "popover-fr.png", full_page=True)
    browser.close()
