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
