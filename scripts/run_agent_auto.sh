#!/usr/bin/env bash
# run_agent_auto.sh — mode AUTONOME NUIT : enchaîne les jalons donnés, sans intervention.
# L'agent tranche lui-même les contradictions MINEURES (seuils/nombres de cas/assouplissements
# PoC déjà documentés) et CONTINUE ; il ne s'arrête QUE sur les contradictions de SÉCURITÉ
# (isolation tenant, secrets, budgets, actions destructrices) ou un échec technique réel.
# Usage : run_agent_auto.sh M5 M6
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; [[ -f .env ]] && source .env; set +a

mkdir -p BRAIN
for MILESTONE in "$@"; do
  echo "=== $(date -Is) — AUTO: démarrage $MILESTONE ===" | tee -a BRAIN/agent.log

  read -r -d '' PROMPT <<EOF || true
Tu réalises le jalon ${MILESTONE} du projet ATLAS-0, en MODE AUTONOME.

Avant toute action : lis AGENTS.md, MISSION.md, docs/13-poc-spec.md. Respecte docs/11 et docs/14.

RÈGLE D'AUTONOMIE (nuit) : pour toute contradiction MINEURE entre MISSION.md et
docs/13 portant sur un SEUIL, un NOMBRE DE CAS, une RÉPARTITION PAR LANGUE, ou un
ASSOUPLISSEMENT déjà marqué "PoC" dans l'un des deux documents, tu NE t'arrêtes PAS :
tu appliques la version la MOINS STRICTE (celle qui correspond à l'état réel des
jeux dorés livrés), tu documentes ce choix dans le rapport et BRAIN/JOURNAL.md avec
le marqueur "CONTRADICTION résolue en autonomie:", et tu CONTINUES.

Tu t'arrêtes et écris dans BRAIN/BLOCKERS.md UNIQUEMENT si :
- contradiction ou risque de SÉCURITÉ (isolation tenant, fuite de secret, budget dépassé,
  action destructrice, appel payant hors budget) ;
- échec TECHNIQUE réel après 3 tentatives (dépendance cassée, erreur fournisseur persistante) ;
- fichier protégé qui devrait être modifié (CODEOWNERS/verify-*/workflows).

Définition de terminé pour ${MILESTONE} :
  1. make verify-${MILESTONE,,} passe en LOCAL, puis
  2. branche ${MILESTONE,,}-<sujet>, commit, push, PR, puis
  3. attends la CI 'ci' VERTE (poll API GitHub, max 60 essais × 15s = 15 min), puis
  4. si CI verte, MERGE toi-même via l'API GitHub (squash), puis maj BRAIN/.

AUTORISATION MERGE : autorisé si et seulement si le job 'ci' est vert. Ne modifie
jamais de fichier protégé. Appels payants (Scaleway/SerpApi) autorisés dans la limite
du budget par requête ; le GPU n'est PAS requis pour M5/M6.

Quand ${MILESTONE} est terminé et mergé, passe AUTOMATIQUEMENT au jalon suivant s'il y
en a un dans la liste. Écris "JALON ${MILESTONE} TERMINÉ" dans BRAIN/JOURNAL.md.
EOF

  set +e
  codex exec "$PROMPT" \
    --dangerously-bypass-approvals-and-sandbox \
    --json \
    --output-last-message "BRAIN/${MILESTONE}.last.txt" \
    >> "BRAIN/${MILESTONE}.jsonl" 2>> BRAIN/agent.log
  CODE=$?
  set -e

  echo "=== $(date -Is) — AUTO: $MILESTONE fini (exit $CODE) ===" | tee -a BRAIN/agent.log

  # Si le jalon a écrit un blocage de sécurité, on arrête toute la chaîne
  if [[ -f "BRAIN/${MILESTONE}.done" ]]; then
    echo "AUTO: $MILESTONE marqué done, on continue." | tee -a BRAIN/agent.log
  fi
  # Détecter un blocage explicite : si BLOCKERS.md a été touché récemment ET pas de merge,
  # on s'arrête pour ne pas enchaîner un jalon sur une base cassée.
  if grep -q "ARRÊT SÉCURITÉ\|SECURITY STOP" BRAIN/BLOCKERS.md 2>/dev/null; then
    echo "AUTO: arrêt sécurité détecté, chaîne interrompue." | tee -a BRAIN/agent.log
    break
  fi
done
echo "=== $(date -Is) — AUTO: chaîne terminée ===" | tee -a BRAIN/agent.log
