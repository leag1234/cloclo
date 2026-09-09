#!/usr/bin/env bash
set -Eeuo pipefail
python3 -m mypy --strict services scripts/verify_m0.py evals/harness.py tests
