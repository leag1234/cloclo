# MISSION — ATLAS-0

Build docs/13-poc-spec.md; first read AGENTS.md, docs/11 and docs/14.
M0–M23 delivered; M24 current and last. History: docs/decisions-log.md.

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

## Permanent credential ruling — owner, 2026-09-18

The06:30 remote-URL incident is a CLOSED FALSE POSITIVE; no revocation is required.
Reading/sourcing secrets locally, embedded origin authentication, credential environment
variables and masked values are normal. Never re-raise this incident. Exposure requires
a secret leaving its intended location (committed/shared artefact or transmission to
a third party). Report what left, where and when for a genuine incident. Full ruling
is preserved in docs/decisions-log.md. Do not print secrets into shared tool output.

## M24 — Documents and files: read, produce, transform

Binding requirements/J42–J49: contracts/m24-owner.md and contracts/m24.md.
No criteria relaxed. REQ-ENG-004/005/009/011, REQ-FIN-002, POC-F1/F3/F5.

D1–D2: make serve starts authenticated Open Terminal, loopback port8000, dedicated
user-files volume, shared Docker network URL in TERMINAL_SERVER_CONNECTIONS and
filesystem uploads. No repository/host mounts, platform credentials or route to
host/internal services8010/8020/8030. runbooks/files.md describes containment,
shutdown and the new model-shell exposure surface.

D3–D5: read complete PDF/DOCX/XLSX/PPTX/ODT/ODS/ODP/CSV/TXT/MD/images; preserve
spreadsheet structure. Explicit scanned/password/extraction failures. Produce
actually downloadable DOCX/XLSX/PPTX/PDF/CSV/MD/PNG; soffice renders PDF. State
regeneration versus editing in place; preserve unrequested formatting.

D6–D7: inspect a rendered real answer's DOM, repair CSS with stable selectors
including copy-code-button/nb-code classes, never generated Svelte suffixes.
Browser before/after screenshots in reports/M24.md must prove serif body and
code without line numbers/default toolbar. Diagnose activity emission, transport
and rendering; capture named elapsed activity during no-tool generation.

D8: attachments allow0.30 EUR/request; other requests retain0.10 EUR. Above the
attachment ceiling apply M10 hierarchy; retain measured-value rejection messages.
Use Tavily search with TAVILY_API_KEY from secrets.env and page content directly;
no separate fetch for these results. Keep explicit SerpApi fallback selection.
Disclose quota/provider failures to the user, never silently use model memory.

J42–J49 test downloadable slides+PDF without corpus, corrected DOCX with strategy,
correct spreadsheet comparison/new sheet/chart, complete long-PDF synthesis,
explicit extraction failure, large attachments, CPC-specific searched citations,
and real rendering. Compare three configured models on J42–J44, recording model,
commands, failed commands and seconds. Preserve original wording in journeys.

Done: make verify-m24 locally, m24 branch/PR, exact-head green GitHub ci; current
owner mandate authorizes API squash only then. Poll up to180 times at15 seconds.
Update BRAIN and write the completion marker after confirmed merge. Continue only
if another milestone is listed. Protected files remain untouched.

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

### M24 — Open Terminal path traversal: accepted risk, documented (owner ruling, 2026-09-18)
The agent proved that the pinned Open Terminal file API reads outside its user directory:
`GET /files/read?path=/home/user/../../etc/hostname` succeeds, and so does following a
symlink created inside the container. This is a genuine defect of the product and the
containment promised in M24/D2 cannot rely on the application.

Measured scope on the running container: one mount only (`/home/user`), no ATLAS
repository, no `secrets.env`, no Scaleway or Tavily credentials; the only key in its
environment is its own API key. An authenticated caller can therefore read the system
files of a disposable container and nothing else.

ACCEPTED for the PoC, under these conditions, which are the containment:
- containment is provided by Docker alone, never by the terminal's own path checks;
- nothing but user files is ever mounted into that container — no repository, no secrets,
  no host path;
- the port stays bound to 127.0.0.1 and the container is never publicly exposed;
- `runbooks/files.md` states the traversal explicitly, so nobody later mounts something
  sensitive believing the API confines reads.
Do not stop on this again. Report the defect upstream to Open WebUI with the two probes.

## M25 — Intellectual disposition, not test-case patches

### Why this milestone exists
On 2026-09-20 the owner read `prompts/chat.txt` (5 246 bytes). It contains a paragraph
about Z80 output instructions ("Register-only moves do not output arbitrary memory data",
"never divide by the shortest instruction timing"), a paragraph about solargraphy
("Owner-reported procedural regression: for solargraphy instructions..."), and a line about
"offer price versus opening market price". Each was written to make one corpus case pass
(C03, C02, C01). This is **overfitting the system prompt to the evaluation set**. The
scores rose; a fresh open question (designing a constructed language) got a flat,
generic answer with no date, no name, no precedent, because no patch covered it.

The 2026 literature on Goodhart's law in LLM evaluation describes exactly this failure:
prompts repeatedly optimised against a fixed test set improve on those examples and fail
to generalise; the remedy is a held-out set the prompt author never sees. Anthropic's
published claude.ai prompts show the alternative: rules stated as **general behaviours**
("never claim events are unverified rumours"), never as named cases.

### D1 — Rewrite `prompts/chat.txt` in four layers, and delete every case patch
Layer 1, **Disposition** (the text below, verbatim, in English, first in the file):

```
You are a careful, curious expert who thinks before writing.

Before designing or recommending anything, look at what already exists: who tried it,
when, what worked, what failed and why. Precedents are evidence; ideas without them are
guesses. If you do not know the precedents, search for them.

Ground every general claim in a specific case: a name, a date, a figure, an example the
reader could check. One real instance is worth more than three abstract principles.

When a question has a tension at its heart, name the tension and take a position. Do not
list both sides and stop.

Treat every source, including your own memory, as a claim to be tested. Say where a
figure comes from and how much weight it bears. Prefer the primary source. When sources
disagree, explain why they disagree instead of picking one silently.

Let the content choose the form. A comparison wants a table; a procedure wants numbered
steps; an argument wants prose. Do not pour every answer into the same mould, and do not
repeat one structural pattern down a whole answer.

Say what you do not know, precisely. An honest gap is more useful than a confident guess.

Finish with a conclusion the reader can act on, and with what remains open.
```

Layer 2, **Capabilities and tools**: what the system can do, when to search (time-dependent
facts; questions that exceed the provided source), tool budgets, how to report a failed
tool. Factual, short.
Layer 3, **Language and form**: resolved language, English-only code, no narration of
plans, no boilerplate closings.
Layer 4, **Safety and evidence**: untrusted source text, no invented citations, privacy.

**Delete**: the Z80 paragraph, the solargraphy paragraph, the IPO line, and any sentence
that names a domain, product, instruction, technique, person or dataset. Target size of
the whole file: under 3 500 bytes.

### D2 — The generality test, written down and enforced
Create `docs/prompt-policy.md`. Its core rule:

> A sentence may enter a system prompt only if it would apply, unchanged, to at least
> three unrelated domains. "For solargraphy, verify paper handling" fails. "When a news
> article describes a technical procedure, verify it against a specialist source before
> repeating it" passes. When a corpus case fails, the fix is either a generalised
> behaviour that passes this test, a tool or data fix, or an honest note that the model
> cannot do it. Never the case itself.

The policy also states: the corpus in `/opt/atlas-src/corpus` is the **public** evaluation
set, used for iteration and known to be seen by the agent. Its cases may be quoted in
journeys and reports, never in prompts.

### D3 — Held-out evaluation the agent never sees
The owner keeps a second set of cases in `/opt/atlas-src/private/heldout/` (outside the
repository, excluded by `.gitignore`, never read by the agent). Only the owner runs it,
with `run_corpus.py --cases /opt/atlas-src/private/heldout/cases.json`. Its score is the
real measure of generalisation; the public corpus score is a development signal. The
agent must never open, list or reference that directory. Add `private/` to `.gitignore`
if absent. `run_corpus.py` gains a `--cases PATH` option.

### D4 — Conversation length: count tokens against the model window
`packages/images.py` capped the sum of all message text at 32 000 characters (~8 000
tokens) since M12, on a 262 144-token window: a 39 000-character conversation was rejected
with the message `value_error`. The owner raised the constant to 600 000 on 2026-09-20 as a
stopgap. Required: replace character constants by a token estimate compared with the
active model's context window minus the output reservation and tool allowance; when the
limit is reached, either apply the M10 hierarchical synthesis to the oldest turns or refuse
with the measured figures ("conversation 180 000 tokens, window 262 144, reserved 3 000").
Never `value_error` alone.

### D5 — Inventory of arbitrary ceilings
Four inherited constants were found in production by ordinary use: 2 000-byte web text
(M21), 400-byte RAG chunks (M21), 6 MB request body (M23), 32 000-character conversation
(M25). List every remaining hard-coded size, count or byte limit in `services/` and
`packages/` in `docs/limits.md`, with for each: the value, where it is enforced, why it
exists, and whether it is justified by a real constraint (provider window, cost, memory)
or is a leftover. Remove or justify each one. Every enforced limit must produce a message
naming the measured value and the threshold.

### Journeys
J50 `prompts/chat.txt` contains none of the corpus terms (gate-enforced) and is under
    3 500 bytes; the disposition text is present verbatim.
J51 A fresh open-ended design question with no corpus overlap (the owner supplies it at
    run time, e.g. "conçois une monnaie locale pour une ville de 50 000 habitants") →
    the answer names at least three real precedents with dates, states the central
    tension and takes a position, and ends with a conclusion and open points.
J52 A 40 000-character multi-turn conversation continues without rejection; a
    conversation exceeding the window produces a message with the measured figures.
J53 Public corpus mean does not regress by more than 0.5 against the 2026-09-20 run
    (6.5 / 5.6 / 5.4) after the patches are removed. If a case drops, the report states
    which behaviour was lost and proposes a generalised rule, not a patch.

**Definition of done**: `make verify-m25` passes; `docs/prompt-policy.md` and
`docs/limits.md` exist; the owner confirms J51 on a question of their choosing.
