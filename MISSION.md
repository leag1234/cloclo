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

## M21 — Close the quality gap: reasoning, expertise, full context, clear UI

Source: comparison corpus built on 2026-09-17 from three real conversations run in
parallel on ChatGPT and on ATLAS (guitar chord from a photo; Amstrad CPC / Z80 throughput;
pinhole solargraphy from a web article). On all three, ATLAS was **factually correct**. On
all three, ChatGPT was **noticeably deeper**. Every cause of the gap was measured and none
of them is a model limitation.

| Case | ATLAS behaviour | Measured cause |
|---|---|---|
| Guitar chord photo | described finger positions, added a disclaimer | `prompts/vision.txt` says "describe only what is visible" — it asks for description, not expertise |
| Z80 throughput | correct figures, no derivation | `reasoning_effort: none`; ChatGPT "worked for 1m 29s" |
| Solargraphy article | honest "the retrieved text is truncated", then generic answer | `tools.py:189` keeps **2 000 bytes** of a 400 kB page |
| RAG in general | thin citations | `retrieval/tool.py:31` keeps **400 bytes** per chunk |

Principle (unchanged since docs/15): approach frontier behaviour, never excuse. Truncating
silently is an excuse; so is describing when the user asked a question.

---

### D1 — Effort switch: two levels, measured parameters
`reasoning_effort` IS supported by `qwen3.5-397b-a17b` on Scaleway (verified: the reply
carries a `reasoning` field). Measurements on a hard Z80 question:

| effort | max_tokens | trace | answer | tokens used |
|---|---|---|---|---|
| none | 3 000 | 0 | 6 888 chars | 2 069 |
| high | 6 000 | 17–23 k | **0 (empty)** | 6 000 (saturated) |
| high | 10 000 | 23 927 | 5 386 chars | 9 145 |
| high | 16 000 | 25 614 | 5 448 chars | 9 731 |

`low` / `medium` / `high` were indistinguishable on two questions: expose **two** levels,
not three. Reasoning and answer share `max_tokens`: an undersized budget yields an EMPTY
answer, which is worse than no reasoning.

Required:
- Expose two models in the adapter and in Open WebUI's selector: **`atlas`** (standard:
  `reasoning_effort=none`, `max_tokens=3000`, budget 0.05 EUR) and **`atlas-deep`**
  (`reasoning_effort=high`, `max_tokens=16000`, budget 0.10 EUR). Same routing, same
  tools, same prompts otherwise.
- Never return an empty `content` because the trace consumed the budget: if `content` is
  empty and `finish_reason` is `length`, retry once with `reasoning_effort=none` and say
  so in the status.
- Show the reasoning trace as a **collapsed** block ("Réflexion", expandable) above the
  answer — it is longer than the answer and must never bury it.
- Log per request: effort, tokens for trace and for answer, cost.

### D2 — Prompts must ask for expertise, not description
`prompts/vision.txt` ("Describe only what is visible and state uncertainties") produces an
inventory of finger positions where ChatGPT produced a chord name, a tablature, the notes
and a conclusion. Rewrite `prompts/chat.txt`, `prompts/vision.txt`, `prompts/web-chat.txt`,
`prompts/rag.txt`:
- answer the QUESTION as a domain expert would; an attached image or document is evidence,
  not the subject of the answer;
- use the domain's native formats when they help (tablature, code, tables, formulas);
- show the derivation when the answer rests on one (calculations, timings, unit
  conversions), and anticipate the obvious objection;
- conclude explicitly; never end on a reflexive disclaimer ("positions may vary…");
- keep honesty about uncertainty, but as a precise statement, not a hedge.
Keep the safety rules of the existing prompts (untrusted image text, no fabricated sources).

### D3 — Full context reaches the model; long content is synthesised, never cut
- `services/orchestrator/tools.py:189` — web page text is cut to 2 000 bytes. Remove the
  cut. Deliver the **whole extracted text** when it fits the tool budget; when it does not,
  run the M10 hierarchical synthesis on it and deliver the synthesis plus the passages that
  answer the question. The `"truncated"` flag must become rare and must always be visible
  to the user when true.
- `services/retrieval/tool.py:31` — RAG chunks are cut to 400 bytes. Deliver whole chunks;
  size the retrieval budget by tokens, not by a per-chunk byte cap.
- Web fetch: the page is downloaded whole (MAX_BYTES 2 MB is fine). Extraction must run
  before any size decision, and the decision must apply to extracted text, not raw HTML.
- Verbatim journey: fetch
  `https://www.nationalgeographic.com/premium/article/longest-known-exposure-pinhole-uk`
  (no paywall; 400 859 bytes; contains "Ilford", "Bayfordbury", "cider", "Multigrade")
  and answer "comment fabriquer ce type de camera" → the answer must mention at least three
  of those four details. Today it mentions none.

### D4 — Images by reference (the real fix behind the 32 MB limit)
Raising the request-body limit from 6 to 32 MB (commit 601a548) unblocked two phone
photos; it does not fix the cause. Open WebUI re-sends every attached image as base64 on
every turn. Store uploaded images once (`image_store.py` already exists for generated
ones), replace them by references in the history sent to the model, and re-materialise
only the ones the current turn needs. Journey: ten turns, one photo each, no size error.

### D5 — UI: show what is happening, say what the tool did, make questions readable
- **Live activity indicator.** In deep mode the model can think for a minute before any
  text appears; today the screen shows nothing and the user cannot tell the system from a
  frozen one. Stream a visible state from the first moment: an animated indicator with the
  current activity ("Réflexion…", "Recherche web…", "Lecture de la page…", "Génération de
  l'image…") and an elapsed-time counter. It must appear within 2 s of the request and
  update at every state change, including while the reasoning trace is being produced.
- **Name the tool.** "Étape intermédiaire terminée : appel d'outil" is uninformative. Show
  **which** tool ran (recherche web, lecture de page, calcul, génération d'image…), and for
  web tools the URL(s) consulted, in a collapsible block — the way ChatGPT's "Worked for
  21s" expands into its steps.
- **Readable questions.** User messages render in near-white grey and are hard to read.
  Give them a distinct background: **green**, consistent with e/OS identity.

### Journeys (verbatim, public chat API)
J27 `atlas-deep` on the Z80 question → non-empty answer containing OUTI/OTIR timings and a
    derivation; trace present and collapsed; cost logged.
J28 `atlas-deep` with a deliberately small budget → no empty answer (fallback applied and
    stated).
J29 guitar photo + "C'est quoi cet accord (a priori un Ré quelque chose)" → a chord name, a
    tablature or fret list, the notes, a conclusion; no "positions may vary" ending.
J30 National Geographic article → ≥ 3 of the 4 detail keywords present in the answer.
J31 RAG question whose answer sits beyond byte 400 of its chunk → answered with citation.
J32 tool steps → each step names the tool; web steps list URLs.
J33 any request → an activity indicator appears within 2 s and names the current activity;
    in deep mode it stays visible and updated during the whole reasoning phase.

### Non-regression
Everything validated by M17–M20 (J1–J26). `atlas` (standard) must keep its current speed
and cost.

**Definition of done**: `make verify-m21` passes; J1–J32 pass through the public chat API;
the four measured causes above are gone (no 2 000-byte cut, no 400-byte cut, expertise
prompts in place, two effort levels exposed).
