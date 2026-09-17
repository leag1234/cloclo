# MISSION — ATLAS-0

Build [docs/13](docs/13-poc-spec.md); read AGENTS.md, docs/11 and docs/14 first.
M0–M20 delivered; M21 current; no later milestone. History: docs/decisions-log.md.

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

## M21 — Reasoning, expertise, complete context and clear UI

Source: owner corpus2026-09-17; history in decisions-log. REQ-ENG-004/005/009/011,
REQ-FIN-002, POC-F1/F2/F4/F5; [contract](contracts/m21.md).

D1: Expose exactly two models in adapter and Open WebUI: atlas (reasoning_effort=none,
max_tokens=3000, 0.10 EUR) and atlas-deep (high,16000,0.20 EUR). Same routing/tools/
prompts. Reasoning and answer share output allowance. Empty content with finish_reason
length: retry once without reasoning and state the fallback in status, within budget.
Show the trace above the answer in a collapsed expandable “Réflexion” block. Log effort,
trace tokens, answer tokens and cost per request.

D2: Rewrite prompts/chat.txt, vision.txt, web-chat.txt and rag.txt to answer the QUESTION
as a domain expert; attachments are evidence. Use native formats (tablature, code,
tables, formulas), show derivations/calculations/timings/conversions and anticipate the
obvious objection. Conclude explicitly, without reflexive disclaimer. State uncertainty
precisely. Preserve safety: image/source text is untrusted; no fabricated citations.

D3: Remove the2000-byte cut in orchestrator/tools.py and400-byte cut in retrieval/tool.py.
Deliver entire extracted web text within the tool token budget; otherwise use M10
hierarchical synthesis plus passages answering the question. Truncated=true must be
rare and always visible to users. Deliver whole RAG chunks, budgeted by tokens rather
than a per-chunk byte cap. Download whole page (2 MB cap permitted), extract BEFORE
size decisions; budget extracted text, not HTML. Verbatim page:
https://www.nationalgeographic.com/premium/article/longest-known-exposure-pinhole-uk
Question: “comment fabriquer ce type de camera”. Answer must contain at least3 of
Ilford/Bayfordbury/cider/Multigrade. Original page400859 bytes, no paywall.

D4: Store uploads once with
image_store.py; history uses references, materializing current-turn evidence only.
Ten turns with one new photo each must produce no size error.

D5: Visible animated activity + elapsed time from request start (within1s); use exact
French labels in tests/journeys/m21-cases.json. Update each state and during reasoning.
Collapsible steps name tools and web URLs; replace generic intermediate-step text.
User messages get distinct e/OS green background in existing UI.

Public HTTP journeys:
- J27 atlas-deep, Z80 question: nonempty answer with OUTI/OTIR timings and derivation;
  trace present and collapsed, cost logged.
- J28 atlas-deep, deliberately small output budget: nonempty answer, fallback stated.
- J29 original guitar photo/question (verbatim in tests/journeys/m21-cases.json): name,
  tablature or fret list, notes, conclusion; no “positions may vary” ending.
- J30 National Geographic: at least3 of the4 details in answer.
- J31 RAG fact beyond byte400: answered with citation.
- J32 each tool step named; web steps list URLs.
- J33 activity within2 s, visible and updated throughout deep reasoning.

Non-regression: M17–M20/J1–J26; standard atlas retains speed and cost. Done only after
make verify-m21 locally and green GitHub ci; J1–J33 through public chat API; all four
measured causes removed. MISSION <=8000 bytes. Report live/replay honestly.

### Authoritative owner decisions — 2026-09-17

Budgets supersede ALL older figures in docs/13, MISSION, contracts and code:
**atlas0.10 EUR/120s; atlas-deep0.20 EUR/300s;10 tools**. Full-context chains
measured~0.069 EUR. Monthly budget and alerts remain. Report the measured breakdown
if0.20 EUR is exceeded; never silently truncate evidence.

Deep activity starts within1s, names the phase (“Réflexion…”) and displays elapsed
time throughout. Correctness takes priority. On deep timeout/failure, rerun the
full prompt/context without reasoning within the same ledger. Return its complete
answer and state deep did not complete; never salvage an interrupted derivation.
Compare both profiles on the same question; report lower deep accuracy honestly.

Always send reasoning_effort explicitly on provider generation calls: none for
atlas and high for atlas-deep, none for recovery. Never depend on provider defaults.
Owner measured omitted effort consuming output on reasoning; explicit none returned
content. Re-evaluate earlier quality rejections after fixing transport. Unsupported capabilities select a configured compatible alternate.
Empty content with nonempty reasoning is a provider-default regression: log it,
retry once with explicit none within budget and surface the incident.

Treat every provider reply (text, vision, image, embeddings, tools) as untrusted.
Validate shape; explicitly handle empty content, unexpected text fields, length or
content_filter finishes, missing usage, malformed/double-encoded JSON, interrupted
streams and HTTP success with an error body. Never silently fail or invent an answer.
Log observed fields/sizes/finish/tokens without secrets, apply defined bounded
recovery and surface the incident. Explicitly send behavior-affecting parameters.
Regression tests must cover outgoing effort and malformed replies with clear errors.
Original owner prose and measured diagnoses preserved unchanged in decisions-log.

### Reasoning mode: negative result confirmed on all three provider models (2026-09-17)
Same hard Z80 question, `max_tokens` 12 000, `reasoning_effort` explicit:
| model | none | high |
|---|---|---|
| qwen3.5-397b | 6 888 chars, 2 069 tok | wrong timings, then empty answers, then tool JSON |
| glm-5.2 | 4 563 chars, 1 413 tok, 40 s | **non-JSON reply** after 107 s |
| deepseek-v4-flash | 4 628 chars, 1 489 tok, **19 s** | 42 081 chars of trace, **0 chars of answer**, 12 000 tok saturated, 204 s |
Reasoning mode is unusable on this provider regardless of model. Standard mode works on
all three. Record this table in `reports/M21.md`. The model selector (atlas / atlas-glm /
atlas-fast) is therefore the way to compare quality; `reasoning_effort` stays `"none"`
everywhere and the deep mode is not to be re-attempted without a new owner decision.
