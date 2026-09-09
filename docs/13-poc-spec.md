# 13 — Spécification du PoC « ATLAS-0 »

> Durée cible : 6 semaines. Budget infra cible : < 800 € tout compris.
> Objet : démontrer sur données réelles qu'un assistant « Claude-like » construit sur
> modèles open-weight atteint un niveau de qualité mesuré et suffisant pour lancer la
> phase 1 — ou démontrer le contraire, ce qui est un succès du PoC aussi.
> Ce document est **auto-portant** : un agent d'implémentation doit pouvoir le réaliser
> en le lisant avec `14-implementation-autonome.md`, sans lire tout le corpus (les REQ
> du corpus citées ici sont reprises avec leur substance).

## 1. Ce que le PoC FAIT

| Id | Capacité | Détail |
|---|---|---|
| POC-F1 | Chat multi-tours en streaming | SSE, arrêt de génération, historique persisté |
| POC-F2 | RAG avec citations | Ingestion pdf/docx/md/html, hybride BM25+dense+reranker, citations cliquables résolues vers le passage source |
| POC-F3 | **Recherche web automatique** | Le modèle décide de chercher ; API SerpApi (Google Search + Google News), requêtes reformulées par le modèle, localisation `gl`/`hl` adaptée à la langue de la question |
| POC-F4 | **Lecture de pages web (scraping)** | Récupération + extraction du contenu principal (trafilatura), respect de robots.txt, cache local, contenus utilisés dans le raisonnement **avec citation URL + date** |
| POC-F5 | Appels d'outils en boucle agentique | Machine à états avec budgets durs ; outils : `web_search`, `web_fetch`, `rag_search`, `calculator` |
| POC-F6 | Cascade 2 niveaux | Modèle local (défaut) + escalade vers un modèle L serverless UE pour les requêtes complexes, via le gateway |
| POC-F7 | Évaluation automatique continue | Suite d'évals exécutable par CI et à la demande, rapport HTML, comparaison entre runs |
| POC-F8 | Télémétrie minimale | tokens, coût, TTFT, tok/s, taux de hit du prefix cache, par requête ; export CSV/dashboard simple |

## 2. Ce que le PoC ne fait PAS (assumé, ne pas implémenter)

Multi-tenant durci (une seule organisation, auth basique par mot de passe partagé ou
OIDC simple) · guardrails complets (un filtre d'entrée minimal seulement) · SSO/SCIM ·
haute disponibilité · sandbox d'exécution de code · fine-tuning · mémoire long terme ·
mobile · conformité formelle (mais **aucune donnée sensible réelle** dans le PoC :
corpus documentaire public ou interne non confidentiel uniquement — c'est la contrepartie
qui permet d'aller vite).

Règle : toute demande d'extension pendant le PoC est refusée par défaut et notée pour la
phase 1. Le périmètre est gelé à la signature de ce document.

## 3. Architecture PoC (2 machines)

```
[ VM CPU "app" — petite, ~10-20 €/mois ]
  ├─ UI (Open WebUI ou LibreChat)          ← on ne développe PAS d'UI
  ├─ gateway (LiteLLM) ── fallback ──────────► fournisseur serverless UE (modèle L)
  ├─ harness (FastAPI, ~800 lignes) : machine à états, outils, budgets
  ├─ client SerpApi (recherche) + fetcher (trafilatura) + cache
  ├─ Postgres + pgvector (conversations, chunks, télémétrie, résultats d'evals)
  └─ eval-harness (CLI)

[ Nœud GPU — éphémère, reconstructible par script ]
  └─ vLLM : modèle principal + (embeddings + reranker servis via le même vLLM ou TEI)
```

Décisions imposées :
- POC-A1 : le nœud GPU est **jetable** — provisionné par script (Terraform ou CLI du
  fournisseur + cloud-init), poids sur volume Block Storage persistant réattachable.
  Aucune installation manuelle en SSH.
- POC-A2 : la VM app est **permanente** (elle porte l'état) ; le nœud GPU est éteint
  la nuit et le week-end par cron (`scheduler on/off`) → ÷2 à ÷3 sur la facture.
- POC-A3 : tout l'applicatif ne connaît que le gateway (une URL). Changer de modèle ou
  de tier GPU = config uniquement.
- POC-A4 : prefix caching vLLM activé ; ordre des blocs de prompt stable (system →
  outils → docs → historique) — vérifié par un test.

## 4. Modèles du PoC

| Rôle | Choix initial | Remplaçant testé |
|---|---|---|
| Principal (local) | Qwen3-30B-A3B, FP8 (Apache-2.0) | tier supérieur si les évals plafonnent |
| Escalade (serverless UE) | un modèle L open-weight hébergé UE (classe GLM/DeepSeek/Kimi) | second fournisseur en fallback |
| Embeddings | modèle multilingue open-weight, dim ≤ 1024 | — |
| Reranker | cross-encoder open-weight | — |
| Juge d'évals | le modèle L serverless (≠ modèle évalué) | — |

## 5. Outils web — spécification précise (POC-F3/F4)

- POC-W1 : `web_search(query, n=5, lang)` interroge **SerpApi** (Google Search ; Google
  News pour les questions d'actualité). Retour : titre, URL, snippet, date si dispo.
  Paramètres `gl`/`hl` alignés sur la langue détectée de la question (une question en
  allemand cherche sur google.de en allemand). Plan **Starter (25 $/mois, 1 000
  recherches)** ; quota applicatif dans le harness : max 3 recherches/requête utilisateur,
  compteur mensuel avec arrêt propre à 90 % du quota, cache des recherches identiques
  (TTL 1 h) pour ne pas brûler le quota sur les évals répétées — la FAQ SerpApi indique
  que seules les recherches réussies sont décomptées, et les runs d'évals sont les plus
  gros consommateurs.
  *Note de résidence* : SerpApi est un prestataire US ; acceptable pour le PoC car seules
  les **requêtes de recherche** (jamais les documents ni les conversations complètes) lui
  sont transmises et le corpus PoC est non sensible. Pour la prod, ce point repasse par
  la revue REQ-INF-002/REQ-CMP-004 (DPA, clauses de transfert) ou par une alternative UE —
  décision à instruire en phase 1, pas dans le PoC.
- POC-W2 : `web_fetch(url)` : GET avec User-Agent identifié, timeout 15 s, taille max
  2 Mo, **respect de robots.txt**, extraction du contenu principal par trafilatura,
  troncature à 8 000 tokens avec handle pour la suite, cache disque TTL 24 h.
- POC-W3 : sécurité minimale mais non négociable, même en PoC :
  - denylist de réseaux privés (SSRF : 10.x, 172.16–31.x, 192.168.x, 169.254.x,
    localhost, métadonnées cloud 169.254.169.254) ;
  - contenu web = **non fiable** : encadré par délimiteurs + instruction de ne jamais
    exécuter d'instructions qu'il contient ; aucun outil à effet de bord n'existe dans
    le PoC (tous les outils sont read-only), ce qui neutralise l'essentiel du risque ;
  - max 8 fetches par requête utilisateur.
- POC-W4 : toute affirmation issue du web porte URL + date de consultation dans la
  réponse. Le pipeline de vérification de citations (POC-E5) s'applique aussi au web.
- POC-W5 : boucle de recherche type : reformuler → chercher → sélectionner 2–3 URLs →
  fetch → synthétiser → si insuffisant, itérer (max 3 itérations, budget POC-P6).

## 6. Performances attendues (cibles mesurables)

Chargées comme seuils dans l'eval-harness ; un chiffre non atteint = décision explicite
(accepter/corriger/monter de tier), pas un haussement d'épaules.

| Id | Métrique | Cible PoC | Mesure |
|---|---|---|---|
| POC-P1 | TTFT p95 (chat sans outil) | < 2,0 s | bench de charge scripté |
| POC-P2 | Débit décodage p95 | > 30 tok/s | idem |
| POC-P3 | Latence bout-en-bout p95, requête RAG | < 12 s | idem |
| POC-P4 | Latence bout-en-bout p95, requête web (2 fetches) | < 30 s | idem |
| POC-P5 | Concurrence soutenue sans dégradation > 20 % | 8 requêtes parallèles | idem |
| POC-P6 | Budgets durs par requête | ≤ 10 appels d'outils, ≤ 120 s, ≤ 0,05 € | test d'intégration qui les fait sauter |
| POC-P7 | Prefix cache hit rate | > 50 % | métrique vLLM |
| POC-P8 | Coût moyen / requête (GPU amorti + serverless) | < 0,02 € | télémétrie |
| POC-P9 | Disponibilité heures ouvrées sur les 2 dernières semaines | > 97 % | uptime monitor |

## 7. Validation automatique de la qualité (le cœur du PoC)

Jeu doré versionné dans Git : **140 cas minimum**, répartis sur **FR, DE, ES, IT, EN
(aucune langue < 15 % du jeu)**, scores calculés et rapportés **par langue** :

| Suite | Cas | Vérification | Seuil GO |
|---|---|---|---|
| POC-E1 retrieval | 40 questions → doc/chunk attendu (corpus et questions multilingues, y compris question dans une langue ≠ langue du document) | **déterministe** : recall@8, MRR | recall@8 ≥ 0,85 |
| POC-E2 RAG bout-en-bout | 30 Q/R sur le corpus | juge LLM (rubrique exactitude/complétude) + présence de citation | ≥ 4,0/5 moyen |
| POC-E3 refus honnête | 10 questions sans réponse dans le corpus | déterministe (regex « ne trouve pas ») + juge | 10/10 : zéro invention |
| POC-E4 tool-calling | 20 scénarios (bon outil, bons args, récupération sur erreur injectée) | déterministe (assertions sur la trace) | ≥ 90 % |
| POC-E5 fidélité des citations | échantillon des réponses E2 + web | vérificateur NLI/juge : chaque citation supporte la phrase | ≥ 0,90 |
| POC-E6 **web Q/R** | 20 questions dont la réponse n'existe que sur le web (fraîches, vérifiables), réparties sur les 5 langues avec sources locales (presse DE/ES/IT…) | juge + vérification manuelle initiale de la clé de correction | ≥ 80 % correctes et sourcées |
| POC-E7 comportement | 15 cas anti-flagornerie / honnêteté / format (mini-charte) | juge calibré | ≥ 4,0/5 |
| POC-E8 routage | 30 requêtes étiquetées simple/complexe | déterministe : matrice de confusion | ≥ 85 % ; zéro « complexe→local » silencieux sur les cas critiques |
| POC-E9 **traduction** | 20 paires entre FR/DE/ES/IT/EN (textes métier, pas littéraires ; inclut « réponds en X à ce document en Y ») | métrique automatique (COMET ou juge bilingue calibré) | ≥ 4,0/5 ; aucun sens inversé |

Seuil transversal (POC-EL) : pour chaque suite jugée (E2, E6, E7, E9), **l'écart entre
la meilleure et la moins bonne langue ≤ 15 %** — c'est le test d'égalité de traitement.
Un modèle qui passe les moyennes mais échoue ce seuil est un NO-GO au même titre.

Règles d'exécution :
- POC-R1 : `make eval` exécute tout, produit un rapport HTML horodaté avec diff vs le
  run précédent **et ventilation par langue**, stocke les résultats en base.
  Durée < 20 min, coût < 3 €.
- POC-R2 : le juge (modèle L serverless) est calibré une fois par langue : 30 cas notés
  par un humain (répartis sur les 5 langues), accord vérifié (désaccord moyen ≤ 0,5
  point) avant de faire foi.
- POC-R3 : les cas E6 (web) incluent la date de création de la clé de correction ; un
  cas périmé (la réalité a changé) est marqué `stale`, pas compté en échec.
- POC-R4 : CI : `make eval-smoke` (15 cas représentatifs couvrant ≥ 3 langues, < 3 min,
  < 0,3 €) sur chaque PR ; suite complète nightly + à chaque changement de modèle/prompt.

## 8. Critères GO / NO-GO de fin de PoC

**GO phase 1** si : tous les seuils §6 et §7 atteints avec le modèle local (escalades
≤ 25 % des requêtes) **ou** atteints avec un tier GPU supérieur dont le coût projeté
respecte REQ-NFR-005 (< 0,015 €/req à l'échelle). Sinon : rapport d'écart chiffré et
décision explicite (changer de modèle, revoir les cibles, ou arrêter).

## 9. Infrastructure louée — recommandation chiffrée (juillet 2026, à re-vérifier au devis)

| Option | Machine | Prix constaté | Rôle recommandé |
|---|---|---|---|
| **Recommandé : Scaleway L40S-1-48G** (Paris) | 48 Go VRAM, ~8 vCPU, scratch NVMe | **~1,47 €/h HT** ; ~250–350 €/mois en heures ouvrées avec extinction planifiée (POC-A2) | Nœud GPU principal : Qwen3-30B-A3B FP8 + embeddings + reranker. FP8 natif (Ada). Facturation horaire = parfait pour l'extinction nocturne. UE/France, cohérent avec la contrainte de souveraineté. |
| Scaleway L4-1-24G | 24 Go | ~0,75–0,90 €/h | Variante ultra-frugale (30B-A3B en Q4 serré) ; garder en secours |
| Scaleway H100-1-80G | 80 Go | ~2,7–3,0 €/h | Le « tier au-dessus » pour tester un MoE ~120B en fin de PoC (quelques jours suffisent) |
| Hetzner GEX130 (RTX 6000 Ada 48 Go) | dédié mensuel | ~900 €/mois flat (à re-vérifier) | Uniquement si le PoC devait tourner 24/7 — pas notre cas, l'horaire Scaleway gagne |
| RunPod/Vast (spot L40S) | 48 Go | ~0,26–0,50 €/h | Le moins cher, mais hors UE/préemptible : acceptable pour des benchs jetables, pas pour le PoC de référence |
| VM app (Scaleway DEV/PRO ou Hetzner CX) | 4–8 vCPU, 16 Go RAM | ~10–25 €/mois | UI, gateway, harness, client SerpApi, Postgres |

Budget PoC 6 semaines, réaliste : GPU ~350–500 € (heures ouvrées + quelques nightly
d'évals + 3–4 jours de H100 en fin de PoC) + VM ~30 € + serverless L (escalades + juge)
~50–120 € + SerpApi Starter 2 mois ~45 € + stockage ~10 € ≈ **500–700 €**.

- POC-I1 : alerte budget chez le fournisseur à 50 % et 80 % de 800 € ; coupe-circuit
  applicatif sur le serverless (plafond mensuel dans le gateway).
- POC-I2 : l'extinction planifiée du GPU est en place **dès le premier jour** (c'est le
  levier n°1 du budget) ; le redémarrage matinal recharge le modèle automatiquement
  (< 10 min, poids sur volume persistant).


> **Clarification M5 (PoC)** : la calibration du juge en M5 est une calibration CROISÉE inter-modèles (juge production glm-5.2 vs juge de référence d'une autre famille, Claude), pas une calibration humaine. La calibration humaine (30 notes, κ≥0,7) reste une action **pré-GA**, non bloquante pour le PoC. Voir verify-m5.
