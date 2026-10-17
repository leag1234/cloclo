# UI bubble long report

## Delivered

- Completed the pending composer evidence on the real offset-700 Open WebUI shell:
  fresh-page matrix for every style, light/dark mode, 14–20 px text, and 1280/390 px;
  refreshed five composer captures and reviewed each image.
- Made user attachment cards width-safe inside a bubble. Cards are constrained to the
  bubble inner width; names remain single-line ellipses with their full synthetic name
  as a tooltip; file sizes remain visible.
- Added observer-driven long-message handling. Arrondi long messages use the neutral
  user surface, normal text, a 3 px accent edge, an eight-line soft-faded collapse,
  and a keyboard-accessible 44 px toggle. Dense and document retain their neutral
  surfaces with the same collapse behavior.
- Added English, French, German, Spanish, and Italian toggle labels and offline tests.
- Added a real-shell synthetic browser fixture with three 70–90 character attachment
  names, a 30-line pasted message, and a short control message. It captures and
  asserts the requested 12 style/size/viewport combinations.
- Refreshed M24 rendering evidence after the CSS hash changed.

## Evidence

- `reports/ui-restyle/bubble-long-*.png`: 12 reviewed synthetic captures.
- `reports/ui-restyle/measurements.json`: every bubble had no horizontal overflow;
  every card fit its bubble inner width; narrow names overflowed their label box for
  an actual ellipsis; the size stayed visible; collapsed content measured at no more
  than eight line-heights; keyboard activation expanded the toggle.
- `reports/m24-rendering.json`: CSS SHA-256
  `bbb75689517c3ec258f2773f84d5f8d087d4b893f9f43c708961e75e299530a1` and refreshed
  before/after/dark image digests.

## Commands and outcomes

- `bash scripts/test.sh` — passed.
- `make lint` — passed (using the repository virtual environment).
- `make typecheck` — passed.
- `bash scripts/verify-m16.sh` — passed.
- `ATLAS_BUBBLE_ONLY=1 python tests/ui_restyle_browser.py` — passed; final evidence
  matrix captured and reviewed.
- `ATLAS_COMPOSER_ONLY=1 python tests/ui_restyle_browser.py` — passed; fresh composer
  matrix and five captures reviewed.
- Synthetic M24 Playwright capture on the real local shell — passed.
- `make test-journeys` — run once and completed; replay evidence covers J1–J53. The
  repository accepts J34's recorded false state by contract.

ASSUMPTION: synthetic attachment names and message text are permitted rendering evidence
and do not represent owner content.

RISK: no cloud, GPU, or paid provider operation was started. Incremental cloud/GPU cost:
EUR 0/hour; local browser and replay checks have no billed provider cost.

NOTICED BUT NOT TOUCHING: protected workflows, verifier scripts, prompts, corpus cases,
thresholds, assertions, and documentation were left unchanged.

Source: real local Open WebUI v0.11.3 shell at the mandated offset-700 ports; browser
measurements and screenshots listed above.
