#!/usr/bin/env bash
# infra/gpu-down.sh — détruit l'instance GPU du PROJET COURANT uniquement.
# Le volume de poids est CONSERVÉ. Idempotent. Ne masque AUCUNE erreur : si la
# recherche échoue, on s'arrête en erreur plutôt que de laisser un GPU facturé.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; [[ -f .env ]] && source .env; set +a
: "${SCW_DEFAULT_ZONE:?}" "${SCW_DEFAULT_PROJECT_ID:?}"
export GPU_NAME="${GPU_NAME:-atlas-gpu}"
export SCW_DEFAULT_PROJECT_ID

LIST=$(scw instance server list zone="$SCW_DEFAULT_ZONE" project-id="$SCW_DEFAULT_PROJECT_ID" -o json) \
  || { echo "[gpu-down] ERREUR: impossible de lister les instances — un GPU peut rester facturé !" >&2; exit 1; }

ID=$(printf '%s' "$LIST" | python3 -c '
import sys, json, os
name = os.environ["GPU_NAME"]; proj = os.environ["SCW_DEFAULT_PROJECT_ID"]
try:
    data = json.load(sys.stdin)
except Exception as e:
    print(f"PARSE_ERROR:{e}", file=sys.stderr); sys.exit(2)
for s in data:
    if s.get("name") == name and s.get("project") == proj:
        print(s["id"]); break
') || { echo "[gpu-down] ERREUR: analyse de la liste impossible — vérifier manuellement !" >&2; exit 1; }

if [[ -n "${ID:-}" ]]; then
  echo "[gpu-down] suppression de $GPU_NAME ($ID) dans le projet $SCW_DEFAULT_PROJECT_ID…"
  scw instance server terminate "$ID" zone="$SCW_DEFAULT_ZONE" with-ip=true with-block=false >/dev/null \
    || { echo "[gpu-down] ERREUR: terminate a échoué pour $ID — GPU PEUT-ÊTRE ENCORE ACTIF !" >&2; exit 1; }
  # vérification post-destruction : l'instance ne doit plus apparaître
  sleep 5
  if scw instance server list zone="$SCW_DEFAULT_ZONE" project-id="$SCW_DEFAULT_PROJECT_ID" -o json \
     | grep -q "\"id\":\"$ID\""; then
    echo "[gpu-down] ERREUR: $ID est toujours présent après terminate !" >&2; exit 1
  fi
  echo "[gpu-down] instance supprimée et vérifiée, volume de poids conservé."
else
  echo "[gpu-down] aucune instance $GPU_NAME dans ce projet — rien à faire."
fi
rm -f BRAIN/gpu_ip.txt
