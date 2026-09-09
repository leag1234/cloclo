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
**But** : un nœud GPU naît et meurt par script ; le gateway sert un modèle.
**Livrables** : `infra/gpu-up.sh` (crée l'instance ${GPU_INSTANCE_TYPE}, monte le volume
de poids persistant, lance vLLM avec prefix caching), `infra/gpu-down.sh`, gateway
(config `routing.yaml` : local + fallback Generative APIs Scaleway).
**verify-m1** vérifie : `infra/gpu-up.sh` crée le nœud DEPUIS ZÉRO ; `curl` gateway
`/v1/models` → 200 ; un bench TTFT/tok-s est produit et archivé sous `BRAIN/bench/` ;
`infra/gpu-down.sh` détruit instance+IP ; **re-création complète chronométrée < 20 min**.
> Marqueur budget : chaque création écrit le coût/h dans BRAIN/STATUS.md (docs/14).

## M2 — Ingestion + RAG
**But** : RAG hybride avec citations résolvables.
**Livrables** : ingestion (pdf/docx/md/html) → chunks + métadonnées + embeddings ;
recherche BM25+dense+reranker ; génération avec citations `chunk_id`.
Si `evals/golden/` ne contient pas encore E1/E2/E3, exécuter `generation/KIT-E1-E2-E3.md`
sur le corpus fourni (statut `genere-a-valider`, en attente de validation humaine).
**verify-m2** vérifie : POC-E1 recall@8 ≥ 0,85 sur les cas `valide` ; chaque citation
d'une réponse pointe vers un chunk réellement récupérable (test automatique).

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
