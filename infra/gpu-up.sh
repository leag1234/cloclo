#!/usr/bin/env bash
# infra/gpu-up.sh — crée un nœud GPU compatible vLLM (CUDA >= 7.5), en choisissant
# AUTOMATIQUEMENT le premier type disponible dans une liste de préférences.
# Évite les blocages sur rupture de stock (shortage) d'un type donné.
# Monte le volume de poids persistant, lance vLLM avec prefix caching.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; [[ -f .env ]] && source .env; set +a
: "${SCW_DEFAULT_ZONE:?}" "${LOCAL_MODEL:?LOCAL_MODEL manquant dans .env}"

NAME="atlas-gpu"
VOLUME="atlas-weights"
log(){ printf '[gpu-up] %s\n' "$*" >&2; }

# Liste de préférence : GPU mono-carte compatibles vLLM (CUDA >= 7.5),
# du moins cher au plus cher. On prend le premier "available".
# (P100/RENDER-S exclus : CUDA 6.0, incompatible vLLM.)
PREFERRED=("L40S-1-48G" "H100-1-80G" "L40S-2-48G" "H100-SXM-2-80G")

# Si GPU_INSTANCE_TYPE est forcé dans .env et disponible, on le respecte en priorité.
if [[ -n "${GPU_INSTANCE_TYPE:-}" ]]; then
  PREFERRED=("$GPU_INSTANCE_TYPE" "${PREFERRED[@]}")
fi

log "recherche d'un GPU disponible parmi : ${PREFERRED[*]}"
CATALOG="$(scw instance server-type list zone="$SCW_DEFAULT_ZONE" -o json 2>/dev/null)"

CHOSEN=""
for t in "${PREFERRED[@]}"; do
  avail=$(echo "$CATALOG" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for s in d:
    if s.get('name')=='$t':
        print(s.get('availability','')); break
" 2>/dev/null)
  log "  $t -> ${avail:-inconnu}"
  if [[ "$avail" == "available" || "$avail" == "scarce" ]]; then
    CHOSEN="$t"; break
  fi
done

[[ -n "$CHOSEN" ]] || { log "AUCUN GPU compatible disponible actuellement (tous en shortage). Réessaie plus tard."; exit 1; }
log "GPU retenu : $CHOSEN"

# Image GPU Scaleway (drivers NVIDIA + docker préinstallés)
GPU_IMAGE="${GPU_IMAGE:-ubuntu_jammy_gpu_os_12}"

# Volume de poids persistant (créé une fois, réutilisé)
if ! echo "$CATALOG" >/dev/null; then :; fi
if ! scw instance volume list zone="$SCW_DEFAULT_ZONE" -o json 2>/dev/null | grep -q "\"$VOLUME\""; then
  log "création du volume de poids $VOLUME (300 Go)…"
  scw instance volume create name="$VOLUME" size=300GB volume-type=b_ssd zone="$SCW_DEFAULT_ZONE" >&2
fi

# Instance (idempotent)
if scw instance server list zone="$SCW_DEFAULT_ZONE" -o json 2>/dev/null | grep -q "\"$NAME\""; then
  log "instance $NAME déjà présente."
else
  log "création de l'instance $CHOSEN…"
  scw instance server create type="$CHOSEN" name="$NAME" image="$GPU_IMAGE" \
      zone="$SCW_DEFAULT_ZONE" root-volume=l_ssd:80GB ip=new --wait >&2
fi

IP=$(scw instance server list zone="$SCW_DEFAULT_ZONE" -o json 2>/dev/null \
     | python3 -c "import sys,json;[print(s['public_ip']['address']) for s in json.load(sys.stdin) if s.get('name')=='$NAME' and s.get('public_ip')]" 2>/dev/null | head -1)
[[ -n "$IP" ]] || { log "pas d'IP publique obtenue"; exit 1; }
log "instance prête, IP=$IP"

# Lancer vLLM (prefix caching = levier coût, docs/04)
log "démarrage de vLLM pour ${LOCAL_MODEL}…"
ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 root@"$IP" bash -s <<REMOTE >&2 || { log "échec du démarrage vLLM via SSH"; exit 1; }
set -e
docker run -d --gpus all --name vllm -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model ${LOCAL_MODEL} --served-model-name local \
  --enable-prefix-caching --max-model-len 8192
REMOTE

echo "$IP" > BRAIN/gpu_ip.txt
log "OK. vLLM en démarrage sur http://$IP:8000 (type $CHOSEN)."
