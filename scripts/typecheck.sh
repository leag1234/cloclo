#!/usr/bin/env bash
set -Eeuo pipefail
python3 -m mypy --strict services infra/gpu.py scripts/verify_m0.py evals/harness.py evals/agent.py evals/__init__.py tests
