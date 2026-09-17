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
