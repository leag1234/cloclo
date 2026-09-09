# Projet ATLAS — Plateforme LLM souveraine sur modèles open-weight

> Corpus de référence normatif. Ces documents font autorité sur le code.
> Tout écart doit passer par un ADR (voir `11-standards-ingenierie-agents.md`).

## 0. Objet

Construire une plateforme conversationnelle et agentique de qualité « frontier »
à partir de modèles **open-weight**, d'abord pour un usage **interne entreprise**,
puis extensible à un produit multi-tenant.

Contrainte structurante : **coût d'infrastructure minimal à qualité donnée**.
La décision par défaut est donc *ne pas héberger de GPU tant que la charge ne le
justifie pas* (cf. `04-finops.md`, seuil de bascule calculé).

## 1. Comment lire ce corpus

| Doc | Contenu | Public |
|---|---|---|
| `01-exigences-et-perimetre.md` | Exigences REQ-*, NFR, hors-périmètre | Tous |
| `02-architecture-cible.md` | Vue C4, composants, flux, contrats | Archi / agents |
| `03-modeles-et-inference.md` | Choix de modèles, serving, routage | Infra ML |
| `04-finops.md` | Modèle de coût, seuils, leviers | Archi / direction |
| `05-post-training-et-caractere.md` | SFT / DPO / charte, données | ML |
| `06-harness-agent-outils-rag.md` | Orchestrateur, tools, RAG, mémoire | Backend |
| `07-securite-et-conformite.md` | Guardrails, RGPD, AI Act, menaces | Sécu / juridique |
| `08-plateforme-api.md` | API, multi-tenant, quotas, données | Backend |
| `09-evaluation-qualite.md` | Evals, gates CI, régression | ML / QA |
| `10-sre-observabilite.md` | SLO, télémétrie, runbooks | SRE |
| `11-standards-ingenierie-agents.md` | Règles pour les agents implémenteurs | **À lire en premier par tout agent** |
| `12-roadmap.md` | Phases, jalons, critères de sortie | Direction |
| `13-poc-spec.md` | PoC ATLAS-0 : périmètre, cibles, validation auto, infra louée | Tous / agents |
| `14-implementation-autonome.md` | Playbook « clés du camion » : accès, jalons, checkpoints | Humain pilote + agents |

## 2. Conventions normatives (RFC 2119)

- **MUST / DOIT** : bloquant. Une PR qui viole un MUST est rejetée par la CI ou la revue.
- **SHOULD / DEVRAIT** : par défaut ; un écart exige une justification écrite dans la PR.
- **MAY / PEUT** : latitude d'implémentation.

Chaque exigence porte un identifiant stable `REQ-<DOMAINE>-<n>`. Le code, les tests
et les tickets **DOIVENT** référencer l'identifiant (`// covers: REQ-INF-004`).

## 3. Principes directeurs

1. **Contracts first.** Aucun code avant que le contrat (OpenAPI / JSON Schema /
   protobuf) ne soit mergé. Les agents génèrent le code *depuis* le contrat.
2. **Le modèle est remplaçable.** Aucun composant hors de la couche `model-gateway`
   ne connaît le nom d'un modèle. Un changement de fournisseur = changement de config.
3. **Coût = fonction de première classe.** Toute PR touchant le chemin d'inférence
   déclare son impact `€/1k requêtes` (cf. `04-finops.md`).
4. **Rien ne part en prod sans eval.** Le gate de qualité (`09`) est bloquant.
5. **Déterminisme et reproductibilité.** Seeds, versions épinglées, artefacts immuables.
6. **Le plus dur n'est pas le serving, c'est le comportement.** Budget et attention
   à répartir en conséquence : ~20 % infra, ~50 % harness + évals, ~30 % post-training.

## 4. Anti-objectifs explicites

- Ne pas pré-entraîner de modèle de base. Jamais.
- Ne pas construire un framework d'agents maison générique. On assemble.
- Ne pas viser la parité multimodale complète en phase 1.
- Ne pas optimiser la latence avant d'avoir un SLO mesuré et violé.
