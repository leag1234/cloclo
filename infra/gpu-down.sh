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
  # Vérification post-destruction. On distingue explicitement 3 cas :
  #  - vérification OK et instance absente  -> succès
  #  - vérification OK et instance présente -> échec (GPU encore actif)
  #  - vérification IMPOSSIBLE               -> échec (on ne prétend JAMAIS un succès
  #                                            que l'on n'a pas pu constater)
  sleep 5
  if ! CHECK=$(scw instance server list zone="$SCW_DEFAULT_ZONE" project-id="$SCW_DEFAULT_PROJECT_ID" -o json 2>&1); then
    echo "[gpu-down] ERREUR: vérification post-destruction IMPOSSIBLE (API injoignable)." >&2
    echo "[gpu-down] L'instance $ID peut être encore ACTIVE et FACTURÉE — vérifier à la main !" >&2
    exit 1
  fi
  if printf '%s' "$CHECK" | grep -q "\"$ID\""; then
    echo "[gpu-down] ERREUR: $ID est toujours présent après terminate — GPU ENCORE FACTURÉ !" >&2
    exit 1
  fi
  echo "[gpu-down] instance supprimée et vérifiée (absente de l'inventaire), volume conservé."
else
  echo "[gpu-down] aucune instance $GPU_NAME dans ce projet — rien à faire."
fi
rm -f BRAIN/gpu_ip.txt
