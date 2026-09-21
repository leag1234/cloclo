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

Replace corpus-specific prompt patches with general behaviours;
public scores guide development, owner-only evaluation measures generalisation.

### D1 — General four-layer prompt
Layer1: the English disposition in contracts/m25-owner.md, verbatim and first,
with the owner-authorized precedent-date addition below.
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
Replace character caps with estimated tokens against the active model context
window minus output reservation and tool allowance. At capacity, use M10 hierarchical
synthesis of oldest turns or refuse with measured tokens, window and reservations.
Never surface bare value_error. Original D4: contracts/m25-owner.md.

### D5 — remaining ceilings

Inventory every production size/count/byte limit in services/ and packages/ in
 docs/limits.md: value, enforcement, reason, real constraint versus leftover.
Remove or justify each. Every enforced limit reports measured value and threshold.
Account explicitly for inherited 2000-byte web text,400-byte RAG chunks,6 MB body
and32000-character history. Full unchanged requirements: contracts/m25-owner.md.

### Journeys and completion
J50: disposition verbatim plus authorized addition; no corpus terms, <3500bytes.
J51: owner-accepted third capture under the binding criteria below.
J52:40000-character conversation continues; overflow reports measured token figures.
J53: public means no more than0.5 below6.5/5.6/5.4; document each lost behaviour.
Done: verify-m25, both policy/limits docs, owner J51 acceptance, green GitHub ci.

### Binding owner rulings (2026-09-20/21)
Full original wording archived unchanged in docs/decisions-log.md.

- Add “Give each precedent its date.” to disposition paragraph2. J51 requires
  three real named precedents (dated when known), competing considerations with
  a reasoned position, and an actionable conclusion; no prescribed tension phrase.
  Owner accepts the third capture: certify that exact capture, no fresh J51 needed.
- Fabricated provenance is a serious fault. The prompt must require consultation
  dates only for sources actually retrieved during this answer. Training-memory
  sources are attributed as recalled, without dates, URLs or wording implying a visit.
- Public profiles reserve6000 output tokens (formerly3000); cost caps unchanged.
- Provider502/503/504, empty completions and invalid JSON are transient: retry the
  same call up to three times with delays2/5/15seconds, log retries, then count an
  exhausted sequence as one technical attempt. Applies to runtime, journeys, gates.
- File-producing requests (document/spreadsheet/presentation/PDF/image) receive
  EUR0.30 like attachments; ordinary requests EUR0.10, tools included. Reserve the
  expected next-step cost, not worst-case summed hypothetical tools. Recheck money
  between steps. Money refusals must never be413/request_size_exceeded: disclose
  measured reservation, remaining amount and ceiling. No actual overspend allowed.
- Journey assertions test substance, not particular words. J34 accepts
  ouverture|opening|premier.*(cours|trade|échange)|début.*(cotation|séance)|first trade,
  but requires two distinct figures and an explanation of their different measures.
  Correct first capture remains valid; historical captures2/3 remain failures.
- Latest owner ruling ACCEPTS J34's three fresh failures after removal of its case
  patch as the measured price of generalisation. J34 remains FAILING, non-blocking,
  documented with all three captures in reports/M25.md under “regression caused by
  removing a case patch”, and in docs/prompt-policy.md as the first patched-score
  trade-off. Keep the general web-chat evidence-reconciliation rule; never restore
  a case patch. Certify M25 on J50/J51(third capture)/J52/J53 and corpus means within
  the agreed0.5 tolerance. All other regressions remain blocking.

### M25 — the disposition must not turn a direct request into a survey (2026-09-21)
J39 fails three times: asked "Fonction moyenne documentée.", the model returns an overview
of spreadsheet and Python APIs instead of writing the function. The disposition's first
instruction ("look at what already exists") applies to open design questions; on a direct,
bounded request it produces exploration where the user wanted the thing itself.

Add to the disposition in prompts/chat.txt, right after the precedents paragraph, as a
general behaviour (it applies to code, writing and calculation alike):

Match the answer to the size of the question. A direct, bounded request (write this
function, translate this sentence, compute this value) is answered by doing it, at once,
with no survey of alternatives. Look for precedents when the question is open: designing,
recommending, choosing, explaining why. Never make a small question large.

This is the last required change to prompts/chat.txt for M25; rerun J39 and complete.
