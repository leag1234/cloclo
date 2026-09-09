#!/usr/bin/env bash
set -Eeuo pipefail
export PYTHONPATH="services/model-gateway:services/edge-bff${PYTHONPATH:+:$PYTHONPATH}"
python3 -m unittest discover -s tests -v
# The protected workflow calls make test; execute the full milestone gate there.
if [[ "${GITHUB_ACTIONS:-}" == true && "${ATLAS_VERIFY_M0:-}" != 1 ]]; then
  make verify-m0
  PYTHONPATH=".:tests:$PYTHONPATH" python3 tests/m2_gate.py
  ATLAS_M3_EVAL_MODE=replay make verify-m3
  make verify-m4
fi
