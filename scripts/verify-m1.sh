#!/usr/bin/env bash
# verify-m1 — PROTÉGÉ (CODEOWNERS). Gabarit fail-closed : échoue tant que le
# jalon n'est pas réellement livré. L'agent implémente les LIVRABLES (MISSION.md),
# jamais ce script. Au checkpoint, l'humain remplace le bloc marqueur par les
# assertions réelles appelant les artefacts produits (tests, benchs, rapports).
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
fail(){ echo "::error::verify-m1: $*"; exit 1; }
pass(){ echo "  ✓ $*"; }
echo "== verify-m1 =="
# Critères (source: MISSION.md) :
#   - infra/gpu-up.sh crée le nœud depuis zéro
#   - gateway /v1/models répond 200
#   - bench TTFT/tok-s archivé sous BRAIN/bench/
#   - infra/gpu-down.sh détruit instance+IP
#   - re-création complète < 20 min
MARKER="BRAIN/m1.done"
[[ -f "$MARKER" ]] || fail "jalon non prouvé : chaque critère ci-dessus doit être rendu vérifiable par un artefact, puis validé par des assertions ici (checkpoint humain)."
# TODO(humain): remplacer la garde ci-dessus par une assertion par critère.
echo "== verify-m1 OK =="
