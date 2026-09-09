#!/usr/bin/env bash
set -Eeuo pipefail
# Tests SANS LLM live (docs/11 REQ-ENG-009). En M0 : aucun test => ok.
if command -v pytest >/dev/null && ls tests/ >/dev/null 2>&1; then
  pytest -q --disable-warnings tests/
else
  echo "(aucun test encore — M0)"
fi
echo "test ok"
