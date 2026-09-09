# 02 — Architecture cible

## 1. Vue d'ensemble (C4 niveau 2)

```
                    ┌──────────────┐
   Web / Desktop ───│  edge-bff    │  auth OIDC, rate-limit, SSE
   Mobile           └──────┬───────┘
                           │ gRPC/HTTP (contrat OpenAPI v1)
                    ┌──────▼───────────────────────────┐
                    │        orchestrator              │  boucle agentique,
                    │  (state machine, pas de LLM      │  budget tokens/temps,
                    │   logic en dur)                  │  reprise sur échec
                    └─┬────┬────┬────┬────────────┬────┘
                      │    │    │    │            │
        ┌─────────────▼┐ ┌─▼──────┐ ┌▼─────────┐ ┌▼──────────────┐
        │ model-gateway│ │ guard  │ │ retrieval│ │ tool-runtime  │
        │ (routage,    │ │ rails  │ │ (RAG)    │ │ (MCP, sandbox)│
        │  fallback,   │ │        │ │          │ │               │
        │  cache)      │ └────────┘ └────┬─────┘ └───────┬───────┘
        └──┬───────┬───┘                 │               │
           │       │              ┌──────▼─────┐   ┌─────▼──────┐
   ┌───────▼──┐ ┌──▼────────┐     │ vector +   │   │ gVisor /   │
   │ provider │ │ self-host │     │ BM25 + doc │   │ Firecracker│
   │ serverless│ │ vLLM/SGLang│    │ store      │   │ sandbox    │
   └──────────┘ └───────────┘     └────────────┘   └────────────┘

  Transverse : identity, config (feature flags), observability (OTel),
               eval-harness, audit-log (append-only), finops-collector
```

## 2. Composants — responsabilité unique

### 2.1 `edge-bff`
- Terminaison TLS, authentification OIDC/SAML, autorisation par tenant, quotas.
- Streaming SSE vers le client ; **aucune logique métier**.
- REQ-ARC-001 (MUST) : le BFF ne parle jamais directement à un fournisseur de modèle.

### 2.2 `orchestrator` — cœur du système
Machine à états explicite, **pas** une boucle `while true` implicite.

États : `PLAN → RETRIEVE? → GENERATE → TOOL_CALL? → OBSERVE → GENERATE … → FINALIZE`

- REQ-ARC-002 (MUST) : chaque transition est journalisée avec un `trace_id` et un `step_id`.
- REQ-ARC-003 (MUST) : budgets durs par requête — `max_tokens`, `max_tool_calls` (défaut 12),
  `max_wall_clock` (défaut 120 s), `max_cost_eur` (défaut 0,10 €). Dépassement → arrêt propre
  avec message utilisateur, jamais de troncature silencieuse.
- REQ-ARC-004 (MUST) : l'état de la conversation est persisté après chaque étape → reprise
  possible après crash (idempotence par `step_id`).
- REQ-ARC-005 (MUST) : aucun prompt en dur dans le code. Les prompts sont des **artefacts
  versionnés** (`prompts/<name>/<semver>.md`), chargés par identifiant, testés dans les évals.

### 2.3 `model-gateway` — point d'indirection critique
Unique composant qui connaît l'existence de modèles et de fournisseurs.

- REQ-ARC-006 (MUST) : expose une API interne stable et neutre (`POST /v1/generate`,
  schéma OpenAI-compatible en interne — c'est le lingua franca de l'écosystème).
- REQ-ARC-007 (MUST) : routage par **classe de tâche**, pas par nom de modèle.
  L'appelant demande `task_class: "chat_simple" | "reasoning" | "coding" | "extraction"
  | "classification" | "summarize"`. Le mapping classe→modèle est en config.
- REQ-ARC-008 (MUST) : fallback en cascade et *circuit breaker* par fournisseur.
- REQ-ARC-009 (MUST) : cache sémantique + cache exact (voir `04-finops.md` §5).
- REQ-ARC-010 (MUST) : comptabilise tokens et coût par requête, tenant, fonctionnalité.
- REQ-ARC-011 (SHOULD) : *shadow traffic* — possibilité d'envoyer X % du trafic à un
  modèle candidat sans servir sa réponse, pour comparaison offline.

**Contrat (extrait, à figer en OpenAPI avant tout code) :**
```yaml
POST /internal/v1/generate
request:
  task_class: string        # requis
  messages: [{role, content, tool_calls?, tool_call_id?}]
  tools?: [JSONSchema]
  constraints: {max_tokens, temperature, stop?, response_format?}
  routing_hints?: {latency_class: "interactive"|"batch", quality_floor: 0..1}
  tenant_id: string         # requis, pour quota + isolation
  trace_id: string          # requis
response (SSE ou unaire):
  content_blocks: [{type: "text"|"tool_use", ...}]
  usage: {input_tokens, output_tokens, cached_input_tokens, cost_eur}
  model_meta: {provider, model_id, model_version, routed_by}
```

### 2.4 `guardrails`
Deux passes obligatoires : **pré-génération** (entrée utilisateur + contenus récupérés)
et **post-génération** (sortie). Détail : `07-securite-et-conformite.md`.

### 2.5 `retrieval`
Hybride BM25 + dense + reranker. Détail : `06-harness-agent-outils-rag.md`.

### 2.6 `tool-runtime`
Exécution des outils, y compris serveurs MCP. Isolation forte. Détail : `06`.

## 3. Décisions d'architecture (ADR condensés)

| ADR | Décision | Raison | Conséquence |
|---|---|---|---|
| ADR-001 | Pas de GPU dédié en phase 1 ; inférence via fournisseur open-weight à l'usage, hébergé UE. | Volume < seuil de rentabilité (`04` §4). | Dépendance fournisseur → mitigée par ADR-002. |
| ADR-002 | `model-gateway` obligatoire, contrat neutre, ≥ 2 fournisseurs qualifiés en permanence. | Éviter le lock-in ; REQ-NFR-009. | Coût de dev initial +2 semaines. |
| ADR-003 | Routage par classe de tâche avec cascade petit→grand modèle. | 60–80 % des requêtes n'ont pas besoin du modèle frontier. | Nécessite un classifieur de complexité (voir `03` §5). |
| ADR-004 | Prompts et politiques = artefacts versionnés, pas du code. | Itération rapide + évals reproductibles. | Registre de prompts à construire. |
| ADR-005 | Python (ML, harness) + Go ou TypeScript (services edge/tooling). Un seul langage par service. | Écosystème ML ; perf edge. | Deux chaînes CI. |
| ADR-006 | Postgres (+ pgvector au démarrage) plutôt qu'une base vectorielle dédiée. | Simplicité opérationnelle < 50 M chunks. | Migration prévue (Qdrant/Vespa) si > 50 M ou latence p95 > 150 ms. |
| ADR-007 | Kubernetes + GitOps (ArgoCD) + Terraform. Pas de déploiement impératif. | Reproductibilité, audit. | Courbe d'apprentissage. |
| ADR-008 | Pas de framework agentique lourd (LangChain & co) dans le chemin critique. | Dette cachée, abstractions fuyantes, difficile à tester. | On écrit ~1 500 lignes d'orchestrateur explicite. Assumé. |

> ADR-008 est important pour des agents implémenteurs : la tentation d'importer un
> framework pour « aller vite » produit un système impossible à évaluer et à débuguer.
> Les bibliothèques sont autorisées **hors** du chemin critique (ingestion, notebooks).

## 4. Flux de référence — requête RAG avec outil

1. `edge-bff` : auth → quota → crée `trace_id` → stream SSE ouvert.
2. `orchestrator` : charge l'état de conversation, applique le budget.
3. `guardrails.pre(input)` → si bloqué, réponse de refus templatée, fin.
4. `retrieval.search(query, tenant_id)` → top-k chunks + scores. **Les chunks sont marqués
   `untrusted`** et encadrés dans le prompt (anti-injection, cf. `07`).
5. `model-gateway.generate(task_class=…)` → stream.
6. Si `tool_use` : `tool-runtime.execute()` (résultat aussi marqué `untrusted`) → retour en 5.
7. `guardrails.post(output)` → si bloqué, on n'affiche pas ; incident loggé.
8. Persistance : messages, usage, coût, citations, versions (modèle, prompt, politique).

## 5. Environnements

`dev` (éphémère par branche) · `staging` (miroir de prod, données synthétiques) ·
`prod`. Aucun accès humain direct en écriture sur `prod` : tout passe par GitOps.

## 6. Critères d'acceptation de l'architecture

- AC-ARC-1 : changer de fournisseur d'inférence = 1 PR de config, 0 changement de code applicatif. **Testé** par un game day mensuel.
- AC-ARC-2 : un test d'intégration prouve qu'un dépassement de `max_cost_eur` interrompt la requête.
- AC-ARC-3 : une trace OTel unique couvre le parcours complet BFF → gateway → provider.
- AC-ARC-4 : `grep -r "qwen\|glm\|deepseek\|llama" --exclude-dir=model-gateway src/` ne retourne rien (CI bloquante).
