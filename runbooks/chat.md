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

`make test-serve-idempotent` starts `make serve` twice and checks readiness after
the second start. Run only with no active user session. It is excluded from CI.
The launcher gracefully replaces only its own processes and matching containers;
persistent volumes are preserved, including during automatic-removal races.
