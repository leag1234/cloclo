# 08 — Plateforme : API, multi-tenant, données, UI

## 1. API publique (contrat)

- REQ-API-001 (MUST) : spécification **OpenAPI 3.1** versionnée dans le dépôt, mergée
  **avant** toute implémentation. Les clients et les stubs serveur sont générés depuis
  elle. Un endpoint non spécifié n'existe pas.
- REQ-API-002 (MUST) : versionnage `/v1/…` ; changement cassant = nouvelle version majeure,
  avec période de dépréciation ≥ 6 mois et en-tête `Sunset`.
- REQ-API-003 (MUST) : streaming SSE avec des événements typés :
  `message_start`, `content_block_delta`, `tool_use`, `citation`, `usage`, `error`,
  `message_stop`. Le client doit pouvoir afficher un état intermédiaire (« recherche dans
  vos documents… », « exécution de l'outil X… ») — c'est un élément de qualité perçue, pas
  du cosmétique.
- REQ-API-004 (MUST) : idempotence sur les écritures via `Idempotency-Key`.
- REQ-API-005 (MUST) : erreurs normalisées (RFC 9457 `application/problem+json`) avec un
  `type` stable et actionnable, jamais de fuite d'interne (stack, nom de modèle,
  prompt système).
- REQ-API-006 (MUST) : compatibilité **OpenAI-like** pour l'endpoint de complétion brute,
  afin que les équipes internes branchent leurs outils existants sans adaptateur.

Surfaces :
```
POST /v1/conversations
POST /v1/conversations/{id}/messages        (SSE)
GET  /v1/conversations/{id}
POST /v1/files                              (upload → ingestion asynchrone)
GET  /v1/files/{id}/status
POST /v1/corpora/{id}/documents             (RAG entreprise)
POST /v1/assistants                         (config: prompt, outils, corpus, modèle-classe)
POST /v1/chat/completions                   (compat OpenAI, usage machine)
GET  /v1/usage                              (tokens, coût, par tenant/utilisateur)
```

## 2. Multi-tenant

- REQ-PLT-001 (MUST) : modèle **silo logique** : une base Postgres, isolation par
  `tenant_id` + Row Level Security **activée au niveau de la base**, pas seulement dans le
  code applicatif. La RLS est le dernier rempart quand une requête oublie un `WHERE`.
- REQ-PLT-002 (MUST) : les tenants sensibles peuvent exiger un silo **physique** (schéma ou
  instance dédiés). L'architecture doit le permettre sans réécriture (abstraction de la
  connexion par tenant dès le départ).
- REQ-PLT-003 (MUST) : quotas et rate-limits par tenant, par utilisateur et par clé API
  (token bucket) : requêtes/min, tokens/jour, € /mois, appels d'outils/jour.
- REQ-PLT-004 (MUST) : chaque tenant a sa configuration versionnée (assistants, corpus,
  outils autorisés, seuils de guards, modèle-classe autorisée).
- REQ-PLT-009 (MUST) : **cycle de vie du tenant** spécifié et outillé :
  *onboarding* (provisioning SSO — OIDC/SAML —, synchronisation des comptes via SCIM,
  configuration initiale, corpus) ; *offboarding* (gel → export → purge complète avec
  preuve, cf. REQ-PLT-008) ; *export/portabilité* (REQ-FUN-012) en format ouvert
  documenté (JSONL + fichiers sources), déclenchable en autonomie.
- REQ-PLT-010 (MUST) : **console d'administration** par tenant : gestion des utilisateurs
  et rôles, quotas et budgets, corpus et connecteurs, consultation de l'usage et des
  coûts, journal d'audit, déclenchement d'export. Les actions d'admin passent par la même
  API versionnée (pas de backdoor SQL) et sont journalisées dans `audit_log`.
- REQ-PLT-011 (SHOULD) : refacturation interne (chargeback) : les données de
  `usage_events` sont exportables par centre de coût.

## 3. Modèle de données (Postgres)

```
tenants(id, name, plan, config_version, data_residency)
users(id, tenant_id, external_id, role)
conversations(id, tenant_id, user_id, title, created_at, archived_at)
messages(id, conversation_id, role, content_blocks jsonb, created_at)
message_meta(message_id, model_id, model_version, prompt_version, policy_version,
             input_tokens, output_tokens, cached_tokens, cost_eur, latency_ms, trace_id)
tool_calls(id, message_id, tool_name, args jsonb, result_ref, status, duration_ms, cost_eur)
citations(message_id, chunk_id, doc_id, span, verified bool)
documents(id, tenant_id, source_uri, checksum, acl jsonb, version, indexed_at)
chunks(id, doc_id, tenant_id, ordinal, text, embedding vector, metadata jsonb)   -- RLS
memories(id, tenant_id, user_id, fact, source_message_id, visible bool, created_at)
audit_log(id, tenant_id, actor, action, subject, payload_hash, at)   -- append-only
usage_events(...)  -- alimente le dashboard FinOps
```

- REQ-PLT-005 (MUST) : `message_meta` capture **toutes** les versions (modèle, prompt,
  politique, corpus). Sans cela, aucune réponse passée n'est explicable, et REQ-NFR-010
  est impossible à satisfaire. C'est un choix à faire dès la première migration :
  l'ajouter après coup ne reconstruit pas l'historique.
- REQ-PLT-006 (MUST) : `audit_log` en append-only (droits SQL restreints, pas seulement
  une convention).
- REQ-PLT-007 (MUST) : chiffrement au repos, chiffrement en transit, secrets dans un
  coffre (Vault / KMS), rotation automatique.
- REQ-PLT-008 (MUST) : rétention configurable par tenant ; purge effective en cascade
  (messages → embeddings → caches → résumés de mémoire → sauvegardes selon politique).
  Écrire le job de purge **en même temps** que le schéma, pas un an plus tard.

## 4. Tests de sécurité des données (bloquants en CI)

- T-DATA-1 : RLS active — un test tente une requête sans `tenant_id` et **doit** échouer.
- T-DATA-2 : recherche vectorielle cross-tenant → 0 résultat.
- T-DATA-3 : purge → aucune trace résiduelle dans aucun store (vérification exhaustive
  scriptée sur tous les backends, y compris le cache).
- T-DATA-4 : les ACL documentaires sont respectées dans le retrieval (REQ-RAG-007).

## 5. UI (surface minimale de qualité)

- REQ-UI-001 (MUST) : streaming fluide, arrêt de génération, régénération, édition d'un
  message et rebranche de la conversation.
- REQ-UI-002 (MUST) : citations cliquables ouvrant le passage source surligné. C'est le
  premier levier de **confiance** en entreprise ; sans lui, l'adoption s'effondre.
- REQ-UI-003 (MUST) : affichage transparent des étapes agentiques (outils appelés,
  documents consultés), repliable.
- REQ-UI-004 (MUST) : feedback 👍/👎 + commentaire → alimente le jeu d'évals et le DPO (`05`).
- REQ-UI-005 (MUST) : mention claire du caractère IA de l'assistant et de la faillibilité
  des réponses (AI Act, REQ-CMP-005).
- REQ-UI-006 (SHOULD) : gestion des pièces jointes, projets/espaces, historique cherchable.

## 6. Critères d'acceptation

- AC-PLT-1 : OpenAPI mergée avant le code ; clients générés, pas écrits à la main.
- AC-PLT-2 : les 4 tests T-DATA passent, bloquants.
- AC-PLT-3 : `GET /v1/usage` reconcilie à ±2 % avec la facture du fournisseur.
- AC-PLT-4 : toute réponse en prod est reconstructible (prompt exact, versions, docs) depuis
  la base — vérifié par un test d'audit tiré au sort.
