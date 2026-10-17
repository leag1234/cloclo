"""Capture the owner reference chat through the real Open WebUI browser shell."""

import json
import os
from pathlib import Path

from playwright.sync_api import Browser, Error, Page, TimeoutError, sync_playwright

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


def synthetic_images(count: int) -> list[dict[str, object]]:
    """Return browser-file-chooser payloads for public, synthetic image previews."""
    colors = ("#e84d4d", "#2878d4", "#1f9d55")
    return [
        {
            "name": f"synthetic-composer-{index + 1}.svg",
            "mimeType": "image/svg+xml",
            "buffer": (
                '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96">'
                f'<rect width="96" height="96" fill="{colors[index]}"/>'
                "</svg>"
            ).encode(),
        }
        for index in range(count)
    ]


def synthetic_pdf() -> dict[str, object]:
    """A deliberately long synthetic name proves the native file-card truncation."""
    return {
        "name": "Synthetic public composer attachment with a deliberately long name for truncation evidence 2026.pdf",
        "mimeType": "application/pdf",
        "buffer": b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF",
    }


def attach(page: Page, files: list[dict[str, object]]) -> None:
    """Set files on Open WebUI's hidden native input and wait for decoded previews."""
    # The menu creates the real, hidden Upload Files input. Set it directly instead
    # of driving the browser chooser, then wait for Open WebUI to render its queue.
    page.locator("#input-menu-button").click()
    chooser = page.locator('input[type="file"]:not(#camera-input)')
    chooser.wait_for(state="attached")
    chooser.set_input_files(files)
    image_count = sum(file["mimeType"].startswith("image/") for file in files)
    page.wait_for_function(
        """expected => {
          const container = document.querySelector('#message-input-container');
          if (!container) return false;
          const previews = [...container.querySelectorAll('img[data-cy="image"]')];
          const removes = [...container.querySelectorAll(':scope > div:first-of-type button[aria-label]:not(:has(img[data-cy="image"]))')];
          return previews.length === expected.images && removes.length === expected.files
            && previews.every(image => image.naturalWidth > 0);
        }""",
        arg={"files": len(files), "images": image_count},
        timeout=20_000,
    )
    page.keyboard.press("Escape")
    page.wait_for_timeout(250)


def boxes_do_not_intersect(page: Page) -> dict[str, object]:
    """Keep attachment previews clear of the dedicated input row controls."""
    values = page.evaluate(
        """() => {
          const box = element => {
            const r = element.getBoundingClientRect();
            return {left:r.left, right:r.right, top:r.top, bottom:r.bottom,
                    width:r.width, height:r.height};
          };
          const attachments = [
            ...document.querySelectorAll('#message-input-container img[data-cy="image"]'),
            ...document.querySelectorAll('#message-input-container > div:first-of-type button[aria-label]:not(:has(img[data-cy="image"]))'),
          ].map(box);
          const controls = ['#input-menu-button', '#send-message-button', '#chat-input-container']
            .map(selector => document.querySelector(selector)).filter(Boolean).map(box);
          const intersects = (a, b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
          return {attachments, controls, collisions: attachments.flatMap(attachment => controls.filter(control => intersects(attachment, control)))};
        }"""
    )
    assert not values["collisions"], values
    return values


def composer_capture(
    browser: Browser,
    name: str,
    style: str,
    theme: str,
    size: int,
    width: int,
    files: list[dict[str, object]],
    screenshot: bool = False,
) -> None:
    """Exercise one isolated native-composer scenario, retrying only that scenario."""
    last_error: Error | AssertionError | None = None
    for attempt in range(3):
        page = browser.new_page(viewport={"width": width, "height": 900}, locale="fr-FR")
        try:
            page.goto(URL, wait_until="networkidle")
            try:
                page.get_by_text("Okay, Let's Go!", exact=True).click(timeout=1000)
            except TimeoutError:
                pass
            page.evaluate(
                """([style, theme, size]) => {
                  localStorage.setItem('atlas-ui', JSON.stringify({style, mode: theme, accent: 'green', size: String(size)}));
                  localStorage.setItem('theme', theme);
                }""",
                [style, theme, size],
            )
            page.reload(wait_until="networkidle")
            page.locator("#chat-input").wait_for()
            attach(page, files)
            page.locator("#chat-input").fill("Keep typing normally")
            page.keyboard.press("Shift+Enter")
            page.keyboard.type("with a second line")
            _assert_composer(page, name, style, theme, size, width, files, screenshot)
            return
        except (AssertionError, Error) as error:
            last_error = error
            if attempt == 2:
                raise
        finally:
            page.close()
    raise AssertionError(f"{name} exhausted its bounded retry") from last_error


def _assert_composer(
    page: Page,
    name: str,
    style: str,
    theme: str,
    size: int,
    width: int,
    files: list[dict[str, object]],
    screenshot: bool,
) -> None:
    """Assert the completed attachment queue before recording one isolated scenario."""
    images = page.locator('#message-input-container img[data-cy="image"]')
    removes = page.locator(
        '#message-input-container > div:first-of-type button[aria-label]:not(:has(img[data-cy="image"]))'
    )
    assert images.count() == sum(file["mimeType"].startswith("image/") for file in files)
    assert removes.count() == len(files)
    if images.count():
        dimensions = images.evaluate_all(
            "images => images.map(image => { const r = image.getBoundingClientRect(); return [r.width, r.height]; })"
        )
        assert dimensions == [[64, 64]] * images.count(), dimensions
    remove_dimensions = removes.evaluate_all(
        "buttons => buttons.map(button => { const r = button.getBoundingClientRect(); return [r.width, r.height]; })"
    )
    assert all(width >= 44 and height >= 44 for width, height in remove_dimensions)
    file_cards = page.locator('#message-input-container > div:first-of-type > button')
    if any(file["mimeType"] == "application/pdf" for file in files):
        assert file_cards.count() == 1
        assert file_cards.first.bounding_box()["width"] <= 220
        assert file_cards.first.locator(".truncate.pr-1").count() == 1
    values = boxes_do_not_intersect(page)
    composer = page.locator("#message-input-container").bounding_box()
    assert composer is not None and composer["height"] > 52
    assert page.locator("#message-input-container").evaluate(
        "element => getComputedStyle(element).height !== '52px'"
    )
    assert page.locator("#message-input-container").evaluate(
        "element => Math.round(parseFloat(getComputedStyle(element).borderRadius)) === 24"
    )
    MEASUREMENTS[name] = {
        "style": style,
        "theme": theme,
        "size": size,
        "viewport_width": width,
        "composer": composer,
        "no_input_row_collisions": values,
        "remove_dimensions": remove_dimensions,
    }
    if screenshot:
        page.screenshot(path=OUTPUT / name, full_page=False)


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
    if os.environ.get("ATLAS_COMPOSER_ONLY") == "1":
        # The empty native chat is enough to verify queued attachments; do not
        # manufacture a conversation or call a model merely for layout evidence.
        if os.environ.get("ATLAS_COMPOSER_CAPTURES_ONLY") != "1":
            for style in ("arrondi", "dense", "document"):
                for theme in ("light", "dark"):
                    for size in (14, 16, 18, 20):
                        composer_capture(browser, f"composer-matrix-{style}-{theme}-{size}-1280", style, theme, size, 1280, synthetic_images(1))
                        composer_capture(browser, f"composer-matrix-{style}-{theme}-{size}-390", style, theme, size, 390, synthetic_images(1))
        composer_capture(browser, "composer-one-image.png", "arrondi", "light", 16, 1280, synthetic_images(1), True)
        composer_capture(browser, "composer-three-images.png", "dense", "light", 18, 1280, synthetic_images(3), True)
        composer_capture(browser, "composer-pdf-and-long-name.png", "document", "light", 20, 1280, [synthetic_pdf()], True)
        composer_capture(browser, "composer-mobile.png", "arrondi", "light", 16, 390, synthetic_images(3), True)
        composer_capture(browser, "composer-dark.png", "document", "dark", 20, 1280, synthetic_images(1), True)
        (OUTPUT / "measurements.json").write_text(json.dumps(MEASUREMENTS, indent=2) + "\n")
        browser.close()
        raise SystemExit
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
    # The attachment composer is real Open WebUI state, covered at every style,
    # theme, owner text size and both requested viewport widths.
    for style in ("arrondi", "dense", "document"):
        for theme in ("light", "dark"):
            for size in (14, 16, 18, 20):
                composer_capture(
                    browser,
                    f"composer-matrix-{style}-{theme}-{size}-{1280}.png",
                    style,
                    theme,
                    size,
                    1280,
                    synthetic_images(1),
                )
                composer_capture(
                    browser,
                    f"composer-matrix-{style}-{theme}-{size}-{390}.png",
                    style,
                    theme,
                    size,
                    390,
                    synthetic_images(1),
                )
    composer_capture(browser, "composer-one-image.png", "arrondi", "light", 16, 1280, synthetic_images(1), True)
    composer_capture(browser, "composer-three-images.png", "dense", "light", 18, 1280, synthetic_images(3), True)
    composer_capture(browser, "composer-pdf-and-long-name.png", "document", "light", 20, 1280, [synthetic_pdf()], True)
    composer_capture(browser, "composer-mobile.png", "arrondi", "light", 16, 390, synthetic_images(3), True)
    composer_capture(browser, "composer-dark.png", "document", "dark", 20, 1280, synthetic_images(1), True)
    (OUTPUT / "measurements.json").write_text(json.dumps(MEASUREMENTS, indent=2) + "\n")
    browser.close()
