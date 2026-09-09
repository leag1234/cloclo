# 03 — Modèles et couche d'inférence

> **Avertissement de fraîcheur.** Le classement des modèles open-weight change tous les
> 4 à 8 semaines. Ce document fixe une **méthode de sélection** et un **portefeuille au
> 14/07/2026**. Le portefeuille est révisé mensuellement (rituel `model-review`, cf. `12`).
> Aucun composant hors `model-gateway` ne doit dépendre d'un nom de modèle (REQ-ARC-006).

## 1. Vocabulaire — à ne pas confondre

- **Open source (OSI)** : poids + code + données + pipeline d'entraînement publiés.
  Quasiment aucun modèle frontier n'y répond.
- **Open weight** : poids téléchargeables, licence variable, données non publiées.
  C'est ce que nous utilisons. Les modèles cités (Qwen, GLM, DeepSeek, Kimi, Llama, Gemma)
  sont **open-weight**, pas open source.
- **REQ-MOD-001 (MUST)** : la communication interne et externe emploie « open-weight ».
  Une revendication « open source » exposerait l'entreprise à une critique fondée.

## 2. Grille de sélection (pondérée)

| Critère | Poids | Note |
|---|---|---|
| Licence (Apache-2.0 / MIT = 1,0 ; licence custom avec plafonds = 0,5 ; NC = 0) | 25 % | Bloquant si 0 |
| Score sur **nos** évals métier (pas les benchmarks publics) | 30 % | cf. `09` |
| Coût par requête à qualité constante | 20 % | cf. `04` |
| Disponibilité chez ≥ 2 fournisseurs UE + hébergeable | 10 % | REQ-NFR-009 |
| Qualité du tool-calling et du suivi de format | 10 % | eval dédiée |
| Support vLLM/SGLang, quantization FP8 | 5 % | |

- **REQ-MOD-002 (MUST)** : la licence est validée par le juridique **avant** tout POC.
  Vérifier : usage commercial, plafonds d'utilisateurs, restrictions géographiques,
  clauses sur les sorties du modèle, obligations d'attribution.
  Llama et certaines licences « custom » imposent des conditions ; Apache-2.0 (Qwen) et
  MIT (GLM, DeepSeek, Phi) sont les plus propres.
- **REQ-MOD-003 (MUST)** : un modèle n'entre en production qu'après avoir passé la suite
  d'évals `09` avec un score ≥ au champion en place, ou meilleur ratio qualité/coût.
- **REQ-MOD-005 (MUST)** : la qualité **dans chacune des langues cibles (FR, DE, ES, IT,
  EN)** et l'efficacité du tokenizer dans ces langues (tokens/mot mesurés sur un corpus
  interne de référence par langue) font partie de la grille §2. Un modèle excellent en
  anglais mais faible dans une langue cible est disqualifié pour la classe M/L
  conversationnelle. À qualité égale, un tokenizer 25 % plus efficace sur nos langues =
  25 % de coût d'entrée en moins : critère économique, pas cosmétique (REQ-NFR-011).
- **REQ-MOD-006 (MUST)** : le modèle d'embedding est versionné et **figé par corpus**
  (`embedding_model_version` dans les métadonnées de chaque chunk). Changer de modèle
  d'embedding impose une ré-indexation complète : la migration se fait par **double
  indexation** (ancien + nouveau index en parallèle, bascule après validation des évals de
  retrieval, puis suppression de l'ancien). Interdiction de mélanger deux espaces
  d'embedding dans un même index.

## 3. Portefeuille de référence (juillet 2026 — à revalider)

| Classe | Rôle | Candidats | Taille / archi | Licence |
|---|---|---|---|---|
| **XS** | classification, routage, garde-fous, réécriture de requête | Qwen3-4B/8B, Gemma-class, Phi-4 | dense, 4–15B | Apache/MIT |
| **S** | chat simple, extraction, résumé | Qwen3-30B-A3B (MoE) | ~30B tot / 3B actifs | Apache-2.0 |
| **M** | défaut conversationnel, RAG | Qwen3-235B-A22B | 235B tot / 22B actifs, ctx 1M | Apache-2.0 |
| **L** | raisonnement, code, agentique long | GLM-5.x, Kimi K2.5/K2.6, DeepSeek | MoE ~750B–1T tot / 32–40B actifs | MIT / MIT modifiée |
| **Embeddings** | RAG | modèle multilingue open-weight, dim ≤ 1024 | — | Apache |
| **Reranker** | RAG | cross-encoder open-weight | — | Apache |

Notes d'ingénierie :
- Les **MoE** (peu de paramètres actifs par token) sont l'élément décisif pour le coût :
  un 235B-A22B coûte à l'inférence approximativement comme un dense ~22–30B, tout en
  gardant la capacité d'un très gros modèle. **Privilégier systématiquement les MoE.**
- Les modèles L (≈1T paramètres totaux) exigent des nœuds 8×H100/H200. Ne pas les
  auto-héberger avant la phase 3 (cf. `04` §4).
- Le contexte long (200k–1M) est disponible mais **coûteux** : chaque token d'entrée est
  payé. Le RAG bien fait reste moins cher que « tout mettre dans le contexte ».
  REQ-MOD-004 (SHOULD) : plafonner le contexte servi à 32k tokens par défaut ; au-delà,
  passer par la synthèse hiérarchique ou le RAG.

## 4. Modes de déploiement — décision par phase

| Mode | Quand | Avantages | Inconvénients |
|---|---|---|---|
| **A. Serverless open-weight (par token)** chez un fournisseur UE | **Phase 1 et 2** | Zéro capex, élasticité, aucune ops GPU | €/token plus élevé à forte charge ; dépendance ; nécessite clause ZDR |
| **B. Endpoint dédié managé** (GPU réservés chez le fournisseur) | Phase 2–3, charge stable | Perf prévisible, prefix cache stable | Facturation à l'heure même à vide |
| **C. Auto-hébergement** (nos GPU, vLLM/SGLang) | Phase 3+, si seuil `04` §4 franchi ou contrainte de souveraineté absolue | Coût marginal le plus bas à forte utilisation ; contrôle total | Ops lourde (drivers, pannes, capacity planning), SRE 24/7 |

- **REQ-INF-001 (MUST)** : quel que soit le mode, l'interface reste celle du
  `model-gateway`. Le passage A→B→C ne doit avoir **aucun impact applicatif**.
- **REQ-INF-002 (MUST)** : contrat fournisseur avec **rétention zéro**, hébergement UE,
  et interdiction d'entraînement sur nos données (REQ-NFR-006/007). Sans ces clauses,
  le fournisseur est disqualifié, quel que soit son prix.
- **REQ-INF-014 (MUST)** : au-delà de la protection des données, le contrat fournisseur
  couvre : **SLA** de disponibilité et de latence avec pénalités ; **garanties de quota**
  (rate limits contractuels, procédure d'augmentation) ; **préavis sur les changements**
  de prix (≥ 60 j) et de modèle (dépréciation ≥ 90 j) ; **plan de réversibilité** (export,
  fin de contrat). Ces clauses sont vérifiées par le juridique avant qualification, au
  même titre que la ZDR. Le fallback (REQ-INF-004) protège techniquement ; ce contrat
  protège économiquement.

## 5. Routage et cascade — le principal levier de coût

`model-gateway` implémente une **cascade** :

```
requête → classifieur XS (coût ~0,00001 €)
        → estime: complexité, besoin d'outils, besoin de raisonnement
        → route vers S / M / L
        → si le modèle S produit une réponse dont la confiance (juge XS) < seuil
          → escalade vers M, puis L  (au plus une escalade par requête)
```

- REQ-INF-003 (MUST) : le classifieur de routage est lui-même évalué (`09`) ; sa matrice
  de confusion est suivie. Une erreur « L classé S » (sous-routage) est bien plus coûteuse
  en qualité qu'une erreur inverse en €. Optimiser le seuil sur cette asymétrie.
- REQ-INF-004 (MUST) : chaque classe de tâche a un modèle **par défaut** et un **fallback**
  chez un autre fournisseur, déclarés en config :

```yaml
# config/routing.yaml — source de vérité, versionnée
task_classes:
  chat_simple:
    primary:  { provider: prov_a, model: model_s, quant: fp8 }
    fallback: { provider: prov_b, model: model_s_alt }
    max_cost_eur_per_call: 0.002
  reasoning:
    primary:  { provider: prov_a, model: model_l }
    fallback: { provider: prov_b, model: model_l_alt }
    max_cost_eur_per_call: 0.05
```
- REQ-INF-005 (SHOULD) : *speculative decoding* (modèle brouillon XS + vérification par le
  modèle cible) en auto-hébergement — gain typique 1,5–2,5× sur la latence, sans perte de
  qualité (la sortie reste exactement celle du modèle cible).

## 6. Auto-hébergement — spécification technique (à activer en phase 3)

- REQ-INF-006 (MUST) : serveur = **vLLM** ou **SGLang**. Pas d'inférence « naïve »
  (`transformers.generate` en prod est interdit).
  *Veille (pas une option de prod à ce jour)* : **ZML** (Apache-2.0, Zig/MLIR) — stack
  d'inférence compilée visant le découplage matériel (NVIDIA/AMD/TPU/Trainium), alignée
  avec notre logique anti-lock-in mais un niveau plus bas. Critères d'entrée pour ouvrir
  un ADR : (a) support de nos classes de modèles M/L (MoE), (b) serveur OpenAI-compatible
  avec continuous batching **et** prefix caching, (c) un différentiel de coût matériel
  démontré (ex. AMD MI3xx à −30 % vs NVIDIA à débit égal), (d) maturité opérationnelle
  (releases, adoption). Revue au rituel `model-review` trimestriel. Grâce à REQ-ARC-006,
  une adoption future n'impacterait que ce composant.
- REQ-INF-007 (MUST) : activer *continuous batching*, *paged attention* et
  **automatic prefix caching**. Avec un system prompt + définitions d'outils longs et
  partagés, le prefix caching réduit massivement le coût du prefill (A-5 : > 70 % de hit
  attendu). C'est le premier réglage à vérifier, avant toute autre optimisation.
- REQ-INF-008 (MUST) : quantization **FP8** (poids + KV cache) par défaut ; INT4/AWQ
  uniquement si une eval démontre une perte < 1 point sur nos tâches.
- REQ-INF-009 (MUST) : parallélisme — tensor parallel intra-nœud, expert parallel pour les
  MoE ; ne pas franchir la frontière du nœud sans interconnect (NVLink/InfiniBand).
- REQ-INF-010 (MUST) : autoscaling sur la profondeur de file d'attente, **pas** sur le
  taux d'occupation GPU (qui est trompeur : un GPU peut être à 100 % en attente mémoire).
- REQ-INF-011 (SHOULD) : séparer les pools **interactif** (faible batch, latence) et
  **batch** (gros batch, spot instances, jusqu'à −70 % de coût, tolérant à l'éviction).
- REQ-INF-012 (MUST) : chargement des poids depuis un cache local/NVMe ou un registre
  d'artefacts interne — pas de téléchargement depuis Internet au démarrage du pod
  (temps de démarrage + risque de supply chain).
- REQ-INF-013 (MUST) : vérifier l'empreinte (checksum/signature) des poids ; les modèles
  téléchargés sont un vecteur de supply chain. Miroir interne obligatoire.

### Capacity planning — formules à utiliser (ne pas deviner)

```
VRAM ≈ poids_quantifiés + KV_cache + activations + overhead(~10%)

KV_cache_par_token ≈ 2 × n_layers × n_kv_heads × head_dim × bytes_par_élément
KV_cache_total     ≈ KV_cache_par_token × contexte_moyen × requêtes_concurrentes
```
Le KV cache, et non les poids, est ce qui limite la concurrence en pratique. Les modèles
récents réduisent son empreinte (attention parcimonieuse, fenêtres glissantes, GQA/MLA) :
c'est un **critère de sélection à part entière** pour l'auto-hébergement, souvent plus
déterminant que 2 points de benchmark.

## 7. Critères d'acceptation

- AC-INF-1 : benchmark de charge reproductible (script versionné) produisant TTFT, TPOT,
  débit, coût/1k req, pour chaque configuration candidate.
- AC-INF-2 : le taux de hit du prefix cache est exposé en métrique et > 60 % en prod.
- AC-INF-3 : bascule fournisseur testée et chronométrée < 1 h (REQ-NFR-009).
- AC-INF-4 : la cascade de routage réduit le coût/requête d'au moins 40 % vs « tout sur L »,
  à qualité d'eval ≥ 97 % du « tout sur L ».
