#!/usr/bin/env bash
set -Eeuo pipefail
# Use the project virtualenv when present: dependencies are installed there,
# so tests must run with the same interpreter (otherwise ModuleNotFoundError).
if [[ "$(command -v python3)" == /usr/bin/python3 && -x "$PWD/.venv/bin/python3" ]]; then
  export PATH="$PWD/.venv/bin:$PATH"
fi
export PYTHONPATH="services/model-gateway:services/edge-bff${PYTHONPATH:+:$PYTHONPATH}"
python3 -m unittest discover -s tests -v
# The protected workflow calls make test; execute the full milestone gate there.
if [[ "${GITHUB_ACTIONS:-}" == true && "${ATLAS_VERIFY_M0:-}" != 1 ]]; then
  make verify-m0
  PYTHONPATH=".:tests:$PYTHONPATH" python3 tests/m2_gate.py
  ATLAS_M3_EVAL_MODE=replay make verify-m3
  make verify-m4
  python3 tests/ci_regressions.py
fi
