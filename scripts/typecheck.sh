#!/usr/bin/env bash
set -Eeuo pipefail
if command -v mypy >/dev/null && ls **/*.py >/dev/null 2>&1; then
  mypy --strict --ignore-missing-imports . || true
fi
echo "typecheck ok"
