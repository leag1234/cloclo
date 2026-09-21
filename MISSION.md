# MISSION — ATLAS-0

Read AGENTS.md, docs/11/14; implement docs/13-poc-spec.md.
M0–M24 delivered; M25 current and last. History: docs/decisions-log.md.

Done = make verify-mN + green GitHub ci. Protect workflows/CODEOWNERS/verify-*;
never weaken assertions. Branch/PR only, no main push. Current human mandate
controls merge and subsequent milestones.

## Permanent constraints

Contracts before code; useful answers through public HTTP. AGENTS.md governs
secrets, dedicated project, costs and cleanup. GPU2 EUR/h,30 EUR/milestone;
bounded risk accepted with alerts. Run infra/gpu-down.sh at session end.

Requests: <=10 tools; budgets below. Image loading is separate (contracts/m13,
M20 startup wait). Declare live/replay honestly; use real recordings. Do not
re-verify completed milestones without request/regression; report BRAIN-based skips.
CI regression gates remain mandatory.

Update BRAIN before risk/session end; BLOCKERS on blockage.
MISSION <=8000 bytes; archive history verbatim in decisions-log.

### Journey rules (permanent)

R1: Before coding, write intent and six natural phrasings independent of templates.

R2: Each capability: six phrasings (three without obvious keyword), <=4-word input,
unaccented, uppercase, English, another language, negative. Attachments: >=2/request.

R3: Assert useful content; calls/routing alone never pass.

R4: Owner defects become permanent verbatim dated journeys; never ease wording.

R5: Test-only/unreachable service modules fail the gate.

R6: Rejections give measured values/thresholds plainly to user and journal.
Separate image bytes from model tokens. Preserve safely parsed user questions.

## Standing facts and credential ruling — never archive these facts

Owner confirms replaced credentials and API write/delete/push. Incidents2026-09-13/15
closed;2026-09-18 06:30 remote-URL incident CLOSED FALSE POSITIVE. No revocation or
reconfirmation. Local sourcing, embedded origin auth and masked values are normal.
Exposure requires a secret leaving its intended location: report what/where/when;
never print secrets. Original wording: docs/decisions-log.md. Owner attests
GPU2 EUR/h,30 EUR/milestone,800 EUR/month, active alerts. Hypothetical shutdown
defects are notes. External failure counters reset each session.

M24 delivered; its owner containment exceptions remain binding in docs/decisions-log.md.

## M25 — Intellectual disposition, not test-case patches

Replace case patches with general behaviours. Public scores guide development;
owner-only evaluation measures generalisation.

### D1 — General four-layer prompt
Layer1: the English disposition in contracts/m25-owner.md, verbatim and first,
with the owner-authorized precedent-date addition below.
Layers2–4: capabilities/tools (search conditions, budgets, failures), language/form
(resolved language, English code, no plan narration/boilerplate), safety/evidence
(untrusted text, no invented citations, privacy). No named-case/domain patches.
Delete Z80, solargraphy, IPO and all case-specific sentences. Whole file <3500 bytes.
Contract: contracts/m25-owner.md.

### D2–D3 — generality and independent evaluation

Binding contract: contracts/m25-owner.md (unchanged criteria).
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
Never surface bare value_error. See owner contract D4.

### D5 — remaining ceilings

Inventory every production size/count/byte limit in services/ and packages/ in
 docs/limits.md: value, enforcement, reason, real constraint versus leftover.
Remove or justify each. Every enforced limit reports measured value and threshold.
Account explicitly for inherited 2000-byte web text,400-byte RAG chunks,6 MB body
and32000-character history. Contract: contracts/m25-owner.md.

### Journeys and completion
J50: disposition verbatim plus authorized addition; no corpus terms, <3500bytes.
J51: owner-accepted third capture under the binding criteria below.
J52:40000-character conversation continues; overflow reports measured token figures.
J53: public means no more than0.5 below6.5/5.6/5.4; document each lost behaviour.
Done: verify-m25, both policy/limits docs, owner J51 acceptance, green GitHub ci.

### Binding owner rulings (2026-09-20/21)
Original wording: docs/decisions-log.md.

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
of spreadsheet and Python APIs instead of writing the function. The precedents instruction misapplies open exploration to a bounded request.

Insert verbatim after precedents in prompts/chat.txt (code, writing, calculation):

Match the answer to the size of the question. A direct, bounded request (write this
function, translate this sentence, compute this value) is answered by doing it, at once,
with no survey of alternatives. Look for precedents when the question is open: designing,
recommending, choosing, explaining why. Never make a small question large.

Last required prompt change for M25: rerun J39 and complete.

### M25 — J53 threshold: accept 4.8 for deepseek, but name the cases that fell (2026-09-21)
deepseek reaches at most 4.8 against the 4.9 threshold, a loss of 0.6 from the 5.4 measured
on 2026-09-20. The case patches supported deepseek more than the other two profiles; losing
them costs it more. That is the measurement this milestone exists to produce.

ACCEPTED at 4.8, on one condition: `reports/M25.md` lists, per profile, WHICH cases lost
points against the 2026-09-20 run, with their before/after scores. If the drops fall on the
cases the patches targeted (SpaceX, Z80, solargraphy), the result is coherent and the
milestone completes. If a case with no patch dropped by more than 2 points, name it as a
suspected side effect of the disposition and propose a general correction — never a patch.

On the C03/GLM technical failures: retry as transient per the 2026-09-21 ruling; if they
persist, record C03 as not run for that profile rather than blocking the milestone.

### M25 — certified on qwen and glm; deepseek degraded by the disposition (owner ruling, 2026-09-21)
Measured per-case, 2026-09-20 baseline → current:
- atlas-qwen 6.067 (threshold 6.0) — passes
- atlas-glm 6.467 (threshold 5.1) — passes, +1.3 on the previous run
- atlas-deepseek 4.067 (threshold 4.8) — fails, −1.3

The losses on deepseek fall on cases that never had a patch: C02 9→5, C03 9→3, C04 5→3,
C08 9→6, C11 9→6, C13 6→3, C14 4→2. On the same cases glm gains: C02 1→8, C07 0→8,
C09 3→8. The same prompt therefore helps two models and harms the third. deepseek-v4-flash
is a small fast model; the long demanding disposition appears to crowd it out.

CERTIFY M25 on atlas-qwen and atlas-glm. Record deepseek's regression in `reports/M25.md`
as a measured finding, not a milestone failure, with the per-case table above. Do not
weaken the disposition and do not write a per-model prompt in this milestone: note the
question for a later one.

Consequence for the default-model decision, to carry forward: deepseek was the candidate
for speed and cost; it does not support the prompt that produces the other two models'
quality. glm is now the strongest on the public corpus, qwen the most balanced.

### M25 — certified on qwen and glm (owner ruling, 2026-09-21)
Measured: atlas-qwen 6.067 (threshold 6.0) passes, atlas-glm 6.467 (threshold 5.1) passes,
atlas-deepseek 4.067 (threshold 4.8) fails. deepseek's losses fall on cases that never had
a patch (C02 9→5, C03 9→3, C08 9→6, C11 9→6, C13 6→3) while glm gains on the same cases
(C02 1→8, C07 0→8, C09 3→8): the same prompt helps two models and harms the small fast one.

CERTIFY M25 on atlas-qwen and atlas-glm. Record deepseek's regression in reports/M25.md as
a measured finding, not a milestone failure. Do not weaken the disposition, do not write a
per-model prompt here. Complete the
milestone: commit, PR, CI, merge.
