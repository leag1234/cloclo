#!/usr/bin/env bash
# infra/gpu-down.sh — détruit l'instance GPU et son IP publique. Le VOLUME de poids
# est CONSERVÉ (réattaché au prochain gpu-up, évite le retéléchargement).
# Idempotent : ne fait rien s'il n'y a rien.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; [[ -f .env ]] && source .env; set +a
: "${SCW_DEFAULT_ZONE:?}"
NAME="atlas-gpu"
ID=$(scw instance server list zone="$SCW_DEFAULT_ZONE" -o json \
     | jq -r --arg n "$NAME" '.[]|select(.name==$n)|.id' || true)
if [[ -n "${ID:-}" && "$ID" != "null" ]]; then
  echo "[gpu-down] arrêt+suppression de $NAME ($ID) et de son IP…"
  scw instance server terminate "$ID" zone="$SCW_DEFAULT_ZONE" with-ip=true with-block=false >/dev/null
  echo "[gpu-down] instance supprimée, volume de poids conservé."
else
  echo "[gpu-down] aucune instance $NAME — rien à faire."
fi
rm -f BRAIN/gpu_ip.txt
