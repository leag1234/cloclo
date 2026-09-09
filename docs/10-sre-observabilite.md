# 10 — SRE, observabilité, exploitation

## 1. SLO et budget d'erreur

| SLI | SLO (interne) | SLO (produit) | Fenêtre |
|---|---|---|---|
| Disponibilité (`2xx+4xx` / total) | 99,5 % | 99,9 % | 30 j glissants |
| TTFT p95 | < 1,2 s | < 1,0 s | 30 j |
| TPOT p95 (inter-token) | > 25 tok/s | > 30 tok/s | 30 j |
| Taux d'échec de tâche agentique | < 5 % | < 3 % | 30 j |
| Fraîcheur de l'index RAG | < 15 min après modification de la source | idem | continu |

- REQ-SRE-001 (MUST) : budget d'erreur explicite. S'il est consommé, **le développement de
  nouvelles fonctionnalités s'arrête** au profit de la fiabilité. Règle écrite, appliquée.
- REQ-SRE-002 (MUST) : alertes basées sur les **symptômes** (SLO brûlé) et non sur les
  causes (CPU haut). Pas d'alerte non actionnable — chaque alerte a un runbook.

## 2. Télémétrie

- REQ-OBS-001 (MUST) : **OpenTelemetry** de bout en bout. Un `trace_id` unique traverse
  BFF → orchestrateur → gateway → fournisseur → outils. Chaque étape agentique est un span
  avec : modèle, tokens (entrée / sortie / cachés), coût, latence, décision de routage,
  résultat des guards.
- REQ-OBS-002 (MUST) : métriques minimales exposées :
  `llm_requests_total{tenant,task_class,model,provider,status}`,
  `llm_tokens_total{direction,cached}`, `llm_cost_eur_total{…}`,
  `llm_ttft_seconds`, `llm_tpot`, `prefix_cache_hit_ratio`,
  `tool_calls_total{tool,status}`, `guard_blocks_total{stage,category}`,
  `retrieval_latency_seconds`, `escalation_total`.
- REQ-OBS-003 (MUST) : **logs de prompts** — traités comme des données personnelles :
  chiffrés, accès restreint et journalisé, rétention limitée (30 j par défaut),
  redaction des PII. Un accès aux logs de prompts en production **doit** être motivé
  et tracé. C'est le fichier le plus sensible du système.
- REQ-OBS-004 (MUST) : échantillonnage : 100 % des traces en erreur, 100 % des blocages de
  guards, 1–5 % du trafic nominal (le reste en métriques agrégées).
- REQ-OBS-005 (MUST) : dashboards standard : Qualité (L6 de `09`), Coût (`04`), Fiabilité
  (SLO), Sécurité (guards, injections détectées).

## 3. Déploiement

- REQ-SRE-003 (MUST) : GitOps. Aucun `kubectl apply` manuel en prod. L'état désiré est
  dans Git ; la dérive est détectée et corrigée.
- REQ-SRE-004 (MUST) : déploiements progressifs (canary 5 % → 25 % → 100 %) avec analyse
  automatique et rollback automatique (cf. REQ-EVA-011).
- REQ-SRE-005 (MUST) : **feature flags** pour : modèle par classe de tâche, fournisseur,
  activation d'un outil, seuils de guards, activation du RAG. Ils constituent le
  kill switch (REQ-SEC-020) et permettent de réagir sans déploiement.
- REQ-SRE-006 (MUST) : migrations de base réversibles, testées sur une copie de prod.

## 4. Résilience

- REQ-SRE-007 (MUST) : *circuit breaker* par fournisseur ; sur ouverture → bascule sur le
  fallback, alerte, pas d'échec utilisateur.
- REQ-SRE-008 (MUST) : dégradation **gracieuse** en cascade, dans cet ordre :
  1. modèle L indisponible → M ;
  2. RAG indisponible → répondre sans documents **en le disant explicitement** ;
  3. outils indisponibles → répondre sans outils en le disant ;
  4. tout indisponible → message d'erreur honnête, pas une réponse inventée.
  Ne **jamais** dégrader silencieusement : une réponse sans RAG présentée comme fondée sur
  les documents est pire qu'une erreur.
- REQ-SRE-009 (MUST) : file d'attente + backpressure ; en surcharge, on met en file et on
  informe, on ne timeout pas sauvagement.
- REQ-SRE-010 (MUST) : sauvegardes chiffrées, restauration **testée** trimestriellement
  (RTO 4 h / RPO 15 min, REQ-NFR-008). Une sauvegarde non restaurée n'existe pas.

## 5. Runbooks (à écrire, un fichier par scénario)

| Id | Scénario | Déclencheur |
|---|---|---|
| RB-01 | Fournisseur d'inférence dégradé / indisponible | circuit breaker ouvert |
| RB-02 | Explosion des coûts (dérive du routage, boucle d'outils, prompt géant) | budget à 80 % avant terme |
| RB-03 | Chute du taux de hit du prefix cache | `prefix_cache_hit_ratio` < 40 % |
| RB-04 | Régression de qualité détectée en canary | rollback auto → analyse |
| RB-05 | Suspicion de fuite cross-tenant | **Sév 1** : coupure du tenant, gel des logs, cellule de crise |
| RB-06 | Injection de prompt réussie avec effet de bord | **Sév 1** : kill switch outils, révocation, audit |
| RB-07 | Index RAG corrompu ou périmé | ré-indexation, dégradation gracieuse en attendant |
| RB-08 | Modèle retiré par son éditeur / changement de licence | bascule fournisseur ou modèle, revue juridique |
| RB-09 | Vague de faux refus | ajustement des seuils par flag, cas d'eval ajoutés |

- REQ-SRE-011 (MUST) : chaque runbook contient : détection, impact, mitigation immédiate
  (< 5 min), correction, communication, et la référence de l'eval à ajouter après coup.
- REQ-SRE-012 (MUST) : **game days** mensuels — bascule de fournisseur, kill switch,
  restauration, RB-05 en simulation. Un runbook jamais joué est une fiction.

## 6. Post-mortem

- REQ-SRE-013 (MUST) : sans blâme, sous 5 jours ouvrés, avec cause racine, chronologie,
  actions correctives datées et **assignées**, et un cas d'eval créé (REQ-EVA-007).

## 7. Critères d'acceptation

- AC-SRE-1 : une trace unique permet de reconstituer une requête complète, coût inclus.
- AC-SRE-2 : les 9 runbooks existent ; ≥ 4 ont été joués en game day.
- AC-SRE-3 : rollback automatique déclenché avec succès lors d'un test provoqué.
- AC-SRE-4 : restauration testée et documentée dans les 3 derniers mois.
