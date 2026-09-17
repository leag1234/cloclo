# MISSION — ATLAS-0

Build [docs/13](docs/13-poc-spec.md); read AGENTS.md, docs/11 and docs/14 first.
History: [decisions log](docs/decisions-log.md). M0–M20 delivered; M21 current; no later milestone.

Completion requires `make verify-mN` and green GitHub `ci`. Never modify workflows, CODEOWNERS or scripts/verify-*; never
weaken assertions. Branches and PRs only; no direct pushes to main. Follow the
current human mandate for merge authorization and subsequent milestones.

## Permanent constraints

Requirements/contracts precede code. Prove useful answers through public chat HTTP.
No secrets in repo/logs/prompts; dedicated project only. GPU <=2 EUR/h,
<=30 EUR/milestone; owner accepts bounded risk, alerts active. Record costs before
provisioning; destroy experiments and run infra/gpu-down.sh at session end.

Requests: <=120 seconds, <=10 tools, <=0.05 EUR (atlas-deep <=0.10 EUR, exception below).
Image model loading is measured separately under contracts/m13 and M20's bounded
startup wait. External journeys declare live/replay; replay requires real recordings.
Never invent results. Do NOT re-verify completed milestones merely to start work;
use BRAIN's merged outcomes. Recheck on explicit request or visible regression;
report skipped verifications. CI regression gates remain mandatory.

Update BRAIN/{STATUS,TASK,JOURNAL}.md before risk and session end; blockers in
BLOCKERS.md. MISSION <=8000 bytes; append settled history unchanged to
docs/decisions-log.md. Keep active rules here.

### Journey rules (permanent)

R1: Write a one-sentence user intent and at least six natural phrasings before
examining implementation. Do not derive wording from regexes or prompt templates.

R2: For each capability include six phrasings, three without the obvious keyword,
a message of at most four words, unaccented and uppercase input, English and another
language, and a negative case. For attachments include at least two in one request.

R3: Assertions describe useful content received by the user, not internal function
calls or routing flags. An assertion that passes with no useful answer is invalid.

R4: Preserve every owner-reported defect as a permanent, verbatim, dated journey;
never rephrase it to make it easier.

R5: A service module called only from tests is not delivered. Unreachable modules
must fail the gate, not merely produce a warning.

R6: Every rejection identifies measured values and thresholds, in plain user-facing
language and the server journal. Never conflate image byte limits with model token
limits. Preserve the user's question when it can be safely parsed.

## Standing facts — active rules, never archive

- Token exposures2026-09-13/15 are CLOSED. Owner replaced the token after the15th
  with Contents/Pull-requests/Workflows write, tested API201/delete200 and push,
  reinjected secrets.env/remote. No reconfirmation or stop for pre-17th incidents.
- Owner attests GPU_MAX_EUR_H=2.00,30 EUR/milestone,800 EUR monthly with alerts.
  Hypothetical shutdown defects are notes, not blockers.
- External failure counters reset per session; historical errors do not prevent
  a first attempt today. Archive history only; keep permanent rules in MISSION.

## M21 — Reasoning, expertise, complete context and clear UI

Source: owner corpus,2026-09-17: guitar, CPC/Z80, solargraphy; original prose and
causes in [decisions log](docs/decisions-log.md). REQ-ENG-004/005/009/011,
REQ-FIN-002, POC-F1/F2/F4/F5; [contract](contracts/m21.md).

D1: Expose exactly two models in adapter and Open WebUI: atlas (reasoning_effort=none,
max_tokens=3000, 0.05 EUR) and atlas-deep (high,16000,0.10 EUR). Same routing/tools/
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

D5: Stream visible animated activity and elapsed time within2 s, from request start:
Use the verbatim French labels in tests/journeys/m21-cases.json. Update
on every state change and throughout reasoning. Collapsible tool steps name each tool
and web URLs; replace generic “Étape intermédiaire terminée : appel d’outil”. Give user
messages a distinct green background consistent with e/OS in the existing UI.

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

### M21 — Asynchronous deep mode (owner decision, 2026-09-17)

Measured: deep reasoning took~96s;120s caused incorrect recovery. Standard
answered correctly; deep used another platform's18/23-cycle timings.

1. **Deadline:** atlas-deep300s; atlas120s. D5 activity starts within the first
second, names the phase (“Réflexion…”) and displays elapsed time throughout.
Correctness takes priority.
2. **Recovery:** on deep failure/timeout, rerun the question without reasoning
with the full prompt and context, within the budget. Return the complete answer
and state that deep did not complete. Never salvage an interrupted derivation.
3. **Correctness:** J27 must verify correct timings and derivation. Compare both
profiles on the same question; report lower deep accuracy honestly, never force
an assertion to pass.

### Authoritative request budgets — owner decision 2026-09-17

AUTHORIZED: atlas0.10 EUR/request; atlas-deep0.20 EUR/request. These supersede ALL
older per-request figures in docs/13, MISSION, contracts and code. Full-context
chains measured~0.069 EUR; prior caps assumed truncated evidence. Keep10-tool and
120s/300s deadlines, monthly budget and alerts. If0.20 EUR is exceeded, report the
measured breakdown; never silently truncate evidence. Original decisions preserved
unchanged in docs/decisions-log.md.

### Provider default changed: always send `reasoning_effort` explicitly (owner finding, 2026-09-17)
Root cause of the repeated empty answers that blocked M21 (acquisitions 2 and 3 returned
41/37 output tokens with no text, no trace, no tools): **Scaleway changed the default**.
Measured today on `qwen3.5-397b-a17b`, same prompt, same model:
- `reasoning_effort` OMITTED → 8 422 chars of trace, 354 chars of answer, 2 369 tokens.
- `reasoning_effort: "none"` sent explicitly → 0 trace, 467 chars of answer, 123 tokens.
With the old 800-token budget the default reasoning consumed everything and `content` came
back empty, which the gateway correctly rejected.

Rule: the gateway MUST send `reasoning_effort` explicitly on every provider call —
`"none"` for `atlas`, `"high"` for `atlas-deep`. Never rely on the provider default.
Add a regression test asserting the parameter is present in every outgoing request.

Defensive measure: if `content` comes back empty while `reasoning` is non-empty, that is a
provider-default regression, not a model failure. Log it as such, retry once with
`reasoning_effort: "none"`, and report the incident rather than returning an empty answer.

This is an external change, not an implementation defect: the earlier J27/J29 "quality"
rejections must be re-evaluated once the parameter is sent explicitly.

### Never assume the shape of a provider reply (owner principle, 2026-09-17)
M21 was blocked for hours because the gateway assumed an answer would arrive in `content`.
Scaleway changed its default and the text went to `reasoning` instead, so the pipeline saw
empty answers and stopped. The lesson is NOT about where the model runs — a self-hosted
model can return an empty, truncated or oddly shaped reply just as easily. The lesson is
that the system must **verify** what it received instead of assuming it.

Rule for every provider call (text, vision, image, embeddings, tools):
- Treat the reply as untrusted data. Validate its shape before using it.
- Handle explicitly: empty `content`; text delivered in an unexpected field; `finish_reason`
  of `length` or `content_filter`; missing `usage`; malformed or double-encoded JSON;
  partial or interrupted streams; HTTP success with an error body.
- On any of these, do not fail silently and do not invent a fallback answer. Log what was
  actually received (fields present, sizes, finish_reason, tokens), apply a defined recovery
  (explicit parameters, one retry, alternate model), and surface the incident.
- Send every parameter that affects behaviour explicitly — `reasoning_effort` above all.
  Provider defaults change without notice and must never be relied upon.
- Add regression tests that feed the gateway these malformed replies and assert it degrades
  gracefully with a clear message, rather than returning nothing.
