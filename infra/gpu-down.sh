#!/usr/bin/env bash
# infra/gpu-down.sh — délègue au moteur unique infra/gpu.py, qui applique les 6
# garanties de la spec fermée (propriété par tag atlas-m1 + projet, JSON validé,
# erreurs non masquées, terminate --wait, refus d'ambiguïté). Une seule implémentation.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; [[ -f .env ]] && source .env; set +a
exec python3 infra/gpu.py down "$@"
