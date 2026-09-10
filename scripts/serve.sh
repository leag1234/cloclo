#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ -f .env ]]; then set -a; source .env; set +a; fi
export PATH="$PWD/.venv/bin:$PATH"
export PYTHONPATH=".:services/model-gateway${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m services.orchestrator.serving
