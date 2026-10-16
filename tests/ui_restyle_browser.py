"""Capture the owner reference chat through the real Open WebUI browser shell."""

import json
import os
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from ui_fidelity_browser import (
    languages,
    measure,
    popover_rows,
    resize_sidebar,
    settings_matrix,
)


URL = os.environ["ATLAS_RENDER_CHAT_URL"]
OUTPUT = Path("reports/ui-restyle")
MEASUREMENTS: dict[str, object] = {}


def capture(page: Page, name: str, style: str, theme: str, size: int = 16) -> None:
    page.evaluate(
        """([style, theme, size]) => {
            localStorage.setItem('atlas-ui', JSON.stringify({style, mode: theme, accent: 'green', size: String(size)}));
            localStorage.setItem('theme', theme);
        }""",
        [style, theme, size],
    )
    page.reload(wait_until="networkidle")
    page.locator(".chat-assistant").wait_for()
    page.evaluate("document.fonts.ready")
    page.locator("#chat-input").fill("Ask a follow-up")
    page.locator("#messages-container").evaluate("e => e.scrollTop = 0")
    MEASUREMENTS[name] = measure(page, style, size)
    page.screenshot(path=OUTPUT / name, full_page=False)


OUTPUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1280, "height": 900}, locale="fr-FR")
    page.goto(URL, wait_until="networkidle")
    try:
        page.get_by_text("Okay, Let's Go!", exact=True).click(timeout=1000)
    except Exception:
        pass
    page.locator(".chat-assistant").wait_for()
    assert page.locator(".user-message").count() == 1
    assert page.locator("#atlas-ui-selector").count() == 1
    page.evaluate(
        "localStorage.setItem('sidebar', 'true'); localStorage.setItem('locale', 'en-US')"
    )
    capture(page, "arrondi-light.png", "arrondi", "light")
    capture(page, "arrondi-dark.png", "arrondi", "dark")
    capture(page, "dense-light.png", "dense", "light")
    capture(page, "document-light.png", "document", "light")
    page.locator("#atlas-ui-toggle").click()
    popover_rows(page)
    assert page.locator("#atlas-ui-popover").is_visible()
    page.screenshot(path=OUTPUT / "popover.png", full_page=False)
    page.evaluate("localStorage.setItem('locale', 'fr-FR')")
    page.reload(wait_until="networkidle")
    page.locator("#atlas-ui-toggle").click()
    assert page.get_by_text("Paramètres d’affichage", exact=True).is_visible()
    page.screenshot(path=OUTPUT / "popover-fr.png", full_page=False)
    page.keyboard.press("Escape")
    assert page.locator("#atlas-ui-toggle").get_attribute("aria-expanded") == "false"
    assert page.locator("#atlas-ui-toggle").evaluate("e=>e===document.activeElement")
    for size in (14, 18, 20):
        capture(page, f"arrondi-light-{size}px.png", "arrondi", "light", size)
    # The interface remains English; browser language alone selects French.
    page.evaluate("localStorage.setItem('locale', 'en-US')")
    capture(page, "arrondi-light.png", "arrondi", "light")
    page.locator("#atlas-ui-toggle").click()
    assert page.get_by_text("Paramètres d’affichage", exact=True).is_visible()
    popover_rows(page)
    page.screenshot(path=OUTPUT / "popover-fr.png", full_page=False)
    for width in (360, 359):
        page.set_viewport_size({"width": width, "height": 900})
        if width == 360:
            popover_rows(page)
    page.set_viewport_size({"width": 1280, "height": 900})
    # An explicit appearance override has precedence over the browser locale.
    page.evaluate("localStorage.setItem('atlas-ui-language', 'de-DE')")
    page.reload(wait_until="networkidle")
    page.locator("#atlas-ui-toggle").click()
    assert page.get_by_text("Anzeigeeinstellungen", exact=True).is_visible()
    popover_rows(page)
    page.keyboard.press("Escape")
    MEASUREMENTS["settings_matrix"] = settings_matrix(page)
    MEASUREMENTS["languages"] = languages(browser, URL)
    resize_sidebar(page)
    MEASUREMENTS["native_sidebar_resize"] = True
    (OUTPUT / "measurements.json").write_text(json.dumps(MEASUREMENTS, indent=2) + "\n")
    browser.close()
