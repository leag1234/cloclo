#!/usr/bin/env bash
# infra/gpu-down.sh — détruit l'instance GPU du PROJET COURANT uniquement.
# Le volume de poids est CONSERVÉ. Idempotent. Ne touche jamais une instance
# d'un autre projet, même si elle porte le même nom.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; [[ -f .env ]] && source .env; set +a
: "${SCW_DEFAULT_ZONE:?}" "${SCW_DEFAULT_PROJECT_ID:?SCW_DEFAULT_PROJECT_ID requis pour cibler le bon projet}"
NAME="${GPU_NAME:-atlas-gpu}"

# On filtre explicitement par project-id côté API ET on revérifie le projet du résultat.
ID=$(scw instance server list zone="$SCW_DEFAULT_ZONE" project-id="$SCW_DEFAULT_PROJECT_ID" -o json \
     | python3 -c "
import sys, json, os
name = os.environ['NAME']; proj = os.environ['SCW_DEFAULT_PROJECT_ID']
for s in json.load(sys.stdin):
    if s.get('name') == name and s.get('project') == proj:
        print(s['id']); break
" 2>/dev/null || true)

if [[ -n "${ID:-}" ]]; then
  echo "[gpu-down] suppression de $NAME ($ID) dans le projet $SCW_DEFAULT_PROJECT_ID…"
  scw instance server terminate "$ID" zone="$SCW_DEFAULT_ZONE" with-ip=true with-block=false >/dev/null
  echo "[gpu-down] instance supprimée, volume de poids conservé."
else
  echo "[gpu-down] aucune instance $NAME dans ce projet — rien à faire."
fi
rm -f BRAIN/gpu_ip.txt
