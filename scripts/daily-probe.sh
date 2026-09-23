#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ -f ../secrets.env ]]; then set -a; source ../secrets.env; set +a; fi
if [[ -f .env ]]; then set -a; source .env; set +a; fi
export PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=".:services/model-gateway"
exec flock -n BRAIN/daily-probe.lock python3 scripts/daily_probe.py
