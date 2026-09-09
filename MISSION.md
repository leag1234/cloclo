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
panne GPU simulée (`infra/gpu-down.sh` en plein trafic) → l'UI répond encore via fallback.

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
