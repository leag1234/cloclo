#!/usr/bin/env bash
# infra/gpu-up.sh — crée le nœud GPU Scaleway, monte le volume de poids persistant,
# lance vLLM (prefix caching activé). Cadre fourni ; l'agent complète et DURCIT en M1
# (idempotence, attente readiness, montage du volume, checksum des poids).
# Objectif verify-m1 : re-création complète depuis zéro < 20 min, puis gpu-down.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; [[ -f .env ]] && source .env; set +a

: "${SCW_DEFAULT_ZONE:?}" "${GPU_INSTANCE_TYPE:?}" "${LOCAL_MODEL:?LOCAL_MODEL manquant dans .env}"
NAME="atlas-gpu"
VOLUME="atlas-weights"   # volume Block Storage persistant réattaché entre extinctions

log(){ printf '[gpu-up] %s\n' "$*"; }

# ASSUMPTION: le quota ${GPU_INSTANCE_TYPE} est débloqué dans ${SCW_DEFAULT_ZONE}.
# Si la création échoue pour quota, l'agent écrit RISK: dans BRAIN/BLOCKERS.md.

# 1. volume de poids (créé une fois, réutilisé) — évite le retéléchargement (docs/03 REQ-INF-012)
if ! scw instance volume list zone="$SCW_DEFAULT_ZONE" -o json | jq -e --arg n "$VOLUME" \
       '.[]|select(.name==$n)' >/dev/null; then
  log "création du volume de poids $VOLUME (300 Go)…"
  scw instance volume create name="$VOLUME" size=300GB volume-type=b_ssd \
      zone="$SCW_DEFAULT_ZONE" >/dev/null
fi

# 2. instance GPU (idempotent)
if scw instance server list zone="$SCW_DEFAULT_ZONE" -o json | jq -e --arg n "$NAME" \
     '.[]|select(.name==$n)' >/dev/null; then
  log "instance $NAME déjà présente."
else
  log "création de l'instance $GPU_INSTANCE_TYPE…"
  scw instance server create type="$GPU_INSTANCE_TYPE" name="$NAME" \
      image=ubuntu_jammy_gpu_os_12 zone="$SCW_DEFAULT_ZONE" \
      root-volume=l_ssd:80GB additional-volumes.0="$VOLUME" \
      ip=new --wait >/dev/null
fi

IP=$(scw instance server list zone="$SCW_DEFAULT_ZONE" -o json \
     | jq -r --arg n "$NAME" '.[]|select(.name==$n)|.public_ip.address')
log "instance prête, IP=$IP"

# 3. lancement de vLLM en conteneur (prefix caching = levier coût n°1, docs/04)
#    TODO(agent M1) : durcir — readiness probe, --kv-cache-dtype fp8, montage volume,
#    téléchargement des poids une fois vers /weights, checksum (docs/03 REQ-INF-013).
log "démarrage de vLLM pour ${LOCAL_MODEL}…"
ssh -o StrictHostKeyChecking=accept-new root@"$IP" bash -s <<REMOTE
set -e
docker run -d --gpus all --name vllm -p 8000:8000 \
  -v /mnt/weights:/weights \
  vllm/vllm-openai:latest \
  --model ${LOCAL_MODEL} --served-model-name local \
  --enable-prefix-caching --kv-cache-dtype fp8 --max-model-len 32768
REMOTE

echo "$IP" > BRAIN/gpu_ip.txt
log "OK. Gateway doit pointer http://$IP:8000/v1 (via config, docs/02)."
