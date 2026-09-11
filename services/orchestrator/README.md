# Orchestrator M3

Responsable : OWNERS. Contrat : [M3](../../contracts/m3.md).
REQ-HAR-001/002/006, REQ-TOOL-001/002/004/012/013/014/015, REQ-FIN-002.

Le modèle choisit les outils, le harness valide les arguments et réserve coût/tokens
avant chaque I/O. Les plafonds déclenchent un résultat `stopped` avec une raison
explicite ; les erreurs d'outil sont retournées au modèle pour récupération bornée.
Les résultats web/RAG sont non fiables ; les instructions restent dans prompts/.

## Exploitation locale

Depuis la racine, avec l'environnement Python installé :
`uvicorn services.orchestrator.app:app --host 127.0.0.1 --port 8020`.
Le gateway CPU/serverless M2 doit tourner à `ATLAS_GATEWAY_URL` (défaut port 8010),
et `ATLAS_RETRIEVAL_DSN` doit désigner la base M2 ingérée. Le gateway reçoit ses
credentials via environnement ; `SERPAPI_KEY` reste dans l'environnement harness.
`ATLAS_WEB_CACHE` désigne SQLite (défaut BRAIN/web-cache.sqlite).
Ne pas exposer directement ce serveur sans authentification ; branchement UI M4.

POST `/query` : `{"question":"Combien font 7*9 ?","lang":"fr"}`.
GET `/continuation/{handle}?offset=0` lit les extraits suivants jusqu'à expiration.
Arrêt du processus par SIGTERM ; aucun GPU nécessaire.

SLO M3 : arrêt de requête <=120s, <=10 outils, <=0.05 EUR, <=16384 tokens.
Les réservations demeurent comptées si l'appel échoue ou expire ; aucune promesse
que l'annulation HTTP annule la facturation fournisseur. Cache SerpApi 1h, pages 24h,
quota réservé 900/mois ; conserver SQLite lors des redémarrages pour garder le quota.

Diagnostic : examiner `state`, `reason`, `tokens`, `cost`, `tool_calls`, `trace`.
Les événements JSON `tool_finished` et `request_stopped` ne journalisent pas les
credentials ou le contenu des requêtes. Vue opérateur M3 : ces compteurs par réponse
et `BRAIN/eval/{tools,web}.json` par langue ; dashboard agrégé relève de M5.
Un refus robots/SSRF ne se contourne pas. Après trois erreurs identiques, consigner
BRAIN/BLOCKERS.md et arrêter ; ne pas effacer le quota pour débloquer une recherche.

## Vérification

`make test-web-security test-budgets` : HTTP local, DNS, robots, taille et budgets.
`make verify-m3` : E4/E6 réels, fautes E4 injectées dans le driver sous tests/.
`ATLAS_M3_EVAL_MODE=replay make verify-m3` : replay strict des mêmes appels ;
un prompt modifié ou des appels différents invalident les cassettes.
Aucun mock n'est importé par le runtime. Les cassettes sont exclusivement sous tests/.
E6 mesure ici l'exécutabilité avec URL/date ; pas de GO qualité sans revue des clés
et calibration humaine du juge. La fidélité de chaque phrase relève du gate E5.

M7 : chat_pipeline utilise les budgets du harness, retrieval HTTP et les citations
résolues. interactions écrit les mesures reçues et codes d'arrêt en JSONL privé ;
contrat complet et limites documentées dans contracts/m7.md.

M12 : `packages/images.py` définit les messages image validés du contrat `contracts/m12.md`.
PNG/JPEG sont décodés par Pillow après contrôle des dimensions ; URL distantes,
formats non pris en charge et dépassements cumulés sont refusés. Cette première
brique est commune aux futures frontières adaptateur/gateway vision.
Le chat accepte désormais des parties `text` et `image_url` en data URI PNG/JPEG.
Toute image de l'historique sélectionne `/vision/complete` ; les échanges texte
conservent le harness. Le journal contient métadonnées, tokens/coût et route vision,
sans base64, y compris si le fournisseur renvoie les octets en écho. Les erreurs
budget et délai restent distinctes et conservent une réservation de 0,05 EUR.

La vision relaie sa réponse complète validée dans SSE ; elle ne prétend pas
produire des tokens progressifs amont. Le texte/projet conserve le transport M11.

M15 : entrée développeurs `PYTHONPATH=.:services/model-gateway uvicorn services.orchestrator.devapi:app --host 127.0.0.1 --port 8030 --no-access-log` ; clés via `python -m services.orchestrator.dev_auth create <dev> --key-file <fichier-privé>`, révocation via `revoke <dev>`. ATLAS_DEVAPI_DB conserve les quotas quotidiens et réservations inconnues ; contrat contracts/m15.md. POST /v1/chat/completions expose désormais texte et fonctions en JSON ou SSE, sans accès aux outils/données du chat privé.

M15 protocole Chat : dev_chat normalise les messages texte et assemble les deltas sans exécuter les fonctions. Les identifiants doivent rester stables, les arguments complets être des objets JSON finis et les noms provenir des outils déclarés. Le stop fournisseur avec appel complet devient tool_calls ; length reste une troncature.

Sélection M10 : les contributions de pertinence sont additionnées avec math.fsum pour conserver les égalités indépendamment du hash seed Python. Le départage existant par position reste déterministe ; la cassette fournisseur exacte est inchangée.

M15 : dev_input traduit les historiques Responses/Messages vers les mêmes messages validés, sans stockage de conversations. Métadonnées et cache sont des indications sans effet d'identité ni garantie de cache ; l'effort Messages sans thinking ne l'active pas. Les images, outils hébergés, stockage Responses et thinking Messages sont refusés explicitement.

M15 : POST /v1/responses fournit les événements nommés texte/fonctions, les identifiants d'items et la terminaison completed/incomplete ; store=false. Le même quota est réservé avant le flux et réconcilié sur l'usage fournisseur.

M15 : POST /v1/messages traduit texte/tool_use/tool_result et les événements SSE message/content_block. Une sortie tronquée reste max_tokens ; les coûts viennent du même registre par clé. Compatibilité expérimentale pour les clients configurés sans thinking ni outils hébergés.
