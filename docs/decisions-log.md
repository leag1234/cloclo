# Archived milestone definitions and decisions

Moved from MISSION.md during M20; historical text below is preserved.

# MISSION — ATLAS-0

Build the PoC defined in `docs/13-poc-spec.md`, milestone by milestone, with each milestone proven by `make verify-mN` **green on GitHub CI** (not just locally).

Golden rule: a milestone only exists when its CI is green. Your word means nothing; the `ci` job means everything. You never modify `.github/workflows/` or `scripts/verify-*` (protected by CODEOWNERS).

The order is **mandatory**. M0 then M1 first: without CI and without reproducible infrastructure, everything else is unverifiable.

---

## M0 — Verifiable Framework
**Goal**: the verification loop runs end-to-end on an empty project.
**Deliverables**: service structure (skeletons), `make` target, CI executing lint+typecheck+tests+secret-scan, `eval-harness` capable of running empty.
**verify-m0** verifies: `make lint test` green; `make eval-smoke` executes (0 cases ok); an `edge-bff` healthcheck responds 200; the secret scan passes; the anti-model-name grep (docs/02 AC-ARC-4) finds nothing outside `services/model-gateway`.

## M1 — Reproducible GPU Infra + Gateway

**Goal**: prove that a GPU node is created by script, serves a model via vLLM, then is destroyed. Deliverables: `infra/gpu-up.sh`, `infra/gpu-down.sh`, config `services/model-gateway/`.

**verify-m1** validates ON THE VM (GPU access + Scaleway creds), NOT on GitHub CI (no GPU nor secrets). On CI: static control of scripts. On the VM, `make verify-m1` runs ONE cycle: creates the node, verifies vLLM responds on /v1/models, launches a control inference, archives a simple bench under BRAIN/bench/, destroys the node, all in under 20 min. The proof of M1 is the successful execution of `make verify-m1` on the VM. See contracts/m1.md.

## M2 — Ingestion + RAG
**Goal**: Hybrid RAG with resolvable citations.
**Deliverables**: ingestion (pdf/docx/md/html) → chunks + metadata + embeddings; BM25+dense+reranker search; generation with `chunk_id` citations.
If `evals/golden/` does not yet contain E1/E2/E3, run `generation/KIT-E1-E2-E3.md` on the provided corpus (status `genere-a-valider`, awaiting human validation).
**verify-m2** verifies on the multilingual corpus (corpus/): ingestion produces chunks with metadata; retrieval achieves **recall@8 ≥ 0.70** on the E1 golden set (M2 gate; target 0.85 eventually, adjustable via M2_RECALL_MIN); every citation in a response points to a chunk actually retrievable. M2 does not create a GPU.

## M3 — Agentic Harness + Web Tools
**Goal**: bounded tool loop, safe web search + reading.
**Deliverables**: state machine (hard budgets POC-P6), tools `web_search` (SerpApi), `web_fetch` (trafilatura, robots.txt, anti-SSRF), `rag_search`, `calculator`.
**verify-m3** verifies: POC-E4 ≥ 90%; SSRF tests (private IPs refused) + robots.txt + fetch ceiling; the 4 budgets trigger a clean stop (integration test); POC-E6 executable end-to-end.

## M4 — Cascade + UI + Escalation
**Goal**: S→L routing, fallback on GPU failure, UI connected.
**Deliverables**: routing classifier, escalation to Scaleway Generative APIs, UI (Open WebUI/LibreChat) connected to the gateway.
**verify-m4** verifies: POC-E8 ≥ 85%, zero under-routing on critical cases; fallback: if the local model is unreachable (simulated failure by cutting the local endpoint, WITHOUT creating a paid GPU), the gateway switches to Scaleway escalation and still responds. The UI (Open WebUI/LibreChat) is a visual PLUS, NON-blocking for this PoC gate.

## M5 — Full Evals + Telemetry
**Goal**: measure, compare, trace.
**Deliverables**: `make eval` (all suites, HTML report with diff + breakdown by language, < 20 min), calibrated judge (POC-R2), cost/latency dashboard, prefix-cache hit exposed.
**verify-m5** verifies: `make eval` complete green and under budget/time; report generated; telemetry metrics present (tokens, cost, TTFT, tok/s, cache hit).

## M6 — Hardening + Final Bench + GO/NO-GO Report
**Goal**: quantified proof for decision making.
**Deliverables**: load bench (POC-P1..P9), minimal input filter, `make demo` (full scenario), GO/NO-GO report auto-generated from measurements.
**verify-m6** verifies: POC-P1..P9 measured and archived; `make demo` runs a RAG + web + escalation journey without error; `reports/GO-NOGO.md` generated with real figures.

---

### Human Checkpoints (outside your responsibility, humans do these)
After M1 (infra/budget), after M3 (10 manual requests), after M5 (judge calibration), after M6 (decision). Between these points, you advance alone and log in BRAIN/.

### M1 — Protection Confirmation (Prerequisite AUTO-2 / POC-I1/I2 lifted)
Budget protections CONFIRMED and ACTIVE: Scaleway alerts at 50% and 80% of €800 (SMS + email), verified in console. GPU shutdown guaranteed by the trap in verify-m1.sh (destruction at end of test no matter what) and by the explicit call to gpu-down.sh. GPU type: automatic selection by gpu-up.sh (L40S-1-48G priority, available). The agent is AUTHORIZED to create a billed GPU to execute make verify-m1. This confirmation must not be requested again.

### M2 — Generation Engine Confirmed
For the RAG GENERATION step (drafting responses with citations), use the L model via Scaleway Generative APIs (ESCALATION_MODEL, already configured in .env, endpoint SCW_GENERATIVE_BASE_URL). The budget ceiling is ACTIVE and confirmed. The small CPU model serves ONLY for embeddings/reranking, not for generation. You are authorized to call Generative APIs to generate and produce reliable citations.

### M3 — Resumption Authorization (provider_error diagnosis)
The provider_error errors on E4-004/013/018 likely come from a truncated response (output token limit too low) when the context is long (fetched web page). You are AUTHORIZED to: (1) increase the gateway output token limit (e.g., 512 -> 2048), (2) truncate/summarize large web contents BEFORE passing them to the model (respecting context ceiling, docs/03 REQ-MOD-004), (3) retry E4/E6 attempts as many times as necessary within the per-request budget limit (€0.05). Scaleway function-calling is supported (official doc verified). Continue until E4 >= 90% then merge. Do not lower the E4 threshold, do not modify correction keys.

### M5 — Reference Judge for Cross-Calibration
The reference judge for cross-calibration is **gpt-oss-120b** (Scaleway Generative APIs, OpenAI family, distinct from the production judge glm-5.2 AND the system under test Qwen — independence of the 3 families is respected). Use the already configured Scaleway endpoint (SCW_GENERATIVE_BASE_URL, same key). Calculate Cohen's κ between glm-5.2 scores and gpt-oss-120b scores on the eval sample. No external access nor human judge required for the PoC; human calibration remains pre-GA.

### M5 — E9 Translation without FLORES (PoC)
Downloading FLORES-200 fails (mirror unavailable/authentication). For the PoC, the E9 suite uses ONLY cases already present in evals/golden/e9_traduction.yaml (written and validated business cases, false friends + terminology). Do NOT run fetch_flores.py, do not block on FLORES. The FLORES-200 extension is a post-PoC action. E9 is evaluated on available 'valide' cases.

### M5 — Calibration Fix (Judge JSON transport)
Scaleway's strict structured-output mode (response_format=json_object / json_schema) produces invalid doubly-encapsulated JSON (prefix `{"{"`). You are AUTHORIZED to:
1. NOT use strict json_schema/json_object mode for judge calls; request JSON in the prompt (text output) and parse it on the client side in a TOLERANT manner (extract the first valid JSON object {...} from the response, ignore potential wrapping). This is NOT "fixing a score": it is transport parsing, the judge's score is never modified.
2. Retry a bounded series of calls (budget < 3 EUR) to produce the calibration.
3. If a judge call remains unparsable after tolerant extraction, exclude it from the κ calculation and SIGNAL it in the report (best-effort calibration on valid cases).
The reference judge remains gpt-oss-120b (family independence preserved).

## M7 — Test UI + Interaction Observability
**Goal**: make the system queryable via a chat UI, with structured and exploitable logging of EVERY interaction, to analyze quality/latency/routing.

**Deliverables**:
- `make serve`: starts all necessary services in one command (http gateway + retrieval + adapter), without GPU by default (everything goes through Scaleway escalation; local GPU is activated only if GPU_LOCAL=1).
- **OpenAI-compatible Adapter**: exposes `POST /v1/chat/completions` (standard OpenAI protocol) and routes it to the internal pipeline (RAG /answer, web search, or escalation depending on request nature). Allows connecting any OpenAI client, including Open WebUI.
- **Open WebUI** in Docker, pointed at the adapter, accessible on port 3000 of the VM. The user opens http://<vm-ip>:3000 and chats with the system.
- **Structured logging per interaction**: each request produces a JSON line in `BRAIN/interactions/<date>.jsonl` with AT LEAST: timestamp, question, réponse, modèle_utilisé (local|escalade), route_decision (simple|complexe), latence_ms (retrieval, génération, total), chunks_récupérés (doc_id + score), citations (resolved chunk_id), tokens (in/out), coût_eur, any errors/timeouts. No secrets nor keys in logs.

**verify-m7** verifies: `make serve` starts services; the adapter responds to a `/v1/chat/completions` request end-to-end (response + citation); a structured log line is produced in BRAIN/interactions/ with required fields; Open WebUI is reachable (HTTP 200 on port 3000). Without GPU (escalation only) by default.

**Out of scope**: multi-user authentication, HTTPS, public exposure (port remains on VM; access via SSH tunnel or direct IP depending on network config).

## PoC v2 (M8→M13) — see docs/15-poc-v2.md

### GitHub Token Incident — ASSUMED RISK (human decision, 2026-09-10)
The GitHub token was exposed outside the VM. The project owner examined the risk and DECIDES not to revoke it for the duration of the PoC: scope limited to a private repo without sensitive data, prototyping context, rotation cost judged higher than residual risk. The incident is thus CLOSED as a blocker: this is not a revocation, it is an explicit and tracked risk acceptance.
Deferred action: rotate token before any production deployment.
The agent MUST NO LONGER block on this point nor ask for confirmation again.

### M13 — GPU Budget Attested (human decision, 2026-09-11)
The Scaleway consumption API is not readable by the project's IAM token; the budget is therefore ATTESTED here by the owner:
- Global monthly budget: €800; consumption to date: < €5; available margin: > €795.
- Hourly GPU ceiling: GPU_MAX_EUR_H=€2.00/h (the L40S is ~€1.47/h).
- GPU spending ceiling for M13: **€30 maximum** for the entire milestone.
- Active Scaleway budget alerts at 50% and 80% (SMS + email).
You are AUTHORIZED to create a GPU for M13 within these limits, provided you shut it down after each test (trap already in place). Do not query the billing API anymore: this attestation stands as proof.

### BUDGET RISK RULE (replaces any prior interpretation) — 2026-09-11
The financial risk related to the GPU is BOUNDED and ACCEPTED by the owner:
- hourly ceiling GPU_MAX_EUR_H = €2/h; M13 ceiling = €30; monthly budget €800;
  SMS+email alerts active at 50% and 80%. Worst case of a GPU forgotten overnight: ~€15.
- This risk is CONSCIOUSLY ASSUMED. A theoretical defect in shutdown (edge case of inventory, unlikely homonym, etc.) IS NOT a reason to stop: it is an improvement note to log in the report, then you CONTINUE.
- You are AUTHORIZED and REQUIRED to provision the GPU for M13, deploy Flux, test, then shut down with infra/gpu.py down. If shutdown returns an error, you log it and signal it — you do not block the milestone before having attempted it.
- Only remaining reasons to STOP: effective breach of ceiling (€30), secret leak, destructive action outside the strike-poc project, modification of a protected file. Preventive audit of shutdown scripts is NOT part of this.
Any new security objection regarding gpu.py/gpu-down must be PROPOSED in the report, never used to block. Provision.

## M16 — English localization of the public repository (PRIORITY)
**Context**: the repository is now PUBLIC. All documentation and code intended for external readers must be in English. This is a blocking presentation issue for an open-source project.

**Scope — TO TRANSLATE into English**:
- `README.md` — **to CREATE** (currently missing): project overview, architecture summary, quickstart (install, `make serve`, tunnel, UI), milestones, licence note. This is the first thing a visitor sees.
- `docs/*.md` (~2200 lines), `contracts/*.md` (~940), `runbooks/*.md` (~150)
- `MISSION.md`, `AGENTS.md`
- All comments, docstrings, log and error messages in `services/`, `scripts/`, `infra/`, `tests/` (~65 files contain French)

**Scope — MUST NOT be translated (French is intentional there)**:
- `corpus/` — the multilingual test corpus (7 languages) is the point of the test set
- `evals/golden/` — questions in FR/DE/ES/IT/AR/ZH are deliberate
- `BRAIN/` — local working journal, not tracked by git

**Constraints**: translation only — do NOT change behaviour, identifiers used by other code, file names, or test semantics. Keep commit messages and future PR titles in English.

**verify-m16** checks: README.md exists and is structured; no French function words in docs/contracts/runbooks/README/MISSION/AGENTS; no French in code comments/messages; and the multilingual corpus and golden sets are still intact (not translated away).

### M16 — Translation method (mandatory)
Do NOT build a segmentation/numbered-transport pipeline for translation. Translate each file DIRECTLY: read the file, produce the English version, write it back, one file at a time. No invariant validation, no concurrent calls, no cache layer. If a file is large, translate it in a few sequential passes over its sections, still writing plain text. Keep markdown structure, code blocks, links and anchors intact. Files to translate, in this order: README.md (create), runbooks/*.md, AGENTS.md, MISSION.md, contracts/*.md, docs/*.md. Commit after each file or small group.

## M17 — Integration: make existing capabilities actually usable (PRIORITY)

**Why this milestone exists.** M8–M15 are all "done": unit tests pass, CI is green,
every `verify-mN` succeeds. Yet a real user session found that **only one capability
out of seven works end to end**. Every `verify-mN` validated *components in isolation*,
never a *user journey* through the chat interface. A capability that answers a direct
function call but is unreachable from the UI is NOT delivered.

**New rule**: a milestone is "done" only when a **user journey through the public chat
API** proves it. Component tests are necessary, never sufficient.

### Defects found in the 2026-09-11 user session (all must be fixed)
1. **Language drift** — reply in English while the conversation was in French, after an
   image was sent. The vision path (likely also web and image paths) does not carry the
   conversation-language rule from `prompts/chat.txt`.
2. **Image generation fails** — a French request to create an image of a dancing dog →
   `stream_error`; UI shows "Uh-oh! There was an issue with the response."
3. **Projects unreachable** — M9 exists in the backend (`services/retrieval/project_api.py`)
   but a user cannot create or use a project from Open WebUI.
4. **Web search never returns a final answer** — UI shows two intermediate tool-call notices then nothing. Tools run; no answer is delivered.
5. **Auxiliary Open WebUI functions always fail** — title/tags/follow-up return
   `provider_error`/`cost`/`request_stopped` on every message. Either make them work
   (dedicated light model + own budget) or disable them with an explicit note.
   Silent permanent failure is not acceptable.
6. **`make serve` is not idempotent** — fails when containers or a previous `serving.py`
   process still exist. It must clean up its own resources first.

### Deliverables
- Fix defects 1–6.
- `tests/journeys/`: automated **user journeys** that call the **public chat API**
  (`POST /v1/chat/completions` on the adapter, exactly as the UI does) and assert on what
  the *user* receives. Internal function calls do not count as journeys.
- `make test-journeys` runs them and writes `BRAIN/eval/journeys.json`.
- **Live vs CI**: journeys needing the web, a provider or a GPU (J4, J6) run **live on the
  VM** and are **replayed from recorded cassettes in CI**. J4 must not create a GPU on
  every run: record once, replay afterwards; a live J4 run is explicit (`JOURNEYS_LIVE=1`).
- `make test-serve-idempotent` (J8) is a **separate** target, never part of the CI gate:
  it restarts the stack and must not run while a user session is active.

### Language criterion (explicit, so it cannot be gamed)
A reply "matches" the question language when a language detector (e.g. `langdetect`,
or a simple French/English function-word ratio) classifies the reply as the same
language as the last user message, with ≥ 0.8 confidence. Code blocks are excluded
from the check.

### Projects: realistic UI path
Open WebUI has no native "project" object. J5 is satisfied by ANY of these, as long as
a user can do it from the UI without editing files: (a) a project exposed as a dedicated
Open WebUI model with an attached knowledge base; (b) a chat command
(`/project create <name>`, `/project use <name>`) handled by the adapter; (c) an Open
WebUI tool/function. Document the chosen path in `runbooks/chat.md`.

### Journeys that must pass
J1 plain question → non-empty final answer, in the question's language.
J2 corpus question → answer with ≥ 1 resolvable citation.
J3 image sent → description, **in the conversation language**.
J4 a French request to generate an image of X → an image is returned (live on VM; cassette in CI).
J5 project → a fact stated in conversation A is used in conversation B of the same
   project; a different project does NOT see it.
J6 web question → tools run **and a final answer is delivered** (live on VM; cassette in CI).
J7 auxiliary calls (title/tags/follow-up) → no error, or explicitly disabled + documented.
J8 `make test-serve-idempotent` → second consecutive `make serve` succeeds (separate target).

**Nice to have (not blocking)**: expose the configured models distinctly (generalist,
code, vision) so Open WebUI's arena can compare them for the quality-evaluation phase.

**Definition of done**: `make verify-m17` passes. The gate itself performs a real call
to the public chat API and checks the reply; it does not trust the report alone.

### M17 — Decision: project-scoped image history (2026-09-11)
The leak you found is real and CORRECT to report: in `chat_pipeline.py`, any image in
the history triggers `process_vision` BEFORE `process_project`, and `vision.py` forwards
every client message to `/vision/complete` without project validation.

DECISION: images must be **scoped to the current project**, not refused.
- Resolve the project scope FIRST, then build the vision payload from messages belonging
  to the current project only. Reorder `process_project` before `process_vision`.
- `vision.py` must receive only in-scope messages; it must never receive history from
  another project (or from outside any project when a project is active).
- Journey J5 (`projects_isolated`) must cover this exact case: image in project Alpha,
  switch to Beta, ask a question → no Alpha content reaches vision. Keep
  `tests/test_project_vision_scope.py` as a permanent regression test.

You are AUTHORISED and REQUIRED to fix this yourself: `chat_pipeline.py` and `vision.py`
are your own, unprotected files. Finding a leak in your own code is not a reason to stop —
it is the work. Only stop if a PROTECTED file would have to change, or if fixing it would
require weakening isolation. Fix it, prove it with J5, then continue M17.


## M18 — Conversation integrity and image fidelity (user-test corrections)

Source: real user session of 2026-09-12. Capabilities now work individually, but the
**conversation breaks as soon as a non-text capability is involved**, and image
generation ignores explicit user constraints. Text-only multi-turn conversation is
confirmed working and must not regress.

### D1 — Follow-up after retrieval is treated as a new request (blocking)
Observed: after a RAG answer on an uploaded PDF, "translate what you just wrote into German" (asked in French) triggered a NEW retrieval ("Retrieved 1 source") then failed.
Required: a follow-up that refers to the assistant's previous answer ("translate that",
"summarise it", "shorter", "in German") must operate on the **previous turn**, not
re-enter retrieval/web/vision routing. Classify follow-ups before routing.

### D2 — `context_exceeded` after image generation (blocking)
Observed: after an image was generated, "you forgot the roller skates" (asked in French) returned
`context_exceeded`.
Cause: the generated image (base64 data URI) is kept in the conversation history sent to
the model. Required: store images **by reference**, never re-inject base64 into the model
context. A user must be able to iterate on a generated image ("add X", "same but Y").

### D3 — Intent ignored when an image is present
Observed: "could you edit this image?" (asked in French) produced an unsolicited description.
Required: the presence of an image must not force description. Read the request:
describe / analyse a specific point / extract text / compare / edit. Editing an existing
image is NOT supported by the current model: say so explicitly and offer what is
possible (describe, or generate a new image from a description). Never answer something
that was not asked.

### D4 — Premature give-up on web search timeout
Observed: a first web attempt timed out; the assistant answered "I could not obtain the
information" and redirected the user to news sites. On a second explicit request it
searched again and found a correct, sourced answer.
Required: at least one automatic retry (different phrasing or source) before giving up.
Only report failure after retries are exhausted, stating what was attempted.

### D5 — Interface labels in a random language
Observed: status labels ("Intermediate step completed: tool call" (displayed in French)) appeared in
French then in German within the same conversation.
Required: interface/status labels are FIXED strings, never produced or translated by the
model. Language of labels follows the UI locale, not the model output.

### D6 — Image generation ignores explicit constraints
Observed: "cat dancing with a dog, roller skates, pink sunglasses" (asked in French)
produced the animals and the pink glasses, no roller skates.
Diagnosis (confirmed in `services/model-gateway/image_worker.py` and `image-model.json`):
`unsloth/FLUX.1-schnell` with `num_inference_steps=4`, `512x512`,
`max_sequence_length=256` (which **TRUNCATES longer prompts** — the roller skates were at
the end of the sentence), fixed `manual_seed(42)` (same prompt always yields the same
image), and no prompt rewriting.

**DECISION: stay on FLUX.1-schnell** (Apache-2.0, freely usable commercially, no gated
download). FLUX.1-dev was considered and rejected for this PoC: it is gated on Hugging
Face and released under a **non-commercial licence**, which would block any production
use. Document this trade-off in `runbooks/`.

Required, within schnell's design:
- `max_sequence_length=512` — stop truncating prompts (primary suspected cause);
- `1024x1024` instead of 512x512;
- `num_inference_steps`: raise to the highest value that still helps on a distilled
  model (schnell is trained for few steps; measure 4 vs 8 and keep the better);
- **random seed** per generation, returned with the image so a user can reproduce one;
- **rewrite the user request into a structured English image prompt** before generation
  (subjects, attributes, scene, style), as mainstream systems do. This is the main lever
  left on a distilled model: log both the original and the rewritten prompt;
- `guidance_scale` stays 0.0: this is schnell's documented setting, NOT a defect;
- raise the worker watchdog from 85 s to 180 s to accommodate 1024x1024.
If, after these changes, explicit constraints are still dropped, report it with evidence
(prompt, rewritten prompt, seed, image) so the human can decide whether the licence cost
of FLUX.1-dev is worth paying. Do not silently accept a truncated prompt.

### Non-regression
Text-only multi-turn conversation, RAG with resolvable citations, web search with a final
sourced answer, vision description in the conversation language, dev API auth/quotas and
MCP confirmation must all keep working.

### Journeys (extend `tests/journeys/`, same rules as M17: public chat API only)
J9  RAG answer, then "translate your answer into German" (asked in French) → German translation of the
    PREVIOUS answer, no new retrieval, no error.
J10 image generated, then "add X" (asked in French) → a new image is returned, no `context_exceeded`.
J11 image sent with "can you edit it?" (asked in French) → explicit statement that editing is not
    supported + what is possible; NOT an unsolicited description.
J12 web search whose first attempt fails → automatic retry, final sourced answer.
J13 status labels are fixed strings in the UI locale across a whole conversation.
J14 image generation with three explicit constraints → the prompt is NOT truncated, is
    rewritten, uses a random seed and 1024x1024; a vision check reports how many of the
    three constraints are present, and the report records prompt, rewritten prompt, seed
    and the per-constraint result. A score below 3/3 does not fail the gate but MUST be
    reported as evidence for the model-choice decision.

**Definition of done**: `make verify-m18` passes; J1–J14 all pass through the public chat
API; the licence note is present.

### M18 — SerpApi availability confirmed (2026-09-13)
The three recorded SerpApi failures (timeout, search_unavailable, timeout) are
HISTORICAL evidence from an earlier session, not a current outage. Availability has been
verified by the owner: the account is healthy (Free plan, 244 searches remaining, 6 used
this month). The provider is WORKING.

Therefore: the "three technical failures" stop rule is RESET for SerpApi. Delete or
ignore BRAIN/m18-serpapi-failure.json as a blocking record, run the live journeys again
(fresh attempt counter), and continue. Never treat a stored failure from a previous
session as a reason to refuse a first attempt in the current session: the counter is
per-session, not permanent.

If SerpApi fails three times WITHIN THIS SESSION, record it and validate J6/J12 from
cassettes instead, then continue M18 — a transient search outage must not block the
whole milestone.

### Credential rotation completed (2026-09-13)
CONFIRMED by the owner: the exposed GitHub token has been REVOKED and replaced. The new
token is in secrets.env and in the git remote, with write access verified (API write
returned 201, delete returned 200). The incident is CLOSED. The new token was never
transmitted in clear text. Resume PR/CI/merge for M18; do not ask for this again.

## M19 — Explicit intent, explicit language, locked settings

Examples below are English glosses. The exact French acceptance inputs are
preserved in [the M19 journey cases](tests/journeys/m19-cases.json); tests must
use those originals, including their unaccented variants.

**Root cause.** A second real user session (2026-09-13, after M18) found three failures
that share ONE cause: **decisions taken upstream by heuristics are never carried through
to the model**. The model is then left to guess, and guesses wrong.

| Symptom observed | What actually happens |
|---|---|
| "draw me a five-legged sheep…" → a text answer, no image | a regex decides whether to generate; `image_request()` only matches a verb IMMEDIATELY followed by image/dessin/photo, so 3 natural phrasings out of 4 are missed |
| "I cannot draw images. I am a text assistant…" (with a redirect to DALL·E/Midjourney) | `prompts/chat.txt` declares NO capability (grep count = 0); the model sincerely believes it cannot |
| "describe this image" (French) → answer in English | `question_language()` correctly returns `fr`, but the result is only used to pick status LABELS; the detected language is never injected into the vision prompt |

### D1 — Let the MODEL decide when to generate an image
Replace the upstream regex with a declared tool, exactly like `web_search` and
`rag_search`, which work reliably.
- Declare `generate_image(prompt: str)` as a function/tool available to the model.
- Remove `image_request()` from the routing path (keep it only, if useful, as a cheap
  pre-hint — never as the sole gate).
- The model must handle: "draw me a sheep", "make me a portrait of X",
  "I would like to see a dragon", "generate an image of X", "can you depict…",
  and the English equivalents.
- It must NOT trigger generation for "analyze this image", "describe the attached image",
  "edit this image".

### D2 — Declare capabilities in the system prompt (and lock them)
`prompts/chat.txt` is 5 lines and mentions neither vision nor image generation. Restore
an explicit capability section: corpus retrieval with citations, web search and page
reading, exact calculation, **image analysis**, **image generation**, project memory,
MCP tools with confirmation. State plainly that the assistant DOES have vision and image
generation and must never claim otherwise nor redirect the user to third-party tools.
When a capability genuinely fails, say what failed — never "I cannot do this".

### D3 — Impose the detected language on every path
`question_language()` works but its result is discarded. Required:
- inject the resolved language explicitly into the prompt of EVERY path (chat, vision,
  web, image rewrite, follow-up): e.g. "Answer in French." — do not rely on the model
  inferring it from a three-word message;
- make detection robust to unaccented and uppercase French ("describe this image (unaccented French)"
  currently returns None); fall back to the conversation language, then to the UI locale,
  never to a hardcoded default;
- short messages (< 5 words) must inherit the conversation language.

### D4 — Lock the settings that already regressed twice
These values were silently lost before and nothing detects it. Add a permanent test
(`tests/test_settings_lock.py`, run in CI) asserting:
- `prompts/chat.txt` declares image analysis AND image generation;
- every prompt used by a model path carries a language instruction;
- `scripts/run_agent_auto.sh` waits 180 CI attempts (not 60);
- `image_worker.py`: `max_sequence_length=512`, `1024x1024`, variable seed,
  watchdog ≥ 180 s;
- `image-model.json` stays `FLUX.1-schnell` (Apache-2.0).
Any future change to these must break the test loudly, not silently.

### Journeys (extend `tests/journeys/`, public chat API only)
J15 "draw me a five-legged sheep dancing with a blue cow" → an image is
    returned (tool-driven, no regex).
J16 "make me a portrait of a cat" and "I would like to see a dragon" → images returned.
J17 "analyze this image" / "describe the image" → NO generation; a description instead.
J18 "can you generate images?" → a clear yes; never a redirect to DALL·E/Midjourney.
J19 "describe this image" (3-word French message, image attached) → description **in
    French**. Same test with an unaccented variant "describe this image (unaccented French)".
J20 a French conversation that includes a web search and an image generation → every
    answer AND every status label stays in French throughout.

**Non-regression**: everything validated by M17 and M18 (J1–J14) must keep passing.

**Definition of done**: `make verify-m19` passes; J1–J20 pass through the public chat
API; `tests/test_settings_lock.py` is part of the standard test run.

### M19 — External dependencies must not block delivery (2026-09-15)
M19 has been blocked three times by external services (GPU out of stock, then "SerpApi
timeouts") although its substance — imposed language, declared capabilities, tool-based
image routing, locked settings — depends on neither. SerpApi has been verified working by
the owner: HTTP 200 in 0.66 s, 229 searches left. The timeouts are therefore client-side.
Note: `services/orchestrator/web.py` uses `ClientTimeout(total=15)`, which covers search
AND page download; a heavy page exhausts it even though the search itself is instant.
Separate the budgets (connect / search / page read) and raise the page-read budget.

Rule: a journey depending on an external service (web search, image GPU) MAY be validated
from an existing cassette when the live attempt fails, PROVIDED the report declares, per
journey, whether it was `live` or `replay`. Replay is honest; silence is not. Never
fabricate a result. Milestone delivery must not wait for a third party.

## M20 archive boundary

The preceding historical text was moved from MISSION.md. Active requirements
remain in MISSION.md; future historical decisions are appended here.
