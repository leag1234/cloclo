# MISSION — ATLAS-0

Build docs/13-poc-spec.md; first read AGENTS.md, docs/11 and docs/14.
M0–M24 delivered; M25 current and last. History: docs/decisions-log.md.

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

## Standing facts and credential ruling — never archive these facts

Owner confirms replaced credentials and API write/delete/push. Incidents dated
2026-09-13/15 are closed; the 2026-09-18 06:30 remote-URL incident is a CLOSED FALSE
POSITIVE. No revocation/reconfirmation required. Local sourcing, embedded origin
authentication and masked values are normal. Exposure requires a secret leaving
its intended location: report what left, where and when. Full original wording
is preserved in docs/decisions-log.md; never print secrets into shared output.
Owner attests GPU2 EUR/h,30 EUR/milestone,800 EUR monthly, alerts active.
Hypothetical shutdown defects are notes, not blockers. External failure counters
reset each session; historical errors never block a first attempt.

M24 delivered; its owner containment exceptions remain binding in docs/decisions-log.md.

## M25 — Intellectual disposition, not test-case patches

Prompt patches overfit known corpus cases. Replace them with general behaviours;
public scores guide development, owner-only evaluation measures generalisation.

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

Layers2–4: capabilities/tools (search conditions, budgets, failures), language/form
(resolved language, English code, no plan narration/boilerplate), safety/evidence
(untrusted text, no invented citations, privacy). No named-case/domain patches.
Delete Z80, solargraphy, IPO and all case-specific sentences. Whole file <3500 bytes.
Full original requirements: contracts/m25-owner.md.

### D2–D3 — generality and independent evaluation

Binding original requirements: contracts/m25-owner.md (no criteria relaxed).
Create docs/prompt-policy.md: every prompt sentence must apply unchanged to three
unrelated domains. Case failures require a general behaviour, tool/data fix or
honest limitation; never the case itself. The public corpus is development data;
cases belong in journeys/reports, never prompts. Owner alone runs independent
private evaluation. Never inspect/list its directory. Keep private/ ignored.
Add --cases PATH to the public corpus runner.

### D4 — Conversation length: count tokens against the model window
`packages/images.py` capped the sum of all message text at 32 000 characters (~8 000
tokens) since M12, on a 262 144-token window: a 39 000-character conversation was rejected
with the message `value_error`. The owner raised the constant to 600 000 on 2026-09-20 as a
stopgap. Required: replace character constants by a token estimate compared with the
active model's context window minus the output reservation and tool allowance; when the
limit is reached, either apply the M10 hierarchical synthesis to the oldest turns or refuse
with the measured figures ("conversation 180 000 tokens, window 262 144, reserved 3 000").
Never `value_error` alone.

### D5 — remaining ceilings

Inventory every production size/count/byte limit in services/ and packages/ in
 docs/limits.md: value, enforcement, reason, real constraint versus leftover.
Remove or justify each. Every enforced limit reports measured value and threshold.
Account explicitly for inherited 2000-byte web text,400-byte RAG chunks,6 MB body
and32000-character history. Full unchanged requirements: contracts/m25-owner.md.

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

### M25 — J51 acceptance corrected (owner ruling, 2026-09-20)
The owner read the second J51 answer (BRAIN/m25-second-capture.json.gz). It names three real
precedents (Bristol Pound, Eusko, Sol Violette) with their scale and structure, states the
central tension ("liquidité contre ancrage") with both failure modes, grounds a figure in a
named study, and takes a position with a named design. **This is what the disposition asks
for, and the answer is good.** It was rejected for two reasons that were too strict:

1. "Fewer than three dated precedents": the three precedents are present; the years are not
   written. Fix the PROMPT, not the answer: add to the disposition's second paragraph
   "Give each precedent its date." Then judge on named precedents, dated when the date is
   known.
2. "Claimed source consultation without tool calls": citing a study from memory is
   legitimate scholarship, not a fake search. The failure to avoid is claiming to have
   SEARCHED or READ something during this answer without a tool call. Judge on that, not
   on the presence of a citation.

Also raise `max_tokens` for the public profiles from 3 000 to **6 000**: attempt 3 was cut at
3 000 output tokens (`finish_reason=length`) on a design question that legitimately needs
more. Cost ceiling unchanged; the reservation must account for the larger output.

Revised J51: at least three real precedents named (dated when the date is known), the
central tension stated with a position taken, a conclusion. No claim of having searched
without a tool call. Rerun J51 once with the corrected prompt and criteria. If it passes,
proceed to J53 and completion. Do not add any case-specific sentence to the prompt.

### Transient provider failures are not technical failures (owner ruling, 2026-09-21)
HTTP 502/503/504 and empty completions from the provider are TRANSIENT. On 2026-09-21 a
plain curl to the same model returned 200 three times in under half a second while the
agent's long tool-using requests were failing with 502. Such a failure does not count
towards the three-attempt stop rule until it has been retried.
Rule: on 502/503/504, an empty completion, or invalid JSON from the provider, retry the
same call up to three times with increasing delay (2 s, 5 s, 15 s) before counting the
attempt as failed. Log each retry. Only a failure that survives those retries counts as
one of the three attempts. This applies to journeys, gates and the runtime alike.

### Budget for file-producing requests (owner decision, 2026-09-21)
Measured on J42 (presentation + PDF), three attempts: the final delivery needed a
reservation of 66 633 / 61 711 / 114 476 microEUR while 47 137 / 38 271 remained of the
0.10 EUR ceiling. The web searches and page reads consume the budget first, leaving too
little to reserve the generation. No actual overspend occurred: the reservation, not the
spend, is what refused.

AUTHORIZED: a request that produces a file (document, spreadsheet, presentation, PDF,
image) gets **0.30 EUR**, like a request carrying an attachment. Ordinary requests keep
0.10 EUR. The ceiling applies to the whole request, tools included.

Two further requirements:
- A refusal caused by money must never surface as HTTP 413 / `request_size_exceeded`
  (attempt 1 did). Report the measured reservation, what remains, and the ceiling.
- The reservation must reflect the expected cost, not the worst case of every tool
  summed in advance. Re-check the remaining budget between steps instead of reserving
  everything up front; that pessimism is what refuses requests costing three times less.

### M25 — J51 final adjustment, and a rule against fabricated provenance (owner ruling, 2026-09-21)
Two distinct findings from the three captures.

**Fabricated provenance is a serious fault, and the rejection of attempts 1 and 2 was
right.** The model wrote consultation dates (for example 2024-05-23) for sources it never
visited: no search, no fetch in the trace. Add to the prompt, as a general behaviour and
never as a case patch: state a consultation date only for a source actually retrieved
during this answer; knowledge recalled from training is attributed as such, without a
date, without a URL, and without any wording implying a visit. This applies to every
domain and stays in the prompt after M25.

**The third attempt passes.** It names several dated precedents, removes the false
consultation claim, and arbitrates between risks with architecture and recommendations.
Requiring the words "the central tension is" is formalism: a design answer that sets out
the competing risks and takes a position has done the work. Revised J51 acceptance:
- at least three real precedents named, dated when the date is known;
- the competing considerations are set out AND the answer takes a position (a stated
  trade-off, a chosen option with its reason, or an explicit tension — any of these);
- a conclusion the reader can act on;
- no claimed consultation, date or URL for a source not actually retrieved.
Certify J51 on the third capture if it meets these, and complete the milestone.
