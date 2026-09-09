#!/usr/bin/env bash
# verify-m5 — PROTÉGÉ (CODEOWNERS). Gabarit fail-closed : échoue tant que le
# jalon n'est pas réellement livré. L'agent implémente les LIVRABLES (MISSION.md),
# jamais ce script. Au checkpoint, l'humain remplace le bloc marqueur par les
# assertions réelles appelant les artefacts produits (tests, benchs, rapports).
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
fail(){ echo "::error::verify-m5: $*"; exit 1; }
pass(){ echo "  ✓ $*"; }
echo "== verify-m5 =="
# Critères (source: MISSION.md) :
#   - make eval complet vert < 20 min et < budget
#   - rapport HTML + diff + par langue
#   - juge calibré POC-R2
#   - métriques télémétrie présentes
MARKER="BRAIN/m5.done"
[[ -f "$MARKER" ]] || fail "jalon non prouvé : chaque critère ci-dessus doit être rendu vérifiable par un artefact, puis validé par des assertions ici (checkpoint humain)."
# TODO(humain): remplacer la garde ci-dessus par une assertion par critère.
echo "== verify-m5 OK =="
