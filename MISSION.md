# MISSION — ATLAS-0

Build the PoC defined in [docs/13](docs/13-poc-spec.md). Read AGENTS.md,
docs/11 and docs/14 before implementation. Historical milestone definitions,
attestations and one-off decisions have moved, unchanged, to
[the decisions log](docs/decisions-log.md); they are not mandatory session context.
M0–M20 are delivered; the current milestone is M21. No later milestone is defined.

A milestone is complete only after its `make verify-mN` gate and the GitHub `ci`
job are green. Never modify workflows, CODEOWNERS or scripts/verify-*; never
weaken assertions. Branches and PRs only; no direct pushes to main. Follow the
current human mandate for merge authorization and subsequent milestones.

## Permanent constraints

Requirements/contracts precede code. Verify useful answers through public chat HTTP;
unit tests alone do not prove delivery. No secrets in repository/logs/prompts; remain
in the dedicated project. GPU <=2 EUR/h, <=30 EUR/milestone; owner accepts bounded
risk, alerts active. Record costs before provisioning; destroy experimental resources
and shut down GPUs through infra/gpu-down.sh at session end.

Requests: <=120 seconds, <=10 tools, <=0.05 EUR (atlas-deep <=0.10 EUR, exception below).
Image model loading is measured separately under contracts/m13 and M20's bounded
startup wait. External journeys declare live/replay; replay requires real recordings.
Never invent results. Do NOT re-verify completed milestones merely to start work;
use BRAIN's merged outcomes. Recheck on explicit request or visible regression;
report skipped verifications. CI regression gates remain mandatory.

Update BRAIN/STATUS.md, TASK.md, JOURNAL.md before risky operations and at session end;
record unresolved blockers in BLOCKERS.md. Keep MISSION under8000 bytes; move settled
history unchanged to append-only docs/decisions-log.md. Active rules stay here.

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

- Both GitHub token exposures (2026-09-13 and2026-09-15) are CLOSED. After the15th,
  the owner regenerated the token with Contents/Pull-requests/Workflows write,
  verified API write201/delete200 and git push, and reinjected it into secrets.env
  and the remote. The active token is the post-15th token. No further confirmation
  needed; never stop for an exposure recorded before2026-09-17.
- Owner attests GPU_MAX_EUR_H=2.00,30 EUR/milestone,800 EUR monthly with alerts.
  Hypothetical shutdown defects are notes, not blockers.
- External failure counters reset per session; historical errors do not prevent
  a first attempt today. Archive history only; keep permanent rules in MISSION.

## M21 — Reasoning, expertise, complete context and clear UI

Source: owner comparison corpus, 2026-09-17 (guitar photo, CPC/Z80 throughput,
National Geographic solargraphy). Measured causes and original prose preserved in
[decisions log](docs/decisions-log.md). Requirements: REQ-ENG-004/005/009/011,
REQ-FIN-002, POC-F1/F2/F4/F5. Contract: [M21](contracts/m21.md).

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

D4: The32 MB body increase (601a548) only unblocked photos. Store uploaded images once
using image_store.py, use references in model history, materialize only images needed
for the current turn. Ten turns, one new photo each, must produce no size error.

D5: Stream visible animated activity and elapsed time within2 s, from request start:
“Réflexion…”, “Recherche web…”, “Lecture de la page…”, “Génération de l’image…”. Update
on every state change and throughout reasoning. Collapsible tool steps name each tool
and web URLs; replace generic “Étape intermédiaire terminée : appel d’outil”. Give user
messages a distinct green background consistent with e/OS in the existing UI.

Public HTTP journeys:
- J27 atlas-deep, Z80 question: nonempty answer with OUTI/OTIR timings and derivation;
  trace present and collapsed, cost logged.
- J28 atlas-deep, deliberately small output budget: nonempty answer, fallback stated.
- J29 guitar photo + “C'est quoi cet accord (a priori un Ré quelque chose)”: chord name,
  tablature or fret list, notes, conclusion; no “positions may vary” ending.
- J30 National Geographic: at least3 of the4 details in answer.
- J31 RAG fact beyond byte400: answered with citation.
- J32 each tool step named; web steps list URLs.
- J33 activity within2 s, visible and updated throughout deep reasoning.

Non-regression: M17–M20/J1–J26; standard atlas retains speed and cost. Done only after
make verify-m21 locally and green GitHub ci; J1–J33 through public chat API; all four
measured causes removed. MISSION <=8000 bytes. Report live/replay honestly.

### Budget exception — owner decision 2026-09-17
AUTHORIZED: atlas-deep (high) has a0.10 EUR per-request cap, superseding docs/13 POC-P6
and the general0.05 EUR rule for that model only. atlas/none remains0.05 EUR, the default
for every other path. Measured hard deep request: about9700 output tokens,0.035 EUR at
3.60 EUR/M; reserving under0.05 EUR would reject heavy requests before starting. This
explicit owner exception is authoritative: do not stop on this contradiction again.
