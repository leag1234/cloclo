#!/usr/bin/env bash
# Exécute UN jalon avec Codex CLI (OpenAI) en mode headless, puis s'arrête.
# L'agent ne passe au jalon suivant que si `make verify-mN` passe SUR LA CI.
# Codex sert UNIQUEMENT à construire le PoC ; il n'est jamais une dépendance
# d'exécution du produit (l'inférence reste sur Scaleway/open-weight).
# Usage : run_agent.sh M0
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; [[ -f .env ]] && source .env; set +a

MILESTONE="${1:?usage: run_agent.sh M<n>}"
mkdir -p BRAIN
echo "=== $(date -Is) — démarrage agent sur $MILESTONE ===" | tee -a BRAIN/agent.log

# Prompt de mission : court, il renvoie aux artefacts versionnés (docs/14 §3.1).
read -r -d '' PROMPT <<EOF || true
Tu réalises le jalon ${MILESTONE} du projet ATLAS-0.

Avant toute action : lis AGENTS.md, MISSION.md, et docs/13-poc-spec.md.
Respecte STRICTEMENT docs/11 et docs/14 (règles absolues, marqueurs d'observabilité,
anti-rationalisation, état BRAIN/).

Définition de terminé pour ${MILESTONE} :
  1. \`make verify-${MILESTONE,,}\` passe EN LOCAL, puis
  2. tu pushes une branche + ouvres une PR, et le job CI 'ci' est VERT sur GitHub, puis
  3. tu mets à jour BRAIN/JOURNAL.md, BRAIN/STATUS.md, BRAIN/TASK.md.
Tu NE modifies PAS .github/workflows ni scripts/verify-*.sh (protégés).
Si tu es bloqué après 3 tentatives sur le même problème : écris dans BRAIN/BLOCKERS.md
et arrête-toi proprement. Ne prétends jamais qu'un test passe sans preuve CI.

Quand ${MILESTONE} est terminé et vert en CI, arrête-toi : n'enchaîne pas sur le suivant.
EOF

# Codex headless (`codex exec`) : prompt -> exécution -> message final sur stdout.
#  --full-auto : écritures dans le workspace autorisées, PAS d'accès réseau arbitraire
#                (sandbox workspace-write). C'est le niveau fail-loud : l'agent agit
#                dans le repo mais n'ouvre pas le réseau sans qu'on l'ait décidé.
#  Les jalons M1+ créent des ressources cloud via la CLI scw (réseau sortant) : pour
#  ces jalons, exporter CODEX_SANDBOX=danger-full-access UNIQUEMENT sur cette VM isolée
#  (voir MISSION.md). Par défaut on reste en workspace-write.
#  --json : événements structurés pour l'audit. --output-last-message : réponse finale nette.
#  Codex exige un dépôt git (garde-fou natif aligné avec nos règles).
SANDBOX="${CODEX_SANDBOX:-workspace-write}"
set +e
codex exec "$PROMPT" \
  --sandbox "$SANDBOX" \
  --json \
  --output-last-message "BRAIN/${MILESTONE}.last.txt" \
  >> "BRAIN/${MILESTONE}.jsonl" 2>> BRAIN/agent.log
CODE=$?
set -e

echo "=== $(date -Is) — agent sur $MILESTONE terminé (exit $CODE) ===" | tee -a BRAIN/agent.log
echo "Voir BRAIN/STATUS.md et l'onglet Actions du dépôt pour l'état CI." | tee -a BRAIN/agent.log
exit $CODE
