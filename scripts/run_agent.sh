#!/usr/bin/env bash
# Exécute UN jalon avec Codex CLI (OpenAI) en mode headless, puis s'arrête.
# L'agent MERGE lui-même sa PR une fois la CI verte (auto-merge délégué).
# Codex construit le PoC ; il n'est jamais une dépendance d'exécution du produit.
# Usage : run_agent.sh M2
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; [[ -f .env ]] && source .env; set +a

MILESTONE="${1:?usage: run_agent.sh M<n>}"
mkdir -p BRAIN
echo "=== $(date -Is) — démarrage agent sur $MILESTONE ===" | tee -a BRAIN/agent.log

read -r -d '' PROMPT <<EOF || true
Tu réalises le jalon ${MILESTONE} du projet ATLAS-0.

Avant toute action : lis AGENTS.md, MISSION.md, docs/13-poc-spec.md.
Respecte STRICTEMENT docs/11 et docs/14 (règles absolues, marqueurs d'observabilité,
anti-rationalisation, état BRAIN/).

Contrat (R-02) : tu PEUX inclure le contrat ET l'implémentation dans la MÊME PR pour
ce jalon (assouplissement autorisé), sauf si le jalon exige explicitement un contrat
séparé. Vise UNE seule PR par jalon quand c'est raisonnable.

Définition de terminé pour ${MILESTONE} :
  1. \`make verify-${MILESTONE,,}\` passe EN LOCAL, puis
  2. crée une branche ${MILESTONE,,}-<sujet>, commit, push, ouvre une Pull Request, puis
  3. ATTENDS que le job CI 'ci' soit VERT : interroge
     GET https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/commits/<sha>/check-runs
     ou /actions/runs, avec le header "Authorization: Bearer \${GITHUB_TOKEN}", en boucle
     (max 20 essais, 15s d'intervalle), puis
  4. SI ET SEULEMENT SI la CI est VERTE, MERGE toi-même la PR via :
     curl -X PUT -H "Authorization: Bearer \${GITHUB_TOKEN}" -H "Accept: application/vnd.github+json" \\
       https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/pulls/<N>/merge \\
       -d '{"merge_method":"squash"}'
     puis mets à jour BRAIN/ et ARRÊTE-toi. NE PASSE PAS au jalon suivant.

AUTORISATION DE MERGE : tu es autorisé à merger tes propres PR, à la CONDITION STRICTE
que le job 'ci' soit vert. Ne merge JAMAIS une PR à CI rouge ou en attente. Ne modifie
JAMAIS un fichier protégé (CODEOWNERS, scripts/verify-*, .github/workflows).
Si bloqué après 3 tentatives sur le même problème : écris dans BRAIN/BLOCKERS.md et
arrête-toi proprement. Ne prétends jamais qu'un test passe sans preuve CI.
EOF

SANDBOX="${CODEX_SANDBOX:-danger-full-access}"
set +e
codex exec "$PROMPT" \
  --dangerously-bypass-approvals-and-sandbox \
  --json \
  --output-last-message "BRAIN/${MILESTONE}.last.txt" \
  >> "BRAIN/${MILESTONE}.jsonl" 2>> BRAIN/agent.log
CODE=$?
set -e

echo "=== $(date -Is) — agent sur $MILESTONE terminé (exit $CODE) ===" | tee -a BRAIN/agent.log
exit $CODE
