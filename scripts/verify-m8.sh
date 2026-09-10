#!/usr/bin/env bash
# verify-m8 — GPU local + cascade réelle. PROTÉGÉ (CODEOWNERS).
# Prouve que le modèle local est servi sur GPU et que le routage local<->escalade
# fonctionne en conditions réelles. Crée un GPU (coût réel) via infra/gpu.py.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
fail(){ echo "::error::verify-m8: $*" >&2; exit 1; }
pass(){ echo "  ✓ $*" >&2; }
echo "== verify-m8 ==" >&2

# CI / sans creds : contrôle statique
if [[ -z "${SCW_ACCESS_KEY:-}" ]]; then
  bash -n infra/gpu.py 2>/dev/null || python3 -c "import ast;ast.parse(open('infra/gpu.py').read())" || fail "gpu.py invalide"
  grep -rqiE "route|routing|cascade" services/model-gateway/ 2>/dev/null || fail "logique de cascade absente"
  pass "contrôle statique OK (test réel = sur la VM avec GPU)"
  echo "== verify-m8 OK (statique) ==" >&2; exit 0
fi

cleanup(){ echo "  [cleanup] gpu-down…" >&2; python3 infra/gpu.py down >&2 2>&1 || true; }
trap cleanup EXIT

echo "  → création GPU + vLLM (LOCAL_MODEL)…" >&2
python3 infra/gpu.py up >&2 || fail "gpu.py up a échoué"
IP="$(cat BRAIN/gpu_ip.txt 2>/dev/null || true)"; [[ -n "$IP" ]] || fail "pas d'IP GPU"
pass "GPU up, vLLM sur $IP"

# le modèle local répond
code=$(curl -s -o /dev/null -w '%{http_code}' -m 10 "http://$IP:8000/v1/models" 2>/dev/null || echo 000)
[[ "$code" == "200" ]] || fail "vLLM local ne répond pas (/v1/models = $code)"
pass "modèle local sert /v1/models"

# routage : une requête simple doit être servie par le local (rapport de routage)
if ! make test-cascade >&2 2>/dev/null; then
  fail "make test-cascade échoue (routage local<->escalade)"
fi
R="BRAIN/eval/cascade.json"; [[ -f "$R" ]] || fail "rapport cascade absent"
SIMPLE_LOCAL=$(python3 -c "import json;print(json.load(open('$R')).get('simple_routed_local','false'))" 2>/dev/null||echo false)
FALLBACK_OK=$(python3 -c "import json;print(json.load(open('$R')).get('fallback_ok','false'))" 2>/dev/null||echo false)
[[ "$SIMPLE_LOCAL" =~ ^[Tt]rue$ ]] || fail "une requête simple n'est pas routée vers le local"
[[ "$FALLBACK_OK" =~ ^[Tt]rue$ ]] || fail "le fallback (local coupé -> escalade) ne fonctionne pas"
pass "cascade OK (simple→local, fallback→escalade)"

python3 infra/gpu.py down >&2 || fail "gpu.py down a échoué"
trap - EXIT
pass "GPU détruit proprement"
echo "== verify-m8 OK ==" >&2
