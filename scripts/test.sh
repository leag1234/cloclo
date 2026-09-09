#!/usr/bin/env bash
set -Eeuo pipefail
export PYTHONPATH="services/edge-bff${PYTHONPATH:+:$PYTHONPATH}"
python3 -m unittest discover -s tests -v
# The protected workflow calls make test; execute the full milestone gate there.
if [[ "${GITHUB_ACTIONS:-}" == true && "${ATLAS_VERIFY_M0:-}" != 1 ]]; then
  make verify-m0
fi

# CI has no GPU credentials: run the protected static M1 contract.
if [[ "${GITHUB_ACTIONS:-}" == true ]]; then
  env -u SCW_ACCESS_KEY -u SCW_SECRET_KEY make verify-m1
fi
