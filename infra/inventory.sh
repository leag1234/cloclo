#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; [[ ! -f .env ]] || source .env; set +a
exec python3 infra/gpu.py inventory
