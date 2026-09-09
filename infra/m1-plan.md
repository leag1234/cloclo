# Plan M1 — cycle GPU minimal et gateway

Statut : prêt pour revue avant implémentation (docs/11 §9.2).
Source: MISSION.md au commit aebb3e1, contracts/m1.md, docs/13 POC-A1/A3/A4,
POC-I1/I2 ; docs/03 REQ-INF-012/013, docs/04 REQ-FIN-002,
docs/11 REQ-ENG-004/005/009/011.

## Contrat et périmètre
Un cycle réel sur la VM : création, readiness vLLM, inférence, bench JSON,
destruction, durée totale < 20 minutes. Ensuite PR et job GitHub `ci` vert.
CI sans GPU : contrôle statique protégé et tests de cycle de vie avec doubles
strictement limités aux tests. Pas de TTFT SSE ni de second cycle en M1.
Le contrat minimal est déjà dans l'historique local ; vérifier le merge distant
avant implémentation. Pas de migration, nouvelle UI, RAG ou réalisation M2.

## Incréments et fichiers
1. Tests `tests/test_m1.py` : configuration absente/invalide, isolation projet,
   erreurs fournisseur, idempotence, double instance ambiguë, nettoyage sur échec,
   préservation du volume de poids, suppression du disque système et de l'IP.
   Montrer leur échec sur les scripts actuels avant le correctif.
2. `infra/gpu-up.sh`, `infra/gpu-down.sh`, ressources cloud-init sous `infra/` :
   CLI Scaleway avec projet/zone explicites, sélection par ID et tags de propriété,
   verrou local contre les cycles concurrents et état atomique sans secret.
   Créer/réattacher un volume Block Storage persistant de poids ; ne jamais
   reformater un volume existant. Bootstrap par cloud-init, sans installation SSH.
   Épingler l'image GPU et le conteneur après vérification de compatibilité.
   Activer prefix caching, servir l'alias `local`, monter le cache des poids sur
   le volume persistant. Borner les attentes et propager les erreurs.
   Nettoyer toutes les ressources temporaires possédées, y compris les échecs
   partiels ; conserver uniquement le volume de poids convenu au contrat.
3. `services/model-gateway/` : configuration locale et fallback Scaleway,
   identifiants de modèles exclusivement dans ce service ou l'environnement.
   URL locale issue du provisionnement ; tests de cohérence des alias/URLs.
   Documenter l'usage, le coût, les erreurs et la reprise dans le README.
4. `infra/inventory.sh` : inventaire explicitement borné au projet dédié,
   utilisable avant/après le cycle et à la fermeture de session.
5. `scripts/test.sh` : inclure le contrôle statique M1 dans le chemin existant
   de CI, sans appeler le GPU et sans modifier les fichiers protégés.
   Adapter les cibles qualité si du Python est ajouté sous infra.
6. BRAIN : état avant provisionnement et push, bench réel, références PR/CI,
   inventaire final. Aucun secret ni trace brute ajouté à Git.

## Vérifications et livraison
- Tests sans réseau : entrées invalides, erreurs et délais, ressources étrangères
  intouchées, échec de nettoyage visible, poids conservés, cloud-init et routage.
- Syntaxe shell, lint, typage, tests, scan secrets ; couverture du diff ≥ 80 %.
- `make verify-m1` réel sur la VM après prérequis cloud ; inspecter aussi le JSON
  et l'inventaire final sans affaiblir les assertions du vérificateur protégé.
- Maximum trois tentatives par problème ; consigner puis arrêter au troisième.
- Push uniquement sur branche `m1-*`, PR < 400 lignes de diff ; si nécessaire,
  découper en PR cohérentes et attendre les merges humains avant dépendances.
- Attendre le job `ci` vert sur le commit livré, citer son URL ; mettre à jour
  JOURNAL/STATUS/TASK et vérifier la CI du dernier commit publié. Aucun merge agent.
- Aucun fichier .github/workflows/, scripts/verify-*.sh ou CODEOWNERS modifié.

## Prérequis et risques à résoudre avant lancement
- Confirmation des alertes indépendantes 50/80 % de 800 € et de l'extinction
  planifiée (docs/13 POC-I1/I2, docs/14 AUTO-2/3).
- GPU configuré : L40S-1-48G, fr-par-2, 1,469916 EUR/h HT au catalogue API
  consulté le 2026-09-09. Disponibilité annoncée : shortage.
- Chiffrer séparément volume de poids, disque système et IP avant création,
  inscrire le total et le coût persistant dans BRAIN/STATUS.md.
- Protéger le port d'inférence par règle réseau limitée à la VM de vérification.
- Vérifier les signatures réelles CLI, le montage Block Storage, les versions
  GPU/vLLM et la révision des poids ; aucune API ou compatibilité inventée.
- Les tests ne prouvent pas la disponibilité commerciale ou la vitesse du premier
  téléchargement : seul le cycle réel satisfait la preuve GPU.
