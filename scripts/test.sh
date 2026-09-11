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
  ATLAS_M5_MODE=replay make verify-m5
  ATLAS_M6_MODE=replay make verify-m6
  ATLAS_M7_MODE=replay make verify-m7
  SCW_GENERATIVE_API_KEY=test-only ATLAS_M8_MODE=replay make verify-m8
  make verify-m9
  make verify-m10
  make verify-m11
  SCW_GENERATIVE_API_KEY=test-only ATLAS_M12_MODE=replay make verify-m12
  make verify-m13
fi
