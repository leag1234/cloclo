# MISSION — ATLAS-0

Read AGENTS.md, docs/11/14; implement docs/13-poc-spec.md.
M0–M25 delivered; M26 current and last. History: docs/decisions-log.md.

Done = make verify-mN + green GitHub ci. Protect workflows/CODEOWNERS/verify-*;
never weaken assertions. Branch/PR only, no main push. Current human mandate
controls merge and subsequent milestones.

## Permanent constraints

Contracts before code; useful answers through public HTTP. AGENTS.md governs
secrets, dedicated project, costs and cleanup. GPU2 EUR/h,30 EUR/milestone;
bounded risk accepted with alerts. Run infra/gpu-down.sh at session end.

Requests: <=10 tools; budgets below. Image loading is separate (contracts/m13,
M20 startup wait). Declare live/replay honestly; use real recordings. Owner alone runs
private evaluation: never list or inspect /opt/atlas-src/private/heldout/; keep private/ ignored. Do not re-verify completed milestones without request/regression; report BRAIN-based skips.
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

### Disposition text quoted by the current prompt (M25; prompts/chat.txt and
tests/test_prompt_policy.py read it here, do not move it)

Match the answer to the size of the question. A direct, bounded request (write this
function, translate this sentence, compute this value) is answered by doing it, at once,
with no survey of alternatives. Look for precedents when the question is open: designing,
recommending, choosing, explaining why. Never make a small question large.

## M26 — Live acceptance proved, daily probe, attachment path, retrieved sources

Binding contract: contracts/m26-owner.md (D1–D7, J54–J60, evidence format). Read it first.
D1 live acceptance is proved by scripts/verify-m26.sh from fresh captures and provider
completion ids absent from the repository; a report's own mode field proves nothing.
D2 weekday daily probe on six real cases; the owner PDF is read only at
/opt/atlas-src/private/fixtures/owner-174p.pdf and never enters the repository.
D3 attachment flag on every path, 300 s deadline, hierarchical synthesis.
D4 the code or the content always reaches the user. D5 failures name what failed: a
budget refusal is never a 504 (R6 already binds). D6 remove own worktrees and branches.
D7 a URL is cited only if retrieved in the same conversation; facts about existing
things that may have changed trigger a search.
Add `make m26-live` writing the evidence format; extend tests/ci_regressions.py to 26.
Done: make verify-m26 locally with live evidence, green GitHub ci, probe in cron.
