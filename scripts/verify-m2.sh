#!/usr/bin/env bash
# verify-m2 — PROTÉGÉ (CODEOWNERS). Gabarit fail-closed : échoue tant que le
# jalon n'est pas réellement livré. L'agent implémente les LIVRABLES (MISSION.md),
# jamais ce script. Au checkpoint, l'humain remplace le bloc marqueur par les
# assertions réelles appelant les artefacts produits (tests, benchs, rapports).
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
fail(){ echo "::error::verify-m2: $*"; exit 1; }
pass(){ echo "  ✓ $*"; }
echo "== verify-m2 =="
# Critères (source: MISSION.md) :
#   - ingestion pdf/docx/md/html produit des chunks+métadonnées
#   - POC-E1 recall@8 >= 0.85 sur cas valide
#   - chaque citation pointe vers un chunk récupérable
MARKER="BRAIN/m2.done"
[[ -f "$MARKER" ]] || fail "jalon non prouvé : chaque critère ci-dessus doit être rendu vérifiable par un artefact, puis validé par des assertions ici (checkpoint humain)."
# TODO(humain): remplacer la garde ci-dessus par une assertion par critère.
echo "== verify-m2 OK =="
