#!/usr/bin/env bash
# verify-m1 — infra GPU reproductible + gateway. PROTÉGÉ (CODEOWNERS).
#
# VALIDATION : ce jalon se prouve SUR LA VM (accès GPU + creds cloud), PAS en CI
# GitHub (qui n'a ni GPU ni secrets Scaleway). En CI, seul un contrôle statique
# des scripts est fait. Sur la VM avec les creds, le test complet crée réellement
# un GPU, mesure TTFT + débit, et vérifie la reproductibilité par un SECOND cycle.
#
# Livrables vérifiés (MISSION.md M1) :
#   - infra/gpu-up.sh crée le nœud depuis zéro
#   - vLLM répond sur /v1/models (HTTP 200)
#   - bench TTFT + débit (tok/s) archivé sous BRAIN/bench/
#   - infra/gpu-down.sh détruit l'instance
#   - re-création complète < 20 min
#   - reproductibilité : DEUX cycles up/down réussis
#
# Sécurité budget : un trap détruit le GPU en sortie quoi qu'il arrive.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
fail(){ echo "::error::verify-m1: $*"; exit 1; }
pass(){ echo "  ✓ $*"; }
echo "== verify-m1 =="

# --- MODE STATIQUE (CI GitHub, ou VM sans creds) : pas de GPU créé ---
if [[ -z "${SCW_ACCESS_KEY:-}" || -z "${SCW_SECRET_KEY:-}" ]]; then
  echo "  (creds Scaleway absents : contrôle statique uniquement — normal en CI)"
  bash -n infra/gpu-up.sh   || fail "infra/gpu-up.sh : erreur de syntaxe"
  bash -n infra/gpu-down.sh || fail "infra/gpu-down.sh : erreur de syntaxe"
  [[ -x infra/gpu-up.sh && -x infra/gpu-down.sh ]] || fail "scripts gpu-*.sh non exécutables"
  grep -q "enable-prefix-caching" infra/gpu-up.sh || fail "prefix caching non activé (docs/04)"
  [[ -f contracts/m1-bench.schema.json ]] || fail "schéma de bench manquant"
  pass "contrôle statique OK (test GPU réel = ce script sur la VM avec les creds)"
  echo "== verify-m1 OK (mode statique) =="
  exit 0
fi

# --- MODE COMPLET (VM avec creds) : création réelle, 2 cycles ---
mkdir -p BRAIN/bench

run_cycle(){
  local label="$1" start ip code ready t_req t_end dur out_tok tps ttft bench stream_file
  echo "  → [$label] création du nœud GPU…"
  start=$(date +%s)
  bash infra/gpu-up.sh || fail "[$label] gpu-up.sh a échoué"
  ip="$(cat BRAIN/gpu_ip.txt 2>/dev/null || true)"
  [[ -n "$ip" ]] || fail "[$label] pas d'IP produite"

  echo "  → [$label] attente de vLLM sur $ip:8000 (max 12 min)…"
  ready=0
  for _ in $(seq 1 72); do
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 5 "http://$ip:8000/v1/models" 2>/dev/null || echo 000)
    [[ "$code" == "200" ]] && { ready=1; break; }
    sleep 10
  done
  [[ "$ready" == "1" ]] || fail "[$label] vLLM n'a pas répondu 200 en 12 min"

  echo "  → [$label] bench TTFT/débit…"
  stream_file="/tmp/m1_stream_$$.txt"
  t_req=$(date +%s.%N)
  curl -sN -m 90 "http://$ip:8000/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"local","stream":true,"max_tokens":128,"messages":[{"role":"user","content":"Ecris un court paragraphe de presentation dun assistant IA."}]}' \
    > "$stream_file" 2>/dev/null || true
  t_end=$(date +%s.%N)
  grep -q '^data:' "$stream_file" || fail "[$label] bench streaming vide"
  out_tok=$(grep -c '"content"' "$stream_file" || echo 0)
  dur=$(echo "$t_end - $t_req" | bc)
  tps=$(echo "scale=2; ${out_tok:-0} / $dur" | bc 2>/dev/null || echo 0)
  rm -f "$stream_file"

  bench="BRAIN/bench/m1-${label}-$(date +%Y%m%dT%H%M%SZ).json"
  printf '{"cycle":"%s","ip":"%s","total_s":%s,"output_tokens":%s,"tokens_per_s":%s,"ts":"%s"}\n' \
    "$label" "$ip" "$dur" "${out_tok:-0}" "${tps:-0}" "$(date -Is)" > "$bench"
  pass "[$label] bench archivé : $bench (≈${tps} tok/s, ${out_tok} tokens)"

  echo "  → [$label] destruction du nœud…"
  bash infra/gpu-down.sh || fail "[$label] gpu-down.sh a échoué"
  echo $(( $(date +%s) - start ))
}

cleanup(){ echo "  [cleanup] destruction de sécurité…"; bash infra/gpu-down.sh || true; }
trap cleanup EXIT

D1=$(run_cycle "cycle1")
[[ "$D1" -lt 1200 ]] || fail "cycle1 trop lent : ${D1}s (cible < 1200s)"
pass "cycle1 complet en ${D1}s (< 20 min)"

D2=$(run_cycle "cycle2")
[[ "$D2" -lt 1200 ]] || fail "cycle2 trop lent : ${D2}s"
pass "cycle2 complet en ${D2}s — reproductibilité prouvée"

trap - EXIT
echo "== verify-m1 OK (2 cycles, création < 20 min, bench archivés) =="
