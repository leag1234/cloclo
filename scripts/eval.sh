#!/usr/bin/env bash
set -Eeuo pipefail
# Harnais d'évals. M0 : tourne à vide proprement. L'agent l'étoffe aux jalons M2+.
MODE="${1:---smoke}"
COUNT=$(find evals/golden -name '*.yaml' 2>/dev/null | xargs -r grep -lc 'statut: valide' | wc -l || echo 0)
echo "eval $MODE — suites avec cas validés: $COUNT"
echo "(harnais amorcé ; implémentation des exécuteurs par l'agent en M2/M3/M5)"
echo "eval ok"
