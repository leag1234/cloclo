# UI restyle evidence

Status: completed locally on `ui-restyle`; one local commit only. No push, PR,
merge, branch creation, cloud resource, or GPU was used.

## Fixture and capture

The supervisor-approved disposable rendering fixture was created through the offset
Open WebUI saved-chat API, using only synthetic content. It contained `brief.pdf`
(24 KB), `facts.xlsx` (8 KB), the specified French user message, and one saved
assistant message with the specified heading, two-row table, two source links, code
block, and two download links. The unchanged M24 and UI-restyle browser harnesses
waited for that real saved assistant message. The fixture was deleted through the
same API and the offset stack was stopped after capture.

Recaptured artifacts:

- `reports/m24-rendering.json`
- `reports/m24-rendering-before.png`
- `reports/m24-rendering-after.png`
- `reports/m24-rendering-dark.png`
- `reports/ui-restyle/arrondi-light.png`
- `reports/ui-restyle/arrondi-dark.png`
- `reports/ui-restyle/dense-light.png`
- `reports/ui-restyle/document-light.png`
- `reports/ui-restyle/popover.png`
- `reports/ui-restyle/popover-fr.png`

## Visual review

I opened and reviewed every image listed above after the final recapture.

- File names: `brief.pdf` and `facts.xlsx` are visible and readable in the four
  requested style/mode captures. A browser matrix also checked both filenames,
  their bounds, and the compact bubble in all 3 styles × 2 modes × 5 accents.
  The CSS explicitly targets Open WebUI v0.11.3's saved-message attachment buttons;
  the contrast test covers the card foreground/background for that entire matrix.
- User bubble: each capture has one outer bubble that hugs the attachment-card
  width. The cards stack above a transparent text area; the native inner rounded
  message chip no longer contributes a second background or padding.
- French selector: `popover-fr.png` visibly contains only French labels, including
  `Paramètres d’affichage`, `Couleur`, `Taille du texte`, `Système`, `Clair`,
  `Sombre`, and the French accent names. Its visible localized title fixes the
  prior capture failure.
- Overflow: no reviewed image has horizontal content or popover overflow. The
  browser matrix additionally asserted attachment-card and popover bounds.

## Checks

All make, test, and harness commands below used `ATLAS_PORT_BASE=700`.

- `python tests/m24_browser.py` — PASS; wrote the rendering JSON and before/after/dark captures.
- `python tests/ui_restyle_browser.py` — PASS; wrote all six UI-restyle captures.
- Playwright visual matrix (3 styles × 2 modes × 5 accents) — PASS.
- `bash scripts/test.sh` — PASS.
- `make lint` — PASS (`All checks passed!`).
- `make typecheck` — PASS (`334 source files`).
- `bash scripts/verify-m16.sh` — PASS.

ASSUMPTION: the authorized saved fixture is rendering-only evidence, not a claim
about model output. RISK: the local fixture stack used no cloud or GPU resource and
was removed after capture. Cost: €0 direct cloud/GPU cost.
Source: local pinned Open WebUI v0.11.3 shell, its authenticated saved-chat API, and
the unchanged browser capture harnesses.
