# MCP GitLab local — M14

Source: contracts/m14.md, REQ-MCP-001..004.
Installer l'adaptateur MIT figé :
`npm install --prefix /opt/atlas-mcp --ignore-scripts @zereight/mcp-gitlab@2.1.60`.
L'installation de test occupait41 Mo, paquet2,24 Mo hors dépendances ; Node 22.23.2,
SDK MCP Node 1.30.0 transitif. Adaptateur maintenu publiquement ; aucune dépendance
Python nouvelle. Alternative étudiée : SDK Python 2.2.0 (366 Ko hors dépendances),
non retenu pour éviter les transports inutilisés dans ce client stdio borné.

Copier `infra/mcp/gitlab.json` vers un fichier privé, remplacer l'URL GitLab et
REPLACE_PROJECT_ID, puis définir ATLAS_MCP_CONFIG avec son chemin. Fournir
ATLAS_GITLAB_TOKEN par environnement privé (jamais dans une commande, la config ou
le dépôt). Utiliser un jeton API limité au projet autorisé et aux droits nécessaires.
La liste des outils, leur classification et leurs arguments fixes sont administratifs.
Ne pas autoriser de champs permettant de remplacer endpoint, projet ou credentials.
Les serveurs MCP exécutables sont des programmes de confiance installés par l'admin.

Relancer `make serve`. Avec le tunnel SSH existant pour 3000 et 8020, demander une
lecture GitLab ou une création d'issue. Pour une écriture, ouvrir le lien local 8020,
vérifier les arguments affichés, puis cliquer «Confirmer et exécuter une fois».
Aucun effet sur GET. Autorisation valable10 minutes, à usage unique, liée à la config
et au jeton ;100 demandes maximum. Redémarrage du processus = invalidation des attentes.
UI mono-utilisateur, un processus ; pas d'exposition publique de cette confirmation.
Si le résultat indique une écriture incertaine, vérifier GitLab avant une nouvelle
requête ; ATLAS ne relance jamais une écriture automatiquement.

Sans ATLAS_MCP_CONFIG, les quatre outils existants restent inchangés.
Journal : BRAIN/mcp/actions.jsonl, permissions 0600, noms/état/durée uniquement.
Pas de stderr fournisseur, de contenu ou d'arguments dans ce journal.
Les retours MCP sont des données non fiables ; secret connu renvoyé = refus.
Délai MCP15 s, arguments16 KiB, réponse256 KiB ; version protocole 2025-11-25,
texte uniquement, pas de sampling, roots, elicitation, tâches ou transport HTTP.

`make verify-m14` rejoue en CI les échanges réels synthétiques versionnés.
Pour répéter le gate réel sur un GitLab de test : configuration sous le nom gitlab,
issue1 décrite exactement «Synthetic fixture: expected colour is blue.», puis
ATLAS_M14_MODE=live. Le gate crée une issue de test après confirmation HTTP et
remplace la cassette ; il faut un projet synthétique jetable, jamais entreprise.
Les quatre indicateurs ne sont écrits qu'après les assertions et tests adversariaux.
Coût MCP estimé 0 EUR par requête pour cette API sans facturation à l'appel ; le coût
LLM reste dans le budget existant. Aucun GPU nécessaire.
