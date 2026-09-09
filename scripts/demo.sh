#!/usr/bin/env bash
set -Eeuo pipefail
echo "demo — implémentée au jalon M6 (scénario RAG+web+escalade)."
[[ -f BRAIN/m6.done ]] || { echo "M6 non atteint"; exit 1; }
