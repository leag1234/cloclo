# Orchestrator M3

Owner: OWNERS. Contract: [M3](../../contracts/m3.md).
REQ-HAR-001/002/006, REQ-TOOL-001/002/004/012/013/014/015, REQ-FIN-002.

The model selects tools, the harness validates arguments and reserves cost/tokens
before each I/O. Ceilings trigger a `stopped` result with an explicit reason;
tool errors are returned to the model for bounded recovery.
Web/RAG results are untrusted; instructions remain in prompts/.

## Local Operation

From the root, with the Python environment installed:
`uvicorn services.orchestrator.app:app --host 127.0.0.1 --port 8020`.
The M2 CPU/serverless gateway must run at `ATLAS_GATEWAY_URL` (default port 8010),
and `ATLAS_RETRIEVAL_DSN` must point to the ingested M2 database. The gateway receives its
credentials via environment; `SERPAPI_KEY` remains in the harness environment.
`ATLAS_WEB_CACHE` designates SQLite (default BRAIN/web-cache.sqlite).
Do not expose this server directly without authentication; M4 UI integration.

POST `/query`: `{"question":"Combien font 7*9 ?","lang":"fr"}`.
GET `/continuation/{handle}?offset=0` reads subsequent excerpts until expiration.
Process termination via SIGTERM; no GPU required.

M3 SLO: request stop <=120s, <=10 tools, <=0.05 EUR, <=16384 tokens.
Reservations remain counted if the call fails or expires; no promise that HTTP
cancellation cancels provider billing. SerpApi cache 1h, pages 24h,
reserved quota 900/month; retain SQLite across restarts to preserve quota.

Diagnostics: examine `state`, `reason`, `tokens`, `cost`, `tool_calls`, `trace`.
JSON events `tool_finished` and `request_stopped` do not log credentials or request content.
M3 operator view: these counters per response and `BRAIN/eval/{tools,web}.json` per language;
aggregated dashboard falls under M5.
A robots/SSRF refusal cannot be bypassed. After three identical errors, log
BRAIN/BLOCKERS.md and stop; do not clear quota to unblock a search.

## Verification

`make test-web-security test-budgets`: local HTTP, DNS, robots, size and budgets.
`make verify-m3`: real E4/E6, E4 faults injected into the driver under tests/.
`ATLAS_M3_EVAL_MODE=replay make verify-m3`: strict replay of the same calls;
a modified prompt or different calls invalidate cassettes.
No mocks are imported by the runtime. Cassettes are exclusively under tests/.
E6 measures executability here with URL/date; no quality GO without key review
and human calibration of the judge. The fidelity of each sentence falls under gate E5.

M7: chat_pipeline uses harness budgets, HTTP retrieval, and resolved citations.
interactions writes received measurements and stop codes in private JSONL;
full contract and limits documented in contracts/m7.md.

M12: `packages/images.py` defines valid image messages from contract `contracts/m12.md`.
PNG/JPEG are decoded by Pillow after dimension checks; remote URLs,
unsupported formats, and cumulative overruns are rejected. This first
building block is common to future vision adapter/gateway boundaries.
The chat now accepts `text` and `image_url` parts in PNG/JPEG data URI.
Any image in history selects `/vision/complete`; text exchanges
retain the harness. The log contains metadata, tokens/cost, and vision route,
without base64, even if the provider echoes bytes back. Budget and timeout errors
remain distinct and retain a 0.05 EUR reservation.

Vision relays its complete validated response via SSE; it does not claim
to produce upstream progressive tokens. Text/project retains M11 transport.

M15: developer entry `PYTHONPATH=.:services/model-gateway uvicorn services.orchestrator.devapi:app --host 127.0.0.1 --port 8030 --no-access-log`; keys via `python -m services.orchestrator.dev_auth create <dev> --key-file <fichier-privé>`, revocation via `revoke <dev>`. ATLAS_DEVAPI_DB retains daily quotas and unknown reservations; contract contracts/m15.md. POST /v1/chat/completions now exposes text and functions in JSON or SSE, without access to private chat tools/data.

M15 Chat Protocol: dev_chat normalizes text messages and assembles deltas without executing functions. Identifiers must remain stable, complete arguments must be finite JSON objects, and names must come from declared tools. Provider stop with complete call becomes tool_calls; length remains a truncation.

M10 Selection: relevance contributions are summed using math.fsum to preserve ties regardless of Python hash seed. Existing tie-breaking by position remains deterministic; the exact provider cassette is unchanged.

M15: dev_input translates Responses/Messages histories to the same validated messages, without storing conversations. Metadata and cache are hints with no identity effect or cache guarantee; Messages effort without thinking does not activate it. Images, hosted tools, Responses storage, and thinking Messages are explicitly rejected.

M15: POST /v1/responses provides named text/function events, item identifiers, and completed/incomplete termination; store=false. The same quota is reserved before the stream and reconciled against provider usage.

M15: POST /v1/messages translates text/tool_use/tool_result and SSE message/content_block events. A truncated output remains max_tokens; costs come from the same registry per key. Experimental compatibility for clients configured without thinking or hosted tools.

M15: make test-devapi verifies the six gate criteria with recorded real streams. The large context case transmits 24,616 bytes of useful functions and verifies three remote values; double is rejected before inference for budget. The registry retains known costs and unknown reservations per key.

The chat adapter also mounts the bounded M3 harness at `/harness`: POST
`/harness/query` and GET `/harness/continuation/{handle}`. These existing
read-only endpoints retain their validation and budgets.
