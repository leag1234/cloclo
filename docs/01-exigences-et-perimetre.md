# 01 — Exigences et périmètre

## 1. Contexte et hypothèses de charge

Hypothèses à **valider dans les 2 premières semaines** (elles pilotent toute la FinOps).
Tant qu'elles ne sont pas mesurées, elles sont marquées `ASSUMPTION` et ne doivent pas
servir de base à un engagement d'achat GPU.

| Id | Hypothèse | Valeur initiale | Méthode de validation |
|---|---|---|---|
| A-1 | Utilisateurs internes actifs (DAU) | 200 → 2 000 | Pilote 4 semaines |
| A-2 | Requêtes / utilisateur / jour | 25 | Télémétrie |
| A-3 | Tokens entrée / requête (avec RAG) | 6 000 | Télémétrie |
| A-4 | Tokens sortie / requête | 700 | Télémétrie |
| A-5 | Taux de réutilisation du préfixe (system + outils) | > 70 % | Métrique vLLM `prefix_cache_hit_rate` |
| A-6 | Pic / moyenne | 4× | Télémétrie |

Volume dérivé (200 DAU) : ≈ 5 000 req/j → **~34 Mtok entrée / 3,5 Mtok sortie par jour**.
À 2 000 DAU : ~340 Mtok entrée / 35 Mtok sortie par jour.
> Ce volume est **très en dessous** du seuil de rentabilité d'un cluster GPU dédié
> (cf. `04-finops.md` §4). Conséquence architecturale majeure : phase 1 = **inférence
> déléguée à un fournisseur d'open-weight à l'usage**, pas de GPU acheté.

## 2. Exigences fonctionnelles

| Id | Exigence | Niveau |
|---|---|---|
| REQ-FUN-001 | Conversation multi-tours avec streaming token par token. | MUST |
| REQ-FUN-002 | Appel d'outils (function calling) avec exécution serveur, parallélisable. | MUST |
| REQ-FUN-003 | RAG sur bases documentaires d'entreprise avec citations vérifiables (chaque affirmation sourcée pointe vers un `chunk_id` récupérable). | MUST |
| REQ-FUN-004 | Ingestion de fichiers (pdf, docx, xlsx, csv, images) et Q/R dessus. | MUST |
| REQ-FUN-005 | Exécution de code en sandbox isolée (analyse de données, génération de fichiers). | SHOULD |
| REQ-FUN-006 | Mémoire de conversation : résumé glissant + rappel de conversations passées. | SHOULD |
| REQ-FUN-007 | Espaces de travail / projets avec contexte partagé et ACL. | SHOULD |
| REQ-FUN-008 | Connecteurs métier (SharePoint/Drive, Jira, Confluence, base SQL) via MCP. | SHOULD |
| REQ-FUN-009 | Personnalisation d'assistants (system prompt + outils + corpus) par équipe. | SHOULD |
| REQ-FUN-010 | Multimodal image en entrée. | MAY (phase 3) |
| REQ-FUN-011 | Recherche web avec citations, en tant qu'outil contrôlé (allowlist/denylist de domaines par tenant, contenus traités comme non fiables, cf. `06` §2.3 et `07` §3). | SHOULD (phase 2) |
| REQ-FUN-012 | Export complet des données d'un tenant (conversations, documents, mémoires) dans un format ouvert et documenté (portabilité RGPD art. 20, réversibilité). | MUST |

## 3. Exigences non fonctionnelles

| Id | Exigence | Cible | Vérification |
|---|---|---|---|
| REQ-NFR-001 | TTFT (time-to-first-token) p95 | < 1,2 s | Charge synthétique en CI |
| REQ-NFR-002 | Débit inter-token p95 | > 25 tok/s | idem |
| REQ-NFR-003 | Disponibilité API mensuelle | 99,5 % (interne), 99,9 % (produit) | SLO, cf. `10` |
| REQ-NFR-004 | Taux d'erreur 5xx | < 0,5 % | SLO |
| REQ-NFR-005 | Coût unitaire | < 0,015 € / requête moyenne | Dashboard FinOps |
| REQ-NFR-006 | Aucune donnée entreprise ne quitte l'UE | 100 % | Contrôle contractuel + réseau |
| REQ-NFR-007 | Aucune donnée client utilisée pour entraîner un tiers | 100 % | Clause « zero data retention » |
| REQ-NFR-008 | RTO 4 h / RPO 15 min sur les données conversationnelles | — | Test de restauration trimestriel |
| REQ-NFR-009 | Basculement de fournisseur d'inférence | < 1 h, sans redéploiement applicatif | Test de bascule mensuel (game day) |
| REQ-NFR-010 | Traçabilité : toute réponse reconstructible (prompt, version modèle, outils, docs) | 100 % | Audit log |
| REQ-NFR-011 | **Multilinguisme à égalité de traitement** : qualité équivalente en FR, DE, ES, IT et EN (compréhension, génération, et traduction entre ces langues). Les évals (`09`) couvrent chaque langue et les scores sont rapportés **par langue** ; aucun modèle n'est retenu sur ses seuls scores anglais. L'efficacité du tokenizer dans les langues cibles (tokens/mot) entre dans le calcul de coût `04` (écart de 15–40 % possible entre langues et entre tokenizers). | Écart inter-langues ≤ 10 % sur les évals | Eval par langue + mesure tokens/mot |
| REQ-NFR-012 | Accessibilité de l'UI : conformité RGAA / WCAG 2.1 AA. | AA | Audit d'accessibilité avant GA |

## 4. Exigences de sécurité (résumé, détail en `07`)

| Id | Exigence | Niveau |
|---|---|---|
| REQ-SEC-001 | Filtrage entrée/sortie par classifieurs avant toute restitution utilisateur. | MUST |
| REQ-SEC-002 | Isolation stricte des données par tenant, y compris dans les index vectoriels. | MUST |
| REQ-SEC-003 | Défense contre l'injection de prompt indirecte via documents/outils. | MUST |
| REQ-SEC-004 | Sandbox d'exécution de code sans accès réseau sortant par défaut. | MUST |
| REQ-SEC-005 | Journal d'audit immuable, rétention 12 mois. | MUST |

## 5. Périmètre

**Dans le périmètre**
Passerelle modèle multi-fournisseur · orchestrateur agentique · RAG · outils/MCP ·
guardrails · API + UI · évals · observabilité · FinOps · post-training léger (SFT/DPO
sur adaptateurs LoRA) à partir de la phase 2.

**Hors périmètre**
Pré-entraînement · recherche fondamentale d'alignement · datacenter propre ·
génération d'images · voix (phase 4 au plus tôt).

## 6. Critères de succès du programme

- CS-1 : ≥ 60 % des utilisateurs cibles actifs à 30 jours après GA interne.
- CS-2 : score humain de satisfaction ≥ 4,0/5 sur un échantillon hebdomadaire de 100 conversations.
- CS-3 : suite d'évals internes ≥ 90 % du score du modèle propriétaire de référence sur les tâches métier prioritaires.
- CS-4 : coût unitaire conforme à REQ-NFR-005.
- CS-5 : zéro incident de fuite de données inter-tenant.
