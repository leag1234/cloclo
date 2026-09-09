# 06 — Harness : orchestration agentique, outils, RAG, mémoire

> C'est ici que se joue la différence perçue entre « un chatbot open source » et « une
> expérience de qualité ». Un modèle moyen avec un excellent harness bat un excellent
> modèle avec un harness médiocre, sur des tâches réelles.

## 1. Orchestrateur

### 1.1 Machine à états (rappel `02` §2.2)
Explicite, testable, reprise sur incident. Interdiction d'une boucle implicite non bornée.

- REQ-HAR-001 (MUST) : `max_tool_calls` (12), `max_wall_clock` (120 s), `max_cost_eur`
  (0,10 €), `max_tokens` par requête. Dépassement → terminaison **explicite** avec message
  utilisateur honnête (« je n'ai pas pu terminer, voici où j'en suis »), jamais de sortie
  tronquée silencieusement.
- REQ-HAR-002 (MUST) : détection de boucle — si les 3 derniers appels d'outils sont
  identiques (même nom, mêmes arguments normalisés), interruption et changement de
  stratégie ou abandon explicite.
- REQ-HAR-003 (MUST) : parallélisation des appels d'outils **indépendants** (le modèle
  peut en émettre plusieurs par tour). Impact latence majeur.
- REQ-HAR-004 (MUST) : idempotence — chaque `step_id` est rejouable sans effet de bord
  dupliqué (clé d'idempotence propagée aux outils mutants).

### 1.2 Gestion du contexte
- REQ-HAR-005 (MUST) : politique de compaction déterministe quand la conversation dépasse
  le budget : résumé structuré des tours anciens (via modèle S, peu cher) + conservation
  intégrale des N derniers tours + conservation **intégrale** des résultats d'outils
  récents. Le résumé est persisté, pas recalculé à chaque tour.
- REQ-HAR-006 (MUST) : les résultats d'outils volumineux (dumps SQL, gros fichiers) sont
  **tronqués avec un handle** (`result_id` récupérable via un outil `fetch_result`),
  jamais collés en entier dans le contexte.

## 2. Outils (function calling)

- REQ-TOOL-001 (MUST) : chaque outil est déclaré par un **JSON Schema** strict, avec
  description, exemples, effets de bord (`readonly` | `mutating` | `destructive`), et
  coût/latence attendus.
- REQ-TOOL-002 (MUST) : validation du schéma **avant** exécution ; en cas d'arguments
  invalides, retour d'une erreur structurée et lisible par le modèle (« champ `date` :
  format attendu YYYY-MM-DD, reçu '12 mars' ») — pas une stack trace. La qualité des
  messages d'erreur détermine la capacité du modèle à se corriger : c'est un composant
  de qualité, pas de la plomberie.
- REQ-TOOL-003 (MUST) : les outils `destructive` exigent une **confirmation utilisateur
  explicite** hors du contrôle du modèle (l'UI demande, le modèle ne peut pas contourner).
- REQ-TOOL-004 (MUST) : timeout et retry (backoff exponentiel, max 2 essais) par outil ;
  un outil qui échoue renvoie une erreur exploitable, il ne fait pas échouer la requête.
- REQ-TOOL-005 (MUST) : **budget d'outils par tenant** et journalisation de chaque appel
  (qui, quoi, quand, arguments, résultat tronqué, coût).
- REQ-TOOL-006 (SHOULD) : au-delà de ~20 outils, ne pas tous les injecter dans le prompt :
  **sélection dynamique** des outils pertinents (recherche sémantique sur les descriptions).
  Attention : cela casse le prefix cache — mesurer le compromis coût/qualité.

### 2.1 MCP (Model Context Protocol)
- REQ-TOOL-007 (SHOULD) : les connecteurs métier sont exposés via MCP → standardisation,
  réutilisation, découplage. Serveurs MCP internes, jamais de serveur tiers non audité.
- REQ-TOOL-008 (MUST) : un serveur MCP tiers est traité comme du **code non fiable** :
  audit du code, épinglage de version, exécution isolée, permissions minimales. Les
  descriptions d'outils fournies par un MCP sont un vecteur d'injection de prompt (`07`).

### 2.2 Outil de recherche web (REQ-FUN-011, phase 2)
- REQ-TOOL-012 (MUST) : la recherche et la récupération de pages passent par un **proxy
  de sortie unique** : allowlist/denylist de domaines par tenant, journalisation, budget
  de requêtes, aucun cookie ni credential, User-Agent identifié.
- REQ-TOOL-013 (MUST) : tout contenu web est **non fiable** (REQ-SEC-011) et déclenche le
  mode « privilèges restreints » du tour (REQ-SEC-015) : pas d'outil mutant dans le même
  tour sans confirmation humaine.
- REQ-TOOL-014 (MUST) : les réponses fondées sur le web portent des citations résolvables
  (URL + date de consultation), avec la même vérification post-hoc que le RAG
  (REQ-RAG-011). Extraits courts uniquement : pas de reproduction substantielle de
  contenus tiers (droit d'auteur — même règle que pour les documents internes sous
  licence).
- REQ-TOOL-015 (SHOULD) : cache de pages (TTL par type de contenu) pour le coût et la
  reproductibilité des traces.

### 2.3 Sandbox d'exécution de code
- REQ-TOOL-009 (MUST) : isolation par microVM (Firecracker) ou gVisor. **Pas** un simple
  conteneur Docker.
- REQ-TOOL-010 (MUST) : pas de réseau sortant par défaut ; allowlist explicite si besoin.
  Limites CPU/RAM/disque/durée. Système de fichiers éphémère, détruit après usage.
- REQ-TOOL-011 (MUST) : aucun secret, aucune variable d'environnement de production dans
  la sandbox.

## 3. RAG — spécification

### 3.1 Ingestion
```
source → extraction → nettoyage → découpage → enrichissement → embedding → index
```
- REQ-RAG-001 (MUST) : extraction fidèle par type (PDF texte vs PDF scanné → OCR ; tableaux
  préservés en structure, pas aplatis en soupe de mots ; docx → conserver titres/hiérarchie).
  L'extraction bâclée est **la première cause** de RAG médiocre — bien avant le choix du
  modèle d'embedding.
- REQ-RAG-002 (MUST) : découpage sémantique respectant la structure (titres, sections),
  taille cible 300–800 tokens, chevauchement 10–15 %. Chaque chunk porte son **contexte
  parent** (titre du document, chemin de section) préfixé — gain de rappel important pour
  un coût nul.
- REQ-RAG-003 (MUST) : métadonnées obligatoires par chunk : `tenant_id`, `doc_id`,
  `chunk_id`, `source_uri`, `acl`, `version`, `date_maj`, `checksum`.
- REQ-RAG-004 (MUST) : ré-indexation incrémentale sur changement de source ; suppression
  effective quand la source est supprimée (droit à l'effacement, RGPD).

### 3.2 Recherche
- REQ-RAG-005 (MUST) : **recherche hybride** — BM25 (lexical) + dense (sémantique), fusion
  par RRF. Le lexical seul rate les paraphrases ; le dense seul rate les identifiants,
  codes produits, références juridiques. En entreprise, le lexical est indispensable.
- REQ-RAG-006 (MUST) : **reranker cross-encoder** sur le top-50 → top-5/8. C'est le
  meilleur rapport gain/effort de tout le pipeline RAG.
- REQ-RAG-007 (MUST) : **filtrage ACL au niveau de la requête**, pas après. L'index est
  interrogé avec le contexte de permissions de l'utilisateur. Un chunk qu'un utilisateur
  n'a pas le droit de voir ne doit jamais atteindre la couche de reranking.
  Test de non-régression obligatoire (`08` §4).
- REQ-RAG-008 (SHOULD) : réécriture de requête (modèle XS) : décontextualisation des
  pronoms depuis l'historique, expansion multi-requêtes. Gain de rappel notable.
- REQ-RAG-009 (SHOULD) : *self-check* — si aucun chunk ne dépasse un seuil de pertinence,
  le modèle **doit** répondre « je n'ai pas trouvé d'information à ce sujet dans vos
  documents » plutôt que d'improviser. Cette règle seule élimine une grande partie des
  hallucinations perçues.

### 3.3 Génération et citations
- REQ-RAG-010 (MUST) : chaque affirmation factuelle issue des documents porte une citation
  `chunk_id` résolvable en source cliquable.
- REQ-RAG-011 (MUST) : **vérification post-hoc des citations** — un vérificateur
  (modèle XS ou NLI) contrôle que chaque phrase citée est effectivement supportée par le
  chunk référencé. Les citations non supportées sont retirées et l'incident est mesuré
  (métrique `citation_faithfulness`, cf. `09`).
- REQ-RAG-012 (MUST) : les contenus récupérés sont encadrés comme **données non fiables**
  (`07` §3) — jamais interprétés comme des instructions.

## 4. Mémoire

Trois horizons, à ne pas confondre :
1. **Contexte de la conversation courante** (§1.2).
2. **Mémoire de conversation longue** : résumés persistés, rappelés au chargement.
3. **Mémoire à long terme / faits utilisateur** : REQ-HAR-007 (SHOULD) — extraction de
   faits stables, stockage explicite, **visible et éditable par l'utilisateur**
   (transparence, RGPD). Opt-in. Jamais implicite.

- REQ-HAR-008 (MUST) : la mémoire est cloisonnée par `tenant_id` **et** par `user_id`.
  Une fuite de mémoire inter-utilisateur est un incident de sécurité de sévérité 1.

## 5. Critères d'acceptation

- AC-HAR-1 : test d'intégration prouvant l'arrêt sur chacun des 4 budgets (REQ-HAR-001).
- AC-HAR-2 : test prouvant qu'un utilisateur sans droit sur un document n'obtient jamais
  ce document, même par question détournée (10 scénarios adversariaux minimum).
- AC-RAG-1 : évaluation du retrieval isolée du LLM (recall@k, MRR, nDCG) sur un jeu doré
  de ≥ 200 paires question/document. On ne débugue pas un RAG en regardant les réponses
  finales : on mesure chaque étage séparément.
- AC-RAG-2 : `citation_faithfulness` ≥ 0,95 sur le jeu doré.
- AC-TOOL-1 : taux de succès du tool-calling ≥ 95 % sur une suite de 100 scénarios
  (bons arguments, bon outil, bonne récupération après erreur injectée).
