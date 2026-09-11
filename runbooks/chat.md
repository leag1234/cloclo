# Chat M7

Run `make serve` with Scaleway/SerpApi variables injected (`.env` optional).
Python: requirements-dev.txt; Docker Linux. No cloud credentials transmitted to the UI.
From your workstation: `ssh -L 3000:127.0.0.1:3000 -L 8020:127.0.0.1:8020 user@vm`,
then http://localhost:3000; select atlas. The 8020 tunnel serves citations.
Ctrl-C stops the services; atlas-chat-ui/index volumes are preserved. Private logs:
BRAIN/interactions/YYYY-MM-DD.jsonl. Budget/stop: 120 s and 0.05 EUR per request.
Local single-user UI; no HTTPS and no public exposure. No GPU created by serve.
Open WebUI v0.11.3, pinned digest, image ~7.14 GB; interface/branding preserved.
Dependency imposed by MISSION; LibreChat alternative discarded for a single integration.
Configuration/license source: https://docs.openwebui.com/reference/env-configuration/
and https://github.com/open-webui/open-webui/blob/v0.11.3/LICENSE .

Stop serve before `make verify-m7`: tests use the same local ports.
For background launch of the agent, the group PID is in BRAIN/m7-serve.pid.
The execution field distinguishes live, record (real test call), and replay (no cost).
Old lines without this field have an undetermined origin: do not sum their costs.


## Integrated chat journeys (M17)

Use `/project create <name>` in chat to create and select a project. In another
chat, use `/project use <name or ID>` to share its stored facts. Names must be
unambiguous. Each selection creates a separate conversation in that project.
The selection receipt carries the project and conversation IDs; preserve it in
chat history. `/project leave` clears selection. The existing project page at
`http://localhost:8020/project-ui` supports reviewing and deleting stored facts.
Project selection is per conversation, never a global server setting.
Project scope is resolved before image handling. Current uploads are described
using only server history from the selected conversation. The description is
stored there, without image bytes; resend an image to inspect it again. Client
history from previous projects (including images) is never forwarded in project mode.

Title, tags, follow-up and autocomplete auxiliary generation are explicitly
disabled because the PoC has no independent auxiliary budget. Persistent UI
configuration is disabled so these settings also apply to an existing UI volume.
Restart `make serve` to apply them; chat history in the volume is preserved.

Image generation needs a warm image GPU: run `make serve-imagegen` from a shell
with the project credentials before asking for an image. This explicit command
prepares the model and shuts the GPU down after ten minutes. `make serve` never
provisions a GPU. Generation requests retain the 0.05 EUR and 120-second caps;
GPU preparation is a separately budgeted infrastructure operation.

`make test-journeys` starts an isolated test stack and replays recorded external
responses through the real HTTP adapter. `JOURNEYS_LIVE=1 make test-journeys`
records real provider/web/image exchanges, requiring credentials and a warm image
GPU. Both write `BRAIN/eval/journeys.json`; do not run while the chat ports are in
use. Never label replay output as live evidence.

`make test-serve-idempotent` is separate from CI: it starts `make serve` twice and
checks readiness after the second start. Run only with no active user session.
The launcher requests graceful shutdown of its previous process and replaces
only its named containers with matching images; persistent volumes are retained.
