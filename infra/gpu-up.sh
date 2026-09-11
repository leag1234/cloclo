#!/usr/bin/env bash
# infra/gpu-up.sh — délègue au moteur unique infra/gpu.py, qui applique le plafond
# GPU_MAX_EUR_H (refus si le prix horaire du type retenu le dépasse) et sélectionne
# un type compatible disponible. Une seule implémentation = un seul garde-fou.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; [[ -f .env ]] && source .env; set +a
: "${GPU_MAX_EUR_H:?GPU_MAX_EUR_H doit être défini (plafond horaire, ex. 2.00)}"
exec python3 infra/gpu.py up "$@"
