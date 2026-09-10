# guardrails

Responsable : `OWNERS`.

Squelette M0 sans processus actif.
SLO, runbook et dashboard : non applicables avant activation du service
au jalon correspondant dans MISSION.md.

M6 active un filtre pur dans Query, avant I/O : contrôles invisibles dangereux
rejetés, langues et retours à la ligne conservés. Les erreurs 422 ne renvoient pas
le texte rejeté. Log structuré input_rejected sans contenu. Ce filtre minimal ne
constitue pas une défense complète contre l'injection sémantique de prompt.
