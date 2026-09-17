# MISSION — ATLAS-0

Build the PoC defined in [docs/13](docs/13-poc-spec.md). Read AGENTS.md,
docs/11 and docs/14 before implementation. Historical milestone definitions,
attestations and one-off decisions have moved, unchanged, to
[the decisions log](docs/decisions-log.md); they are not mandatory session context.
M0–M19 are delivered; the current milestone is M20. No later milestone is defined.

A milestone is complete only after its `make verify-mN` gate and the GitHub `ci`
job are green. Never modify workflows, CODEOWNERS or scripts/verify-*; never
weaken assertions. Branches and PRs only; no direct pushes to main. Follow the
current human mandate for merge authorization and subsequent milestones.

## Permanent constraints

- Requirements and contracts precede code. Test through the public chat API;
  unit tests alone do not prove a delivered capability.
- No secrets in repository, logs or prompts. Remain in the dedicated cloud project.
- GPU hourly ceiling: 2 EUR/h; milestone ceiling: 30 EUR. Alerts are active.
  Record estimated cost before provisioning and shut down experimental GPUs
  through infra/gpu-down.sh before ending a session. Bounded GPU risk is accepted
  by the owner; hypothetical cleanup defects alone are not blockers.
- Inference requests share one budget: <=120 seconds, <=0.05 EUR, <=10 tool calls.
  The existing image-generation contract measures initial weight loading
  separately; M20 exposes a bounded startup wait separately from inference.
- Every external-service journey reports whether it is live or replay. Replay
  requires an actual recording; never invent one or silently substitute results.
- Do NOT re-verify completed milestones merely to start another task. Read their
  merged outcome from BRAIN. Recheck only on explicit request or visible regression.
  State which completed-milestone verifications were skipped. CI regression gates
  remain mandatory.
- Update BRAIN/STATUS.md, TASK.md and JOURNAL.md before risky operations and at
  session end. Record unresolved blockers in BLOCKERS.md. Report facts honestly.

## M20 — Real-usage journeys, honest failures, unified startup

Source: owner sessions of 2026-09-13 and 2026-09-15. Exact acceptance inputs and
language variants are preserved in [the journey cases](tests/journeys/m20-cases.json).
Requirements: REQ-ENG-004/005/009/011, REQ-INF-012/013, REQ-FIN-002 and POC-P6.

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

### Defects and deliverables

D1: Two attached images are rejected with a misleading context error and an empty
question in the journal. Instrument and reproduce before fixing. Earlier guesses
about base64 reinjection, context size and malformed dimensions were wrong.
Support several attachments; two 1024x1024 images normally fit the vision context.

D2: Requests to edit or combine existing pictures must explicitly say that editing
and compositing are unsupported, and offer image description or generation from a
text description. Never substitute an unsolicited description or a silent error.

D3: Every generation logs the original request, rewritten prompt, seed, model,
resolution and steps so disappointing output can be diagnosed and reproduced.

D4: For the owner's sheep-and-cow request, check that the rewrite preserves every
attribute on both subjects, particularly pink glasses on both. Report actual
per-constraint visual evidence. If the rewrite is correct but the generated image
misses constraints, report a model limitation. Five-legged anatomy is a known
limitation, not something to claim fixed without evidence.

D5: Users must not need a separate GPU provisioning or serve-imagegen command.
When generate_image is called and the worker is down, provision on demand, tell
the user it is starting with the expected wait, and deliver the image. Preserve
automatic shutdown after inactivity and all cost protections.

D6: Every service validates required configuration before startup side effects.
Missing variables must produce an explicit list, never a hang or KeyError.
The permanent settings lock includes those required-variable lists.

D7: gpu-up announces creation only after confirming that the instance exists.
Report real categories such as unavailable stock, quota or missing configuration;
never leak raw provider diagnostics or announce success before creation.

E1: Do not re-verify completed milestones (see permanent constraints).
E2: Keep MISSION.md under 8,000 bytes; move settled material without deleting it
to the append-only decisions log, which is not reread every session.

### Required public journeys

| Journey | User-visible acceptance |
|---|---|
| J21 | Two pictures plus the original compositing request: honest unsupported answer, no context error |
| J22 | Compare two pictures: meaningful comparison using both |
| J23 | Original edit question with one picture: honest unsupported answer (2026-09-13) |
| J24 | Original multi-subject drawing: generated image, recorded prompt/rewrite/seed and per-constraint assessment (2026-09-15) |
| J25 | Drawing with worker down: startup notice, automatic provisioning and image delivery |
| J26 | Missing required variable: explicit startup refusal naming it |

Definition of done: make verify-m20 passes locally and on GitHub CI; J1–J26 pass
through the public chat API; MISSION.md stays under 8,000 bytes and the decisions
log exists. Record the approved merge and completion in BRAIN. No unmeasured image
quality claim or replay presented as live evidence is acceptable.

## Standing facts — never archive these (they are active rules, not history)
- **GitHub token**: the exposed token was REVOKED and replaced on 2026-09-13; write access
  was verified (API write 201, delete 200). The incident is CLOSED. Do not ask for
  confirmation again, do not stop on it.
- **GPU budget**: attested by the owner. `GPU_MAX_EUR_H=2.00`, 30 EUR cap per milestone,
  800 EUR monthly budget with alerts. A theoretical shutdown flaw is a note, not a stop.
- **External services**: a failure counter is per-session, never permanent. A stored
  failure from an earlier session is not a reason to refuse a first attempt today.
- When archiving to `docs/decisions-log.md`, move HISTORY only. Anything that must be
  applied on every session stays in MISSION.md.
