#!/usr/bin/env bash
# infra/gpu-down.sh — détruit l'instance GPU du projet courant, et UNIQUEMENT elle.
# Le volume de poids est CONSERVÉ. Idempotent.
#
# Garanties (chacune est testée dans tests/test_gpu_down.sh) :
#  G1. Cible par (nom, projet, organisation) : jamais une homonyme d'un autre projet.
#  G2. L'inventaire JSON est VALIDÉ structurellement avant toute décision.
#  G3. Aucune erreur masquée : si lister/parser/terminer/vérifier échoue -> exit 1
#      avec un message explicite "GPU peut-être encore facturé".
#  G4. Le succès n'est annoncé que si l'instance est CONSTATÉE absente après terminate.
#  G5. Ambiguïté (plusieurs candidates) -> refus, on ne devine pas.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; [[ -f .env ]] && source .env; set +a
: "${SCW_DEFAULT_ZONE:?SCW_DEFAULT_ZONE requis}"
: "${SCW_DEFAULT_PROJECT_ID:?SCW_DEFAULT_PROJECT_ID requis}"
: "${SCW_DEFAULT_ORGANIZATION_ID:?SCW_DEFAULT_ORGANIZATION_ID requis}"
export GPU_NAME="${GPU_NAME:-atlas-gpu}" SCW_DEFAULT_PROJECT_ID SCW_DEFAULT_ORGANIZATION_ID
SCW="${SCW_BIN:-scw}"   # surchargeable pour les tests

die(){ echo "[gpu-down] ERREUR: $*" >&2; echo "[gpu-down] Un GPU peut être encore ACTIF et FACTURÉ — vérifier à la main dans la console." >&2; exit 1; }

# --- inventaire, filtré côté API par projet ---
INV=$("$SCW" instance server list zone="$SCW_DEFAULT_ZONE" project-id="$SCW_DEFAULT_PROJECT_ID" -o json 2>/dev/null) \
  || die "impossible de lister les instances (API/auth)"

# --- G1+G2+G5 : parse validé, propriété vérifiée, unicité exigée ---
ID=$(printf '%s' "$INV" | python3 -c '
import sys, json, os
name, proj, org = os.environ["GPU_NAME"], os.environ["SCW_DEFAULT_PROJECT_ID"], os.environ["SCW_DEFAULT_ORGANIZATION_ID"]
raw = sys.stdin.read()
try:
    data = json.loads(raw)
except Exception as e:
    print(f"BAD_JSON:{e}", file=sys.stderr); sys.exit(3)
if not isinstance(data, list):
    print("BAD_SHAPE:not a list", file=sys.stderr); sys.exit(3)
cands = []
for s in data:
    if not isinstance(s, dict) or "id" not in s or "name" not in s:
        print("BAD_SHAPE:item without id/name", file=sys.stderr); sys.exit(3)
    if s.get("name") == name and s.get("project") == proj and s.get("organization") == org:
        cands.append(s["id"])
if len(cands) > 1:
    print(f"AMBIGUOUS:{cands}", file=sys.stderr); sys.exit(4)
print(cands[0] if cands else "")
') || {
  rc=$?
  case $rc in
    3) die "inventaire JSON invalide ou de forme inattendue — aucune action prise" ;;
    4) die "plusieurs instances '$GPU_NAME' dans ce projet — ambiguïté, aucune action prise" ;;
    *) die "analyse de l'inventaire échouée (code $rc)" ;;
  esac
}

if [[ -z "$ID" ]]; then
  echo "[gpu-down] aucune instance '$GPU_NAME' (projet $SCW_DEFAULT_PROJECT_ID, org $SCW_DEFAULT_ORGANIZATION_ID) — rien à faire."
  rm -f BRAIN/gpu_ip.txt
  exit 0
fi

# --- G3 : terminate, erreur non masquée ---
echo "[gpu-down] suppression de $GPU_NAME ($ID)…"
"$SCW" instance server terminate "$ID" zone="$SCW_DEFAULT_ZONE" with-ip=true with-block=false >/dev/null 2>&1 \
  || die "terminate a échoué pour $ID"

# --- G4 : constater l'absence, sinon échec (jamais de faux succès) ---
sleep "${GPU_DOWN_SETTLE:-5}"
CHECK=$("$SCW" instance server list zone="$SCW_DEFAULT_ZONE" project-id="$SCW_DEFAULT_PROJECT_ID" -o json 2>/dev/null) \
  || die "vérification post-destruction IMPOSSIBLE (API injoignable) ; $ID peut être encore actif"
STILL=$(printf '%s' "$CHECK" | TARGET="$ID" python3 -c '
import sys, json, os
try: data = json.load(sys.stdin)
except Exception: print("BAD"); sys.exit(0)
print("YES" if any(isinstance(s,dict) and s.get("id")==os.environ["TARGET"] for s in data) else "NO")
')
case "$STILL" in
  NO)  echo "[gpu-down] instance $ID supprimée et CONSTATÉE absente ; volume de poids conservé." ;;
  YES) die "$ID est TOUJOURS présent après terminate" ;;
  *)   die "inventaire post-destruction illisible ; $ID peut être encore actif" ;;
esac
rm -f BRAIN/gpu_ip.txt
