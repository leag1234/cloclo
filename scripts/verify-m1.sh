#!/usr/bin/env bash
# verify-m1 — infra GPU reproductible + gateway. PROTÉGÉ (CODEOWNERS).
#
# VALIDATION sur la VM (GPU + creds), PAS en CI GitHub (ni GPU ni secrets).
# En CI : contrôle statique. Sur la VM avec creds : test complet, 2 cycles,
# bench TTFT + débit. Un trap détruit le GPU en sortie quoi qu'il arrive.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
fail(){ echo "::error::verify-m1: $*" >&2; exit 1; }
pass(){ echo "  ✓ $*" >&2; }
log(){  echo "  → $*" >&2; }
echo "== verify-m1 ==" >&2

# --- MODE STATIQUE (CI, ou VM sans creds) : pas de GPU ---
if [[ -z "${SCW_ACCESS_KEY:-}" || -z "${SCW_SECRET_KEY:-}" ]]; then
  echo "  (creds Scaleway absents : contrôle statique — normal en CI)" >&2
  bash -n infra/gpu-up.sh   || fail "gpu-up.sh : erreur de syntaxe"
  bash -n infra/gpu-down.sh || fail "gpu-down.sh : erreur de syntaxe"
  [[ -x infra/gpu-up.sh && -x infra/gpu-down.sh ]] || fail "scripts gpu-*.sh non exécutables"
  grep -q "enable-prefix-caching" infra/gpu-up.sh || fail "prefix caching non activé (docs/04)"
  [[ -f contracts/m1-bench.schema.json ]] || fail "schéma de bench manquant"
  pass "contrôle statique OK"
  echo "== verify-m1 OK (mode statique) ==" >&2
  exit 0
fi

# --- MODE COMPLET (VM avec creds) ---
mkdir -p BRAIN/bench

# run_cycle : TOUTE la progression va sur stderr ; SEULE la durée (entier) sur stdout.
run_cycle(){
  local label="$1" start ip code ready t_req t_end dur out_tok tps bench stream_file
  log "[$label] création du nœud GPU…"
  start=$(date +%s)
  bash infra/gpu-up.sh >&2 || fail "[$label] gpu-up.sh a échoué"
  ip="$(cat BRAIN/gpu_ip.txt 2>/dev/null || true)"
  [[ -n "$ip" ]] || fail "[$label] pas d'IP produite"

  log "[$label] attente de vLLM sur $ip:8000 (max 12 min)…"
  ready=0
  for _ in $(seq 1 72); do
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 5 "http://$ip:8000/v1/models" 2>/dev/null || echo 000)
    [[ "$code" == "200" ]] && { ready=1; break; }
    sleep 10
  done
  [[ "$ready" == "1" ]] || fail "[$label] vLLM n'a pas répondu 200 en 12 min"

  log "[$label] bench TTFT/débit…"
  stream_file="/tmp/m1_stream_$$.txt"
  t_req=$(date +%s.%N)
  curl -sN -m 90 "http://$ip:8000/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"local","stream":true,"max_tokens":128,"messages":[{"role":"user","content":"Ecris un court paragraphe."}]}' \
    > "$stream_file" 2>/dev/null || true
  t_end=$(date +%s.%N)
  grep -q '^data:' "$stream_file" || fail "[$label] bench streaming vide"
  out_tok=$(grep -c '"content"' "$stream_file" 2>/dev/null || echo 0)
  dur=$(awk "BEGIN{printf \"%.3f\", $t_end - $t_req}")
  tps=$(awk "BEGIN{d=$dur; printf \"%.2f\", (d>0 ? ${out_tok:-0}/d : 0)}")
  rm -f "$stream_file"

  bench="BRAIN/bench/m1-${label}-$(date +%Y%m%dT%H%M%SZ).json"
  printf '{"cycle":"%s","ip":"%s","total_s":%s,"output_tokens":%s,"tokens_per_s":%s,"ts":"%s"}\n' \
    "$label" "$ip" "$dur" "${out_tok:-0}" "${tps:-0}" "$(date -Is)" > "$bench"
  pass "[$label] bench archivé : $bench (≈${tps} tok/s, ${out_tok} tokens)"

  log "[$label] destruction du nœud…"
  bash infra/gpu-down.sh >&2 || fail "[$label] gpu-down.sh a échoué"

  # SEULE ligne sur stdout : la durée en secondes (entier)
  echo $(( $(date +%s) - start ))
}

cleanup(){ echo "  [cleanup] destruction de sécurité…" >&2; bash infra/gpu-down.sh >&2 || true; }
trap cleanup EXIT

D1=$(run_cycle "cycle1")
[[ "$D1" =~ ^[0-9]+$ ]] || fail "cycle1 : durée non numérique ('$D1')"
[[ "$D1" -lt 1200 ]] || fail "cycle1 trop lent : ${D1}s (< 1200s attendu)"
pass "cycle1 complet en ${D1}s (< 20 min)"

D2=$(run_cycle "cycle2")
[[ "$D2" =~ ^[0-9]+$ ]] || fail "cycle2 : durée non numérique ('$D2')"
[[ "$D2" -lt 1200 ]] || fail "cycle2 trop lent : ${D2}s"
pass "cycle2 complet en ${D2}s — reproductibilité prouvée"

trap - EXIT
echo "== verify-m1 OK (2 cycles, < 20 min, bench archivés) ==" >&2
