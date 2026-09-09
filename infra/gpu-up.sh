#!/usr/bin/env bash
# vLLM --enable-prefix-caching is configured by gpu.py cloud-init.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a
source services/model-gateway/local.env
[[ ! -f .env ]] || source .env
set +a
exec python3 infra/gpu.py up
