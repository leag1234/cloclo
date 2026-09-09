#!/usr/bin/env bash
# verify-m3 — PROTÉGÉ (CODEOWNERS). Gabarit fail-closed : échoue tant que le
# jalon n'est pas réellement livré. L'agent implémente les LIVRABLES (MISSION.md),
# jamais ce script. Au checkpoint, l'humain remplace le bloc marqueur par les
# assertions réelles appelant les artefacts produits (tests, benchs, rapports).
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
fail(){ echo "::error::verify-m3: $*"; exit 1; }
pass(){ echo "  ✓ $*"; }
echo "== verify-m3 =="
# Critères (source: MISSION.md) :
#   - POC-E4 >= 90%
#   - tests SSRF IP privées refusées
#   - robots.txt respecté
#   - plafond de fetches appliqué
#   - les 4 budgets déclenchent un arrêt propre
#   - POC-E6 exécutable
MARKER="BRAIN/m3.done"
[[ -f "$MARKER" ]] || fail "jalon non prouvé : chaque critère ci-dessus doit être rendu vérifiable par un artefact, puis validé par des assertions ici (checkpoint humain)."
# TODO(humain): remplacer la garde ci-dessus par une assertion par critère.
echo "== verify-m3 OK =="
