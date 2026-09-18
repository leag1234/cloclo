# MISSION — ATLAS-0

Build [docs/13](docs/13-poc-spec.md); read AGENTS.md, docs/11 and docs/14 first.
M0–M22 delivered; M23 current; no later milestone. History: docs/decisions-log.md.

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

## M23 — readable rendering, English code, activity and complete attachments

Full owner acceptance: [contracts/m23.md](contracts/m23.md), D1–D8 and J39–J41.
Original dated owner wording is preserved in tests/journeys/m23-cases.json.
REQ-ENG-004/005/009/011, REQ-FIN-002, POC-F1/F2. No model change for rendering.

D1–D5: inspect the running Open WebUI theme and record exposed variables in
reports/M23.md before CSS edits. In chat-ui.css use theme variables, semantic tags,
attribute patterns, then generated classes only as a last resort; comment every
rule. Default Georgia/Iowan/Times serif through --atlas-body-font; define/use
--atlas-body-size and --atlas-line-height. User font preferences remain overridable,
no font-family !important. Accessible dark-grey text, 680–720px prose column,
more heading/list spacing, full-width horizontally scrolling unwrapped code.
Code blocks: light background, thin border, padding, no heavy shadow, line numbers,
active-line highlight or default toolbar; copy on hover. Inline code: subtle capsule,
smaller monospace, no border. Preserve M21 green user messages. Dark parity for all.
Document fragile selectors and upgrade repairs; owner judges the original debugging
answer on screen after make serve.

D6: every profile and M15 developer API emits English identifiers, filenames,
comments, docstrings, developer logs/errors and commit messages. Prose follows
user language; end-user labels follow the intended audience. Both chat prompts
state the rule. J39: French request produces English code/docstring with French prose.

D7: activity within2s for every request, including no-tool generation; named phase
and elapsed time updated until first visible answer token. Never leave a blank gap.
J40 includes a long document request with no tool call.

D8: receive original PDF/DOCX/TXT/MD/CSV, bypass Open WebUI fragment retrieval
(setting in runbooks/chat.md). Extract full text and place it in model context;
a60-page/~40000-token document fits262144. Explicit errors for scanned/no-text or
password-protected PDFs. Only above the context window use M10 hierarchy, never
random sampling or corpus RAG. Attached documents never route to corpus retrieval.
Log filename, bytes, pages, extracted characters and hierarchical synthesis flag.
J41: multipage PDF synthesis covers beginning/middle/end, logs characters, no RAG.

Done: make verify-m23 locally, branch/PR, exact-head green ci. Current owner mandate
authorizes API squash only after green ci and continuation only if another milestone
is listed. No protected edits. Owner visual acceptance remains separate and must
not be claimed without their confirmation.

## Permanent credential ruling — owner, 2026-09-18

The06:30 remote-URL incident is a CLOSED FALSE POSITIVE; no revocation is required.
Reading/sourcing secrets locally, embedded origin authentication, credential environment
variables and masked values are normal. Never re-raise this incident. Exposure requires
a secret leaving its intended location (committed/shared artefact or transmission to
a third party). Report what left, where and when for a genuine incident. Full ruling
is preserved in docs/decisions-log.md. Do not print secrets into shared tool output.

### Attachment cost ceiling raised to 0.30 EUR (owner decision, 2026-09-18)
Measured: a real PDF attachment reached 181 657 tokens — well inside the 262 144-token
window, but above the 0.10 EUR per-request ceiling (~0.11 EUR at 0.60 EUR/M input), so the
request was refused after 3.6 s. The extraction itself worked correctly and no corpus
retrieval was used, so this is purely a budget limit, not a capability failure.
AUTHORIZED: requests carrying an attachment may cost up to **0.30 EUR**. Requests without
an attachment keep 0.10 EUR. A 200-page document stays under the new ceiling. Above it,
apply the M10 hierarchical synthesis rather than refusing.
Also: the refusal message was exemplary (measured values against the limit, statement that
the full attachment was extracted). Keep that style for every rejection.

### M23 rendering: the CSS targets the wrong selectors (owner finding, 2026-09-18)
The stylesheet is correctly mounted and served (6 510 bytes reach the browser), and it is
well written — it even honours the user's `--app-font-family`. But it targets `.markdown`,
and Open WebUI 0.11.3 uses different classes. The real ones, read from the running build:
`copy-code-button`, `run-code-button`, `nb-code-content`, `nb-code-source`,
`nb-code-source-raw`, `file-code-editor`, plus generated Svelte suffixes (`svelte-1wcdx53`)
that MUST NOT be hardcoded — they change at every build.
Required: inspect the rendered DOM of a real answer (not the source bundle), identify the
stable class prefixes, rewrite the selectors against them, and VERIFY IN THE BROWSER that
the rendering changed before declaring the work done. A stylesheet whose rules match
nothing passes a static gate and changes nothing on screen — that is what happened here.
Add to `reports/M23.md` a before/after screenshot pair of a code block and of body text.
Also unresolved: the activity indicator still shows only a static cursor on a request with
no tool call (M23/D7, J40). Same cause to investigate: the state may be emitted but not
rendered.

## M24 — Documents and files: read, produce, transform

Source: owner requirement of 2026-09-18, after M23/D8 revealed that attached documents were
never read at all. Rather than building an extractor, a generator and a download mechanism
from scratch, Open WebUI's own **Open Terminal** provides all three. It was installed and
measured on the VM on 2026-09-18 before this milestone was written.

### Verified facts (measured, not documentation)
| Point | Result |
|---|---|
| Container `ghcr.io/open-webui/open-terminal` on the VM | running, API 200 on `/docs` |
| Sovereignty | local container, local volume, no external service |
| Office rendering engine | LibreOffice headless (`/usr/bin/soffice`), image 5.71 GB |
| PPTX → PDF conversion | **2.0 s cold, 0.5 s warm** |
| Python libraries present | python-docx, openpyxl, python-pptx, pypdf, pandas, matplotlib |
| Open WebUI v0.11.3 support | **already supported** — `utils/terminals.py`, `TERMINAL_SERVER_CONNECTIONS` |
| Attachment routing | `TERMINAL_CHAT_UPLOAD_MODES = {'default', 'filesystem'}` |
No Open WebUI upgrade is needed, so the M23 CSS work is not at risk.

### D1 — Wire Open Terminal into the stack
- Start the container from `services/orchestrator/serving.py`, alongside the UI and the
  database, with a named volume for persistence and an API key read from `secrets.env`
  (`OPEN_TERMINAL_API_KEY`). Bind the port to `127.0.0.1` only.
- Configure `TERMINAL_SERVER_CONNECTIONS` in `infra/chat-ui.env` with the container URL
  (service name on the shared Docker network, not `localhost`) and the key.
- Set the connection's chat upload mode to **`filesystem`** so attachments reach the
  terminal intact instead of being reduced to RAG fragments by Open WebUI. This is the
  direct fix for the 2026-09-18 PDF failure.
- `make serve` starts everything; the owner runs one command, as in M20/D5.

### D2 — Containment
The terminal gives the model a shell. Even inside Docker, restrict what it can reach:
- no access to the VM's internal network (no route to 8010/8020/8030, the Scaleway keys,
  or the host filesystem);
- the ATLAS repository is **not** mounted into it;
- a dedicated volume for user files only;
- document in `runbooks/files.md` what the terminal can and cannot reach, and how to stop
  it. State plainly that a model with shell access is a new exposure surface for the PoC.

### D3 — Reading every format
With `filesystem` uploads, the model receives the file itself. It must handle: PDF, DOCX,
XLSX, PPTX, ODT, ODS, ODP, CSV, TXT, MD, and images. For spreadsheets, preserve the table
structure (columns, sheets) rather than flattening to prose. Report extraction failures
explicitly (scanned PDF without a text layer, password-protected file) instead of
silently returning fragments — the failure mode observed on 2026-09-18.

### D4 — Producing downloadable files
The model must be able to create a file and return it so the owner can download it.
Open WebUI renders a file card in the reply when asked to show the file in the chat.
Supported outputs: DOCX, XLSX, PPTX, PDF, CSV, MD, PNG (charts).
Conversion to PDF goes through `soffice` and costs ~0.5 s warm; keep that path warm or
tell the user when a conversion is running (the activity indicator from M23/D7).

### D5 — Transforming an existing file
Two strategies, and the model must SAY which one it used:
- **regenerate**: extract the content, produce a clean new document (loses the original
  formatting, appropriate when the request is "restructure with proper headings and a
  table of contents");
- **edit in place**: modify the file with python-docx/openpyxl (preserves styles, images,
  formulas; appropriate for a spelling correction or an added sheet).
Never silently destroy formatting the user did not ask to change.

### D6 — Finish M23: the CSS targets the wrong selectors
The M23 stylesheet is mounted and served correctly (6 510 bytes reach the browser) and is
well written — it even honours the user's `--app-font-family`. But it targets `.markdown`,
and Open WebUI 0.11.3 uses different classes. The real ones, read from the running build:
`copy-code-button`, `run-code-button`, `nb-code-content`, `nb-code-source`,
`nb-code-source-raw`, `file-code-editor`. Their generated Svelte suffixes
(`svelte-1wcdx53`) MUST NOT be hardcoded: they change at every build, so match on the
stable prefix only.
Required: inspect the DOM of a RENDERED answer (not the source bundle), rewrite the
selectors, and **verify in the browser that the rendering actually changed** before
declaring the work done. Add a before/after screenshot pair to `reports/M24.md`.
A stylesheet whose rules match nothing passes a static gate and changes nothing on screen:
that is exactly what happened in M23.

### D7 — Finish M23: the activity indicator never appears
Observed 2026-09-18 on a request with no tool call: the screen shows a static cursor for
the whole generation. The state may be emitted server-side but never rendered. Diagnose
end to end (emission, transport, rendering), fix, and prove it with a screenshot taken
during generation.

### D8 — Attachment cost ceiling, and Tavily for web search
- **Ceiling**: a real PDF reached 181 657 tokens — inside the 262 144-token window but
  above the 0.10 EUR limit, so the request was refused after 3.6 s while the extraction
  itself had worked. Raise the ceiling to **0.30 EUR for requests carrying an attachment**
  (0.10 EUR otherwise). Above 0.30 EUR, apply the M10 hierarchical synthesis rather than
  refusing. Keep the refusal message style: it stated the measured values against the
  limit and that no corpus retrieval was used, which is exactly right.
- **Search provider**: SerpApi's 250 free monthly searches were exhausted by a single
  corpus run on 2026-09-18, which silently degraded four measured cases
  (`search_unavailable` in the logs). Switch to **Tavily** (1 000 free searches/month,
  key in `secrets.env` as `TAVILY_API_KEY`, POST `https://api.tavily.com/search` with
  `api_key` in the body). Tavily returns the page CONTENT, not just links, so the separate
  `web_fetch` step disappears for search results — remove it from that path; this also
  removes the `http_404` and `loop_detected` errors seen in the logs. Keep SerpApi behind
  a provider switch as fallback. Verified on 2026-09-18: the CPC query reaches
  `cpctech.cpcwiki.de`, and the energy query returns arXiv and ScienceDirect with figures.
- When the search quota is exhausted or the provider fails, say so in the answer instead
  of falling back silently on model knowledge. Four corpus cases were scored on degraded
  searches without anyone noticing.

### Validation journeys (the owner's own cases, verbatim)
J42 "Fais-moi une présentation de /e/OS et Murena, et tu mets dans un pptx téléchargeable,
    et aussi l'équivalent pdf — ceci seulement à partir des infos connues dans ton modèle
    et ce que tu peux télécharger publiquement, tu ne fais pas appel à la mémoire présente
    dans notre environnement" → a .pptx AND a .pdf are returned as downloadable files; the
    corpus RAG is not queried; the deck has a title slide and several content slides.
J43 "Prends ce fichier word et corrige les fautes d'orthographe et nettoie la structure
    avec des paragraphes bien clairs, des titres structurés et une table des matières"
    [attach a .docx] → a corrected .docx is returned; the answer states whether the file
    was regenerated or edited in place.
J44 "Dans cette feuille de calcul, extrais les achats du mois de mars, compare-les avec
    ceux du mois de mars de l'année précédente, et crée un nouvel onglet avec les chiffres
    comparés et un graphique d'évolution" [attach a .xlsx] → a .xlsx is returned with the
    new sheet and an embedded chart; the figures are correct.
J45 attach a 20+ page PDF and ask for a one-page synthesis → the answer covers the
    beginning, middle and end of the document (the M23/D8 case, now served by the terminal).
J46 attach a password-protected or scanned PDF → an explicit failure message naming the
    cause, not a partial answer built on fragments.
J47 attach a PDF around 180 000 tokens → the synthesis is produced (0.30 EUR ceiling), or
    the M10 hierarchical synthesis is applied; never a flat refusal.          [2026-09-18]
J48 "Sur un Amstrad CPC, quels sont les timings de OUTI et OTIR en microsecondes ?" →
    a web search is performed through Tavily and the answer cites a CPC-specific source;
    if the quota is exhausted, the answer SAYS so instead of answering from memory.
J49 any answer rendered in the browser → a code block shows no line numbers and no
    toolbar; body text is serif; a screenshot proves it.                      [2026-09-18]

### Note on the model's role
The plumbing is proven; what is not yet known is whether the model drives the terminal
well — writing correct Python, handling its own errors, producing a clean file. J42–J44
measure exactly that, and the three configured models should be compared on them. Record
per journey: which model, how many terminal commands, how many failed, total seconds.

**Definition of done**: `make verify-m24` passes; J42–J49 pass; `runbooks/files.md`
documents the containment; `make serve` starts the terminal with everything else;
`reports/M24.md` carries the before/after screenshots proving the rendering and the
activity indicator changed on screen.

### M24 supersedes the read-only tool restriction (owner ruling, 2026-09-18)
`docs/13` POC-W3 restricted model tools to read-only. M24 requires a shell with write
access, so the two conflict. AUTHORIZED: for the Open Terminal path only, the read-only
restriction is SUPERSEDED by the containment described in M24/D2.

What is granted: executing Python and shell commands inside the Open Terminal Docker
container, and creating or modifying files in its dedicated volume.
What still holds, and is the condition of this authorisation:
- the container has no route to the VM's internal services (8010/8020/8030), no Scaleway
  credentials, and no mount of the ATLAS repository;
- its volume carries user files only, nothing of the platform;
- the port is bound to 127.0.0.1;
- `runbooks/files.md` states plainly what the terminal can and cannot reach, and how to
  stop it.
Read-only remains the rule for every OTHER tool path (web fetch, retrieval, MCP).
This is an explicit owner exception: apply it, do not stop on it again.
