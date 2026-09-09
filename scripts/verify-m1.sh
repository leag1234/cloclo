#!/usr/bin/env bash
# verify-m1 — infra GPU reproductible + gateway. PROTÉGÉ (CODEOWNERS).
# Vérifie les livrables réels de M1 (MISSION.md) :
#   - infra/gpu-up.sh crée le nœud DEPUIS ZÉRO
#   - le gateway répond sur /v1/models (HTTP 200)
#   - un bench TTFT/tok-s est produit et archivé sous BRAIN/bench/
#   - infra/gpu-down.sh détruit l'instance
#   - re-création complète chronométrée < 20 min
#
# Ce script est exécuté par l'agent en LOCAL (make verify-m1) puis en CI.
# ATTENTION : il crée réellement un GPU (coût ~1,50 €/h). gpu-down est appelé
# en fin de test, y compris en cas d'échec (trap), pour ne jamais laisser
# tourner de GPU à vide.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
fail(){ echo "::error::verify-m1: $*"; exit 1; }
pass(){ echo "  ✓ $*"; }
echo "== verify-m1 =="

# Garde-fou budget : ce test ne doit tourner que là où on l'assume (VM, pas CI
# gratuite sans secrets cloud). Si les creds Scaleway sont absents, on ne tente
# pas de créer un GPU — on vérifie seulement que les scripts sont bien formés.
if [[ -z "${SCW_ACCESS_KEY:-}" || -z "${SCW_SECRET_KEY:-}" ]]; then
  echo "  (creds Scaleway absents : vérification statique des scripts uniquement)"
  bash -n infra/gpu-up.sh   || fail "infra/gpu-up.sh : erreur de syntaxe"
  bash -n infra/gpu-down.sh || fail "infra/gpu-down.sh : erreur de syntaxe"
  [[ -x infra/gpu-up.sh && -x infra/gpu-down.sh ]] || fail "scripts gpu-*.sh non exécutables"
  grep -q "enable-prefix-caching" infra/gpu-up.sh || fail "prefix caching non activé dans gpu-up.sh (docs/04)"
  pass "scripts infra bien formés (test complet nécessite les creds Scaleway sur la VM)"
  echo "== verify-m1 OK (mode statique) =="
  exit 0
fi

# --- Test réel avec création de GPU ---
mkdir -p BRAIN/bench
# nettoyage garanti : quoi qu'il arrive, on détruit le GPU en sortant
cleanup(){ echo "  [cleanup] destruction du GPU…"; bash infra/gpu-down.sh || true; }
trap cleanup EXIT

# 1. création depuis zéro, chronométrée
echo "  → création du nœud GPU (gpu-up.sh)…"
START=$(date +%s)
bash infra/gpu-up.sh || fail "infra/gpu-up.sh a échoué"
IP="$(cat BRAIN/gpu_ip.txt 2>/dev/null || true)"
[[ -n "$IP" ]] || fail "gpu-up.sh n'a pas produit d'IP (BRAIN/gpu_ip.txt)"
pass "nœud GPU créé, IP=$IP"

# 2. attendre que vLLM réponde (readiness), max 12 min
echo "  → attente de la disponibilité de vLLM sur $IP:8000…"
READY=0
for i in $(seq 1 72); do   # 72 × 10s = 12 min
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 5 "http://$IP:8000/v1/models" 2>/dev/null || echo 000)
  if [[ "$code" == "200" ]]; then READY=1; break; fi
  sleep 10
done
[[ "$READY" == "1" ]] || fail "vLLM n'a pas répondu 200 sur /v1/models en 12 min"
pass "vLLM répond 200 sur /v1/models"

# 3. bench minimal TTFT / tok-s, archivé
echo "  → bench d'inférence…"
BENCH="BRAIN/bench/m1-$(date +%Y%m%dT%H%M%SZ).json"
T0=$(date +%s.%N)
RESP=$(curl -s -m 60 "http://$IP:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"local","messages":[{"role":"user","content":"Compte de 1 a 20."}],"max_tokens":64}' \
  2>/dev/null || true)
T1=$(date +%s.%N)
echo "$RESP" | grep -q '"choices"' || fail "le bench n'a pas retourné de complétion valide"
LAT=$(echo "$T1 - $T0" | bc)
OUT_TOKENS=$(echo "$RESP" | grep -o '"completion_tokens":[0-9]*' | grep -o '[0-9]*' || echo 0)
printf '{"latency_s": %s, "output_tokens": %s, "ip": "%s", "ts": "%s"}\n' \
  "$LAT" "${OUT_TOKENS:-0}" "$IP" "$(date -Is)" > "$BENCH"
pass "bench archivé : $BENCH (latence ${LAT}s, ${OUT_TOKENS:-0} tokens)"

# 4. destruction (le trap la refait, mais on vérifie qu'elle marche explicitement)
echo "  → destruction du nœud (gpu-down.sh)…"
bash infra/gpu-down.sh || fail "infra/gpu-down.sh a échoué"
trap - EXIT   # cleanup déjà fait
pass "nœud GPU détruit"

# 5. temps total de création < 20 min (création + readiness)
ELAPSED=$(( $(date +%s) - START ))
echo "  → temps total création→prêt : ${ELAPSED}s"
[[ "$ELAPSED" -lt 1200 ]] || fail "re-création trop lente : ${ELAPSED}s (cible < 1200s)"
pass "re-création complète < 20 min (${ELAPSED}s)"

echo "== verify-m1 OK =="
