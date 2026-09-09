# edge-bff

Responsable : `OWNERS`.

M0 : liveness locale uniquement, contrat `contracts/edge-bff.openapi.json`.
Runbook : `python3 services/edge-bff/server.py`, puis
`bash services/edge-bff/healthcheck.sh` ; arrêt par Ctrl-C.
SLO M0 : `/health` retourne 200 tant que le processus fonctionne.
Dashboard M0 : logs JSON stdout (`service`, `event`) ; métriques M5.
