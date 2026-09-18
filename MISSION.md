# MISSION — ATLAS-0

Build [docs/13](docs/13-poc-spec.md); read AGENTS.md, docs/11 and docs/14 first.
M0–M21 delivered; M22 current; no later milestone. History: docs/decisions-log.md.

Done = make verify-mN + green GitHub ci. Protect workflows/CODEOWNERS/verify-*;
never weaken assertions. Branch/PR only, no main push. Current human mandate
controls merge and subsequent milestones.

## Permanent constraints

Contracts precede code; prove useful answers through public HTTP. No secrets in
repo/logs/prompts; dedicated project only. GPU2 EUR/h,30 EUR/milestone; owner accepts
bounded risk with alerts. Record costs before provisioning; destroy experiments
and run infra/gpu-down.sh at session end.

Requests: <=10 tools; authorized profile budgets/deadlines below.
Image model loading is measured separately under contracts/m13 and M20's bounded
startup wait. Declare live/replay honestly; replay uses real recordings. Do not re-verify completed milestones without explicit request or visible regression;
use BRAIN outcomes and report skips. CI regression gates remain mandatory.

Update BRAIN STATUS/TASK/JOURNAL before risk and session end, BLOCKERS when blocked.
MISSION <=8000 bytes; archive settled history unchanged in decisions-log.

### Journey rules (permanent)

R1: Before implementation, write user intent and six natural phrasings, independent
of regexes/templates.

R2: For each capability include six phrasings, three without the obvious keyword,
a message of at most four words, unaccented and uppercase input, English and another
language, and a negative case. For attachments include at least two in one request.

R3: Assert useful user content, never just internal calls/routing. No useful answer
means failure.

R4: Preserve every owner-reported defect as a permanent, verbatim, dated journey;
never rephrase it to make it easier.

R5: A service module called only from tests is not delivered. Unreachable modules
must fail the gate, not merely produce a warning.

R6: Every rejection identifies measured values and thresholds, in plain user-facing
language and the server journal. Never conflate image byte limits with model token
limits. Preserve the user's question when it can be safely parsed.

## Standing facts — never archive

- Token incidents2026-09-13/15 are CLOSED. Owner replaced and reinjected credentials,
  verified API write/delete and push. Never stop or reconfirm for pre-17th incidents.
- Owner attests GPU2 EUR/h,30 EUR/milestone,800 EUR monthly, alerts active.
  Hypothetical shutdown defects are notes, not blockers.
- External failure counters reset each session; historical errors do not block a
  first attempt. Preserve permanent rules; archive only history.

## M22 — Search before asserting, exceed the source, better vision

Source: owner comparison corpus2026-09-17, preserved verbatim in
tests/journeys/m22-cases.json; [contract](contracts/m22.md).
REQ-ENG-004/005/009/011, REQ-FIN-002, POC-F3/F4/F5.

The delivered public profiles retain0.10 EUR/120s/3000 output tokens/10 tools,
with reasoning_effort=none on every generation, including recovery/evaluation.
Legacy internal clients retain0.05 EUR. Validate every provider reply, explicitly
handle malformed/empty/interrupted results and preserve the shared recovery ledger.
Default text model unchanged; public names are in contracts/m21-profiles.json.

D1: Search BEFORE stating facts that can change: IPO/listing status, leaders,
prices, availability, versions, current status. Training knowledge is a hypothesis.
Verify concrete historical mechanisms too; confidence is not verification. Explain
figures with different definitions/dates (offer price versus opening trading price).
Preserve the original SpaceX and Paris defects in the owner corpus.

D2: Read supplied sources for what they contain and search for what the QUESTION
needs. A how-to, comparison or recommendation based on news/testimony/one reference
requires1–3 targeted subject searches. Read independent practical evidence, identify
contradictions and do not simply repeat the article. Solargraphy paper is scanned,
not chemically developed; explicitly correct the misleading article wording.

D3: Route vision to the owner's selected replacement in model-gateway/routing.yaml,
retaining the previous vision model as fallback. tests/vision_bench/ contains the
original guitar photo and owner low-E-to-high-e frets5,5,7,5,5,7 (full barre fret5,
two fingers fret7). Score correct string/fret positions out of N; report structure
recognised and compatible chord family independently. Chosen score >= previous
score on identical benchmark inputs; no absolute accuracy threshold.

D4: Remove model planning/search narration from final and streamed answer bodies;
show progress as M21 activity states. Preserve substantive answers, code and quotes.

### Public HTTP journeys

Original dated French questions are retained verbatim in tests/journeys/m22-cases.json.
J34: original SpaceX IPO-price question; search before answer, dated price,
     distinguish offer/opening definitions. Never assert stale private status.
J35: CEO of a company whose leadership changed within the last12 months; search first.
J36: original National Geographic URL and camera how-to question; search beyond
     the article, state scanning without chemical development and correct the article.
J37: original guitar photo; record positions/structure/family and score>=previous.
J38: no planning/search narration in answer bodies; activity states carry progress.

Done: make verify-m22 locally and green GitHub ci; J1–J38; at least one annotated
photo and scoring script in tests/vision_bench/; configured replacement vision role.

## M23 — Readable rendering: typography, code blocks, spacing

Source: side-by-side comparison of the same answer rendered by Claude and by ATLAS
(2026-09-18, Python venv debugging question). The content was comparable; the ATLAS
rendering was markedly harder to read. Every difference below is a rendering choice, not
a model choice, and is fixed in `services/orchestrator/chat-ui.css` (already mounted into
the container by `serving.py`).

### Constraint: survive Open WebUI upgrades
Open WebUI generates utility classes that change between versions. Target, in order of
preference: (1) CSS custom properties exposed by the theme, (2) semantic elements
(`pre`, `code`, `p`, `li`, `h2`), (3) attribute patterns (`[class*="bg-gray-"]`), and only
as a last resort a generated class name. Every rule carries a comment stating what it
targets and why, so a future upgrade can be repaired quickly. Before writing rules,
inspect the running UI to list the CSS variables the theme actually exposes and record
them in `reports/M23.md`.

### D1 — Body typography
Claude renders body text in a serif at a comfortable size with softened contrast; ATLAS
uses a dense sans-serif in near-black.
- Define `--atlas-body-font: Georgia, "Iowan Old Style", "Times New Roman", serif` and
  `--atlas-body-size` / `--atlas-line-height` on `:root`, then apply them through
  `var(...)`. **Do not use `!important` on the font** so that a user preference in Open
  WebUI can still override it; if the theme exposes its own font variable, redefine that
  variable instead of the property.
- Soften body colour from pure black to a very dark grey; keep WCAG AA contrast.
- Owner decision: serif by default. Switching the whole rendering back must be a
  one-line change to `--atlas-body-font`.

### D2 — Code blocks: remove the furniture
Observed on ATLAS: every block, including one-liners, carries a "Collapse / Save / Copy"
toolbar, line numbers, and a highlighted active line. Claude shows a plain block with a
light background and a thin border.
- Hide line numbers and the per-block toolbar by default; expose a copy affordance on
  hover only.
- Remove active-line highlighting.
- Light background, thin border, generous inner padding, no heavy shadow.
- Keep horizontal scrolling for long lines; never wrap code.

### D3 — Inline code
Short identifiers (`pip`, `python3`) must read as discreet capsules inside the sentence:
subtle background, no border, slightly smaller monospace, enough padding not to touch the
surrounding words. Today's contrast breaks the reading flow.

### D4 — Line length and spacing
- Cap the text column at 680–720 px; keep code blocks free to use the available width.
- Increase spacing between sections (`h2`, `h3`) and between list items; the current
  rendering is compact and sections run into each other.
- Keep the existing green user-message styling from M21 unchanged.

### D5 — Dark mode parity
Every rule above has a dark-mode counterpart. The current file already handles
`.dark .user-message`; extend the same approach so the reading experience matches.

### D6 — Generated code is always in English
Observed 2026-09-18: asked in French, the models produce identifiers, comments and
docstrings in French. ChatGPT and Claude emit English code regardless of the conversation
language, which is the established convention — and this repository itself has been in
English since M16. French identifiers make the output unusable in a shared codebase.

Rule, to be added to `prompts/chat.txt` and `prompts/chat-agent.txt`:
- **In English, always**: variable, function, class and file names; comments; docstrings;
  log and error messages intended for developers; commit messages.
- **In the user's language**: the prose around the code — explanations, section titles,
  the answer itself.
- **Context-dependent**: strings displayed to end users. If the user asks for an interface
  for French speakers, the visible labels stay French while the code around them stays
  English. The model must distinguish code from the content it carries.
This applies to every profile and to the developer API (M15), where the clients are
Codex and Claude Code.

### D7 — The activity indicator must also cover pure thinking
Observed 2026-09-18: on a long-document synthesis with no tool call, the screen shows only
a blinking cursor while the model works. M21/D5 required an indicator within 2 s naming
the current phase, but it only fires on tool steps; plain generation shows nothing.

Required: the indicator appears within 2 s of the request for EVERY request, including
those with no tool call, and stays visible until the first token of the answer reaches the
screen. It names the phase ("Réflexion…", "Lecture du document…", "Rédaction…") and shows
elapsed time. When tokens start streaming, the indicator gives way to the text; it must
never disappear leaving nothing behind. A request that takes 30 s with no tool call must
show a live state for those 30 s.

### D8 — Attached documents are never read (blocking capability gap)
Observed 2026-09-18: a ~60-page PDF was attached and "fais-moi une synthèse d'une page" was
asked. The answer reported that only three short fragments were available (an eReceipt
header, a mention of a data management plan, a table-of-contents line "9.3 Subcontractors")
and honestly refused to synthesise. Meanwhile the internal RAG searched the test corpus
(logistics, GDPR, medical, telework, marketing) and returned unrelated documents.

Root cause: `prepare_uploads()` in `services/orchestrator/image_store.py` skips every part
whose type is not `image_url`. **There is no document path at all.** What the model saw were
fragments that Open WebUI had extracted with its own retrieval before forwarding the
request — ATLAS never received the file.

Required:
- **Receive the whole file.** Disable Open WebUI's own document retrieval for attachments
  so the file reaches the adapter intact (or accept its upload endpoint and fetch the
  original). Document the setting in `runbooks/chat.md`.
- **Extract and read it in full**: PDF, DOCX, TXT, MD, CSV. Put the extracted text in the
  model context. A 60-page document is roughly 40 000 tokens and fits comfortably in the
  262 144-token window. Report extraction failures explicitly (scanned PDF with no text
  layer, password-protected file) instead of silently delivering fragments.
- **Only above the window**, apply the M10 hierarchical synthesis — never random sampling
  of chunks, and never the corpus RAG.
- **Never route an attached document to the corpus RAG.** A file attached to the
  conversation and the indexed corpus are two different things; a question about the
  attachment must not return corpus documents.
- Log, per request: file name, size, pages, extracted characters, whether hierarchical
  synthesis was applied.

This is the most common professional use of the assistant (summarise a report, a spec, a
contract) and it currently does not work at all.

### Verification
A gate cannot judge aesthetics. `verify-m23` checks what is objectively checkable:
- `chat-ui.css` defines the `--atlas-*` custom properties and uses them via `var()`;
- no `!important` on any `font-family` declaration;
- rules exist for `pre`, `code`, inline code, column width and section spacing;
- dark-mode counterparts exist for each new rule;
- every rule block carries an explanatory comment;
- `prompts/chat.txt` and `prompts/chat-agent.txt` state the English-code rule;
- the activity indicator is emitted on request start, not only on tool events;
- a document path exists in `prepare_uploads` (not only `image_url`), with an extractor;
- `reports/M23.md` lists the theme variables found in the running UI, and states which
  selectors are version-fragile and how to repair them.
The final judgement is the owner's, on screen, after `make serve`.

**Journey** J41: attach a multi-page PDF and ask for a one-page synthesis → the answer
covers sections from the beginning, middle AND end of the document; the log records the
extracted character count; the corpus RAG is not queried.                    [2026-09-18]

**Journey** J40: a request with NO tool call (e.g. summarise a long attached document) →
an activity state is emitted within 2 s and updated until the first answer token.[2026-09-18]

**Journey** J39: ask, in French, for a small Python function with a docstring. The returned
code must carry English identifiers, comments and docstring, while the surrounding
explanation stays French.                                                    [2026-09-18]

**Definition of done**: `make verify-m23` passes; J39 passes; the owner confirms the
rendering on the same debugging answer used for the 2026-09-18 comparison.
