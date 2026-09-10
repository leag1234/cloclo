# MISSION — ATLAS-0

Construire le PoC défini dans `docs/13-poc-spec.md`, jalon par jalon, chaque jalon
prouvé par `make verify-mN` **vert sur la CI GitHub** (pas seulement en local).

Règle d'or : un jalon n'existe que lorsque sa CI est verte. Ta parole ne vaut rien ;
le job `ci` vaut tout. Tu ne modifies jamais `.github/workflows/` ni `scripts/verify-*`
(protégés par CODEOWNERS).

L'ordre est **impératif**. M0 puis M1 d'abord : sans CI et sans infra reproductible,
tout le reste est invérifiable.

---

## M0 — Cadre vérifiable
**But** : la boucle de vérification tourne de bout en bout sur un projet vide.
**Livrables** : structure des services (squelettes), `make` cible, CI qui exécute
lint+typecheck+tests+scan-secrets, `eval-harness` capable de tourner à vide.
**verify-m0** vérifie : `make lint test` vert ; `make eval-smoke` s'exécute (0 cas ok) ;
un healthcheck `edge-bff` répond 200 ; le scan de secrets passe ; le grep anti-nom-de-modèle
(docs/02 AC-ARC-4) ne trouve rien hors `services/model-gateway`.

## M1 — Infra GPU reproductible + gateway

**But** : prouver qu'un nœud GPU se crée par script, sert un modèle via
vLLM, puis se détruit. Livrables : `infra/gpu-up.sh`, `infra/gpu-down.sh`,
config `services/model-gateway/`.

**verify-m1** se valide SUR LA VM (accès GPU + creds Scaleway), PAS en CI
GitHub (ni GPU ni secrets). En CI : contrôle statique des scripts. Sur la VM,
`make verify-m1` fait UN cycle : crée le nœud, vérifie que vLLM répond sur
/v1/models, lance une inférence de contrôle, archive un bench simple sous
BRAIN/bench/, détruit le nœud, le tout en moins de 20 min. La preuve de M1
est l'exécution réussie de `make verify-m1` sur la VM. Voir contracts/m1.md.
## M2 — Ingestion + RAG
**But** : RAG hybride avec citations résolvables.
**Livrables** : ingestion (pdf/docx/md/html) → chunks + métadonnées + embeddings ;
recherche BM25+dense+reranker ; génération avec citations `chunk_id`.
Si `evals/golden/` ne contient pas encore E1/E2/E3, exécuter `generation/KIT-E1-E2-E3.md`
sur le corpus fourni (statut `genere-a-valider`, en attente de validation humaine).
**verify-m2** vérifie sur le corpus multilingue (corpus/) : l'ingestion produit des chunks avec métadonnées ; le retrieval atteint **recall@8 ≥ 0,70** sur le jeu doré E1 (gate M2 ; cible 0,85 à terme, relevable via M2_RECALL_MIN) ; chaque citation d'une réponse pointe vers un chunk réellement récupérable. M2 ne crée pas de GPU.

## M3 — Harness agentique + outils web
**But** : boucle d'outils bornée, recherche + lecture web sûres.
**Livrables** : machine à états (budgets durs POC-P6), outils `web_search` (SerpApi),
`web_fetch` (trafilatura, robots.txt, anti-SSRF), `rag_search`, `calculator`.
**verify-m3** vérifie : POC-E4 ≥ 90 % ; tests SSRF (IP privées refusées) + robots.txt +
plafond de fetches ; les 4 budgets déclenchent un arrêt propre (test d'intégration) ;
POC-E6 exécutable de bout en bout.

## M4 — Cascade + UI + escalade
**But** : routage S→L, fallback en cas de panne GPU, UI branchée.
**Livrables** : classifieur de routage, escalade vers Generative APIs Scaleway, UI
(Open WebUI/LibreChat) connectée au gateway.
**verify-m4** vérifie : POC-E8 ≥ 85 %, zéro sous-routage sur les cas critiques ;
fallback : si le modèle local est injoignable (panne simulée en coupant l'endpoint
local, SANS créer de GPU payant), le gateway bascule sur l'escalade Scaleway et répond
quand même. L'UI (Open WebUI/LibreChat) est un PLUS visuel, NON bloquant pour ce gate PoC.

## M5 — Évals complètes + télémétrie
**But** : mesurer, comparer, tracer.
**Livrables** : `make eval` (toutes suites, rapport HTML avec diff + ventilation par
langue, < 20 min), juge calibré (POC-R2), dashboard coût/latence, prefix-cache hit exposé.
**verify-m5** vérifie : `make eval` complet vert et sous budget/temps ; rapport généré ;
métriques de télémétrie présentes (tokens, coût, TTFT, tok/s, cache hit).

## M6 — Durcissement + bench final + rapport GO/NO-GO
**But** : preuve chiffrée pour la décision.
**Livrables** : bench de charge (POC-P1..P9), filtre d'entrée minimal, `make demo`
(scénario complet), rapport GO/NO-GO auto-généré depuis les mesures.
**verify-m6** vérifie : POC-P1..P9 mesurés et archivés ; `make demo` déroule un parcours
RAG + web + escalade sans erreur ; `reports/GO-NOGO.md` généré avec les chiffres réels.

---

### Checkpoints humains (hors de ta responsabilité, l'humain les fait)
Après M1 (infra/budget), après M3 (10 requêtes à la main), après M5 (calibration juge),
après M6 (décision). Entre ces points, tu avances seul et consignes dans BRAIN/.

### M1 — Confirmation des protections (levée du prérequis AUTO-2 / POC-I1/I2)
Protections budget CONFIRMÉES et ACTIVES : alertes Scaleway à 50% et 80% de 800€
(SMS + email), vérifiées en console. Extinction du GPU garantie par le trap de
verify-m1.sh (destruction en fin de test quoi qu'il arrive) et par l'appel explicite
à gpu-down.sh. Type GPU : sélection automatique par gpu-up.sh (L40S-1-48G en priorité, disponible). L'agent est AUTORISÉ à créer un GPU
facturé pour exécuter make verify-m1. Cette confirmation ne doit plus être redemandée.

### M2 — Moteur de génération confirmé
Pour l'étape de GÉNÉRATION du RAG (rédaction des réponses avec citations), utilise le
modèle L via Scaleway Generative APIs (ESCALATION_MODEL, déjà configuré dans .env,
endpoint SCW_GENERATIVE_BASE_URL). Le plafond budget est ACTIF et confirmé. Le petit
modèle CPU sert UNIQUEMENT aux embeddings/reranking, pas à la génération. Tu es autorisé
à appeler Generative APIs pour générer et produire des citations fiables.

### M3 — Autorisation de reprise (diagnostic provider_error)
Les erreurs provider_error sur E4-004/013/018 viennent probablement d'une réponse
tronquée (limite de tokens de sortie trop basse) quand le contexte est long (page web
fetchée). Tu es AUTORISÉ à : (1) augmenter la limite de tokens de sortie du gateway
(ex. 512 -> 2048), (2) tronquer/résumer les contenus web volumineux AVANT de les
passer au modèle (respect du plafond de contexte, docs/03 REQ-MOD-004), (3) relancer
les essais E4/E6 autant que nécessaire dans la limite du budget par requête (0,05 €).
Le function-calling Scaleway est supporté (doc officielle vérifiée). Continue jusqu'à
E4 >= 90% puis merge. Ne baisse pas le seuil E4, ne modifie pas les clés de correction.

### M5 — Juge de référence pour la calibration croisée
Le juge de référence pour la calibration croisée est **gpt-oss-120b** (Scaleway
Generative APIs, famille OpenAI, distincte du juge de production glm-5.2 ET du système
testé Qwen — l'indépendance des 3 familles est respectée). Utilise l'endpoint Scaleway
déjà configuré (SCW_GENERATIVE_BASE_URL, même clé). Calcule le κ de Cohen entre les
notes de glm-5.2 et celles de gpt-oss-120b sur l'échantillon d'éval. Aucun accès externe
ni juge humain requis pour le PoC ; la calibration humaine reste pré-GA.

### M5 — E9 traduction sans FLORES (PoC)
Le téléchargement de FLORES-200 échoue (miroir indisponible/authentification). Pour le
PoC, la suite E9 utilise UNIQUEMENT les cas déjà présents dans evals/golden/e9_traduction.yaml
(cas métier écrits et validés, faux amis + terminologie). N'exécute PAS fetch_flores.py,
ne bloque pas sur FLORES. L'extension FLORES-200 est une action post-PoC. E9 est évalué
sur les cas 'valide' disponibles.

### M5 — Correctif calibration (transport JSON du juge)
Le mode structured-output strict de Scaleway (response_format=json_object / json_schema)
produit un JSON doublement encapsulé (préfixe `{"{"`) invalide. Tu es AUTORISÉ à :
1. NE PAS utiliser le mode json_schema/json_object strict pour les appels juge ;
   demander le JSON dans le prompt (sortie texte) et le parser côté client de façon
   TOLÉRANTE (extraire le premier objet JSON valide {...} de la réponse, ignorer
   l'enrobage éventuel). Ceci n'est PAS "réparer une note" : c'est du parsing de
   transport, la note du juge n'est jamais modifiée.
2. Relancer une série d'appels bornée (budget < 3 EUR) pour produire la calibration.
3. Si un appel juge reste non parsable après extraction tolérante, l'exclure du calcul
   du κ et le SIGNALER dans le rapport (calibration best-effort sur cas valides).
Le juge de référence reste gpt-oss-120b (indépendance des familles préservée).

## M7 — UI de test + observabilité des interactions
**But** : rendre le système interrogeable via une UI de chat, avec un logging
structuré et exploitable de CHAQUE interaction, pour analyser qualité/latence/routage.

**Livrables** :
- `make serve` : démarre tous les services nécessaires en une commande (gateway
  http + retrieval + adaptateur), sans GPU par défaut (tout passe par l'escalade
  Scaleway ; le GPU local est activé seulement si GPU_LOCAL=1).
- **Adaptateur OpenAI-compatible** : expose `POST /v1/chat/completions` (protocole
  OpenAI standard) et le route vers le pipeline interne (RAG /answer, recherche web,
  ou escalade selon la nature de la requête). Permet de brancher n'importe quel
  client OpenAI, dont Open WebUI.
- **Open WebUI** en Docker, pointé sur l'adaptateur, accessible sur le port 3000 de
  la VM. L'utilisateur ouvre http://<ip-vm>:3000 et discute avec le système.
- **Logging structuré par interaction** : chaque requête produit une ligne JSON dans
  `BRAIN/interactions/<date>.jsonl` avec AU MINIMUM : timestamp, question, réponse,
  modèle_utilisé (local|escalade), route_decision (simple|complexe), latence_ms
  (retrieval, génération, total), chunks_récupérés (doc_id + score), citations
  (chunk_id résolus), tokens (in/out), coût_eur, erreurs/timeouts éventuels.
  Aucun secret ni clé dans les logs.

**verify-m7** vérifie : `make serve` démarre les services ; l'adaptateur répond à une
requête `/v1/chat/completions` de bout en bout (réponse + citation) ; une ligne de log
structurée est produite dans BRAIN/interactions/ avec les champs requis ; Open WebUI
est joignable (HTTP 200 sur le port 3000). Sans GPU (escalade seule) par défaut.

**Hors périmètre** : authentification multi-utilisateur, HTTPS, exposition publique
(le port reste sur la VM ; accès via SSH tunnel ou IP directe selon config réseau).

## PoC v2 (M8→M13) — voir docs/15-poc-v2.md

### Incident jeton GitHub — RISQUE ASSUMÉ (décision humaine, 2026-09-10)
Le jeton GitHub a été exposé hors de la VM. Le propriétaire du projet a examiné le
risque et DÉCIDE de ne pas le révoquer pour la durée du PoC : portée limitée à un
dépôt privé sans données sensibles, contexte de prototypage, coût de rotation jugé
supérieur au risque résiduel. L'incident est donc CLOS en tant que blocage : ce n'est
pas une révocation, c'est une acceptation de risque explicite et tracée.
Action reportée : rotation du jeton avant toute mise en production.
L'agent NE DOIT PLUS bloquer sur ce point ni redemander de confirmation.
