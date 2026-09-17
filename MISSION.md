# MISSION — ATLAS-0

Build [docs/13](docs/13-poc-spec.md); read AGENTS.md, docs/11 and docs/14 first.
Settled history remains unchanged in [decisions log](docs/decisions-log.md),
not mandatory context. M0–M20 delivered; M21 current; no later milestone.

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
Ilford/Bayfordbury/cider/Multigrade. Original page measured400859 bytes, no paywall.

D4: The32 MB body increase (601a548) only unblocked photos. Store uploads once with
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

### Budget exception — owner decision 2026-09-17
AUTHORIZED: deep/high0.10 EUR per request supersedes docs/13 POC-P6; all other paths
retain0.05 EUR. Measured deep output9700 tokens costs~0.035 EUR at3.60 EUR/M;
0.05 EUR reservations reject heavy requests. This owner exception is authoritative;
do not block on this contradiction.

### M21 — Asynchronous deep mode (owner decision, 2026-09-17)

Measured: deep reasoning alone took ~96s; the120s deadline caused recovery with
an incorrect derivation. Standard returned a correct6888-character Z80 answer;
deep used another platform's18/23-cycle timings.

1. **Deadline:** atlas-deep300s; atlas120s. D5 activity starts within the first
second, names the phase (“Réflexion…”) and displays elapsed time throughout.
A slow correct answer is acceptable.
2. **Recovery:** on deep failure/timeout, rerun the question without reasoning
with the full prompt and context, within the budget. Return the complete answer
and state that deep did not complete. Never salvage an interrupted derivation.
3. **Correctness:** J27 must verify correct timings and derivation. Compare both
profiles on the same question; report lower deep accuracy honestly, never force
an assertion to pass.

### Budget raised for full-context tool chains (owner decision, 2026-09-17) — supersedes ALL earlier per-request caps
AUTHORIZED, and this is now the single authoritative statement of per-request caps:
- `atlas` (standard): **0.10 EUR** per request (was 0.05).
- `atlas-deep`: **0.20 EUR** per request (was 0.10).
Any lower figure in docs/13, in earlier MISSION entries or in code comments is SUPERSEDED.
Do not stop on a contradiction with those older figures; apply these.

Rationale, measured on 2026-09-17: removing the 2 000-byte web cut and the 400-byte RAG cut
(M21/D3) multiplied the context carried through a tool chain. A question that triggers five
tools now costs ~0.069 EUR in deep mode and exceeded the old caps BEFORE the answer was
produced — including in standard mode. The caps had been sized for truncated content; they
must be sized for full content, which is the whole point of this milestone.

Cost control stays in place: tool-call count limits, wall-clock deadlines (120 s standard,
300 s deep) and the monthly budget with alerts are unchanged. If a request still exceeds
0.20 EUR, that is a genuine signal — report it with the measured breakdown rather than
silently truncating context again.
