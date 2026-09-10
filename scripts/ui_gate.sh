#!/usr/bin/env bash
set -Eeuo pipefail
trap 'docker stop atlas-m7-test-ui >/dev/null 2>&1 || true' EXIT
export ATLAS_UI_GATE=1
bash scripts/verify-m7.sh
