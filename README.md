# ATLAS-0

ATLAS-0 is a measurable proof of concept for a conversational assistant built on
open-weight models and European inference infrastructure. It combines document
retrieval with source citations, bounded web tools, persistent project memory,
streaming chat, and developer APIs.

The repository contains both the implementation and its requirements. Milestone
completion requires evidence from the GitHub `ci` job. See [MISSION.md](MISSION.md)
for the milestone contracts and [the PoC specification](docs/13-poc-spec.md) for
scope, quality targets, and budget limits.

## Architecture

- **Chat UI and adapter:** Open WebUI connects to the chat completion endpoint.
- **Orchestrator:** routing, streaming, project memory, and bounded tool execution.
- **Retrieval:** document ingestion, hybrid search, reranking, and resolved citations
  backed by PostgreSQL with pgvector.
- **Model gateway:** centralizes provider configuration, inference, and cost limits.
  The default chat stack uses Scaleway serverless inference and CPU retrieval.
- **Tools:** SerpApi search, guarded page fetching, retrieval, and calculation;
  MCP integrations require confirmation for writes.
- **Evaluation harness:** multilingual golden sets, replayable checks, reports,
  and local interaction telemetry.

`make serve` starts the CPU stack. The first image-generation request starts an
ephemeral GPU worker automatically and shows a loading notice. Initial loading
can take up to 15 minutes; inference retains its own time and cost allowance.
The worker launcher shuts down the GPU automatically. See [the architecture](docs/02-architecture-cible.md) and
[developer API runbook](runbooks/devapi.md) for component contracts and endpoints.

## Quickstart

Use a Linux host with Python 3.12, Docker, and sufficient disk space for the CPU
model cache and container images. Install the pinned development dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
```

Provide the configured Scaleway endpoint, API key, model roles and pricing, plus
SerpApi credentials for web search, through environment variables. The serving
script also reads an optional, ignored `.env` file. Configuration details live in
[the gateway documentation](services/model-gateway/README.md) and the
[chat runbook](runbooks/chat.md). Keep credentials out of Git.

```bash
make serve
```

From your workstation, forward the chat UI and citation adapter ports:

```bash
ssh -N -L 3000:127.0.0.1:3000 -L 8020:127.0.0.1:8020 user@your-vm
```

Open [the chat UI](http://localhost:3000) and select `atlas`, `atlas-glm`, or
`atlas-fast` to compare the configured models. Each uses explicit non-reasoning
generation with a €0.10,120-second and3000-output-token limit. See
[the M21 report](reports/M21.md) for measured quality limitations. The adapter on port
8020 serves document citations. Stop the stack with Ctrl-C; persistent database
and UI volumes remain. This is a local PoC deployment accessed through SSH.

## Verification

```bash
make lint typecheck test scan-secrets
make verify-m16
```

Individual milestones expose `make verify-mN` targets. Some require provider
credentials or explicitly budgeted GPU resources; consult the matching contract
before running them. CI uses recorded provider exchanges where configured.
Multilingual source documents and evaluation cases remain in their original
languages under `corpus/` and `evals/golden/`.

## Milestones

| Milestones | Deliverables |
|---|---|
| M0–M1 | Verification framework and reproducible GPU infrastructure |
| M2–M4 | Retrieval, bounded tools, routing and fallback |
| M5–M6 | Evaluations, telemetry, benchmarks and decision report |
| M7–M10 | Chat UI, serverless roles, project memory and large inputs |
| M11–M13 | Streaming, vision and image generation |
| M14–M15 | MCP integration and developer APIs |
| M16 | English public documentation and code prose |

See [the extended PoC roadmap](docs/15-poc-v2.md) and the milestone reports in
`reports/` for implementation details and measured limitations. A milestone list
is a scope summary; its verification evidence determines completion.

## License and attribution

This repository currently has no root license file granting a general license to
its code. Public visibility alone does not grant redistribution rights.
[NOTICE](NOTICE) records upstream attribution. Dependencies, model weights,
Open WebUI, and evaluation datasets retain their respective licenses.

`make serve` gracefully replaces a previous launcher from the same checkout and
preserves chat/index volumes. With no active user session, run
`make test-serve-idempotent` to verify two consecutive starts; this disruptive
check is separate from CI.
