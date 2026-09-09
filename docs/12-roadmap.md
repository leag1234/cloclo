# 12 — Roadmap, jalons et organisation

## 1. Séquencement — logique

L'ordre n'est pas négociable, et il est contre-intuitif : **on construit les évals et la
passerelle avant la première fonctionnalité visible.** Un système génératif sans mesure ne
s'améliore pas, il dérive. Toute inversion de cet ordre a un coût connu : refonte au
premier changement de modèle.

## 2. Phase 0 — Fondations (semaines 1–4)

| Livrable | Doc | Critère de sortie |
|---|---|---|
| Corpus de spec validé, ADR 001–008 actés | tous | Signés par archi + sécu + métier |
| Contrats OpenAPI + schémas mergés | `08` | Clients générés |
| `model-gateway` avec 2 fournisseurs qualifiés | `03` | AC-ARC-1 : bascule < 1 h prouvée |
| `eval-harness` + 50 premiers cas dorés | `09` | Tourne en CI, < 3 min |
| Charte v0.1 | `05` | Revue métier + juridique |
| Squelette CI/CD, IaC, observabilité | `10`, `11` | Pipeline complet vert |
| Validation juridique des licences des modèles retenus | `03` | Avis écrit |
| Mesure réelle des hypothèses A-1..A-6 | `01` | Modèle FinOps recalculé |

**Gate de sortie** : on peut échanger un modèle contre un autre en une PR de config, et
mesurer objectivement l'impact. Rien d'autre n'est requis.

## 3. Phase 1 — Pilote interne (semaines 5–12)

Périmètre : chat + RAG sur 2–3 corpus + 3–5 outils, 1 département pilote (~50 users).

| Livrable | Doc |
|---|---|
| Orchestrateur (machine à états, budgets, reprise) | `06` |
| RAG hybride + reranker + citations vérifiées | `06` |
| Guardrails IN/OUT (petits modèles auto-hébergés) | `07` |
| UI avec citations cliquables, feedback, transparence des étapes | `08` |
| Multi-tenant + RLS + tests de fuite | `08` |
| Dashboards qualité / coût / SLO | `04`, `10` |
| Jeu doré métier ≥ 300 cas, suite adversariale ≥ 200 cas | `09` |
| Red team #1, DPIA, classification AI Act | `07` |

**Gate de sortie (GA interne)** :
- G1–G7 de `09` §6 verts.
- Zéro fuite cross-tenant, zéro effet de bord par injection indirecte.
- €/requête ≤ budget ; TTFT p95 < 1,2 s.
- Satisfaction pilote ≥ 4,0/5 ; ≥ 60 % d'usage hebdomadaire.
- 4 runbooks joués en game day.

## 4. Phase 2 — Généralisation entreprise (mois 4–8)

| Livrable | Doc |
|---|---|
| Cascade de routage S→M→L + classifieur évalué | `03` |
| Auto-hébergement des **petits** modèles (embeddings, rerank, guards, routage) — le meilleur ROI infra | `04` §4 |
| Prefix caching optimisé, cache sémantique | `04` |
| Assistants par équipe, connecteurs MCP internes | `06` |
| Sandbox d'exécution de code | `06` |
| SFT/DPO sur adaptateurs LoRA (format, ton, tool-calling, anti-flagornerie) | `05` |
| Mémoire longue, projets/espaces | `06` |
| Red team #2 (externe) | `07` |

**Gate de sortie** : −40 % de coût/requête à qualité constante (AC-INF-4) ; suite d'évals
métier ≥ 90 % du modèle propriétaire de référence (CS-3) ; ≥ 60 % de DAU sur la cible.

## 5. Phase 3 — Optimisation et éventuel auto-hébergement (mois 9–15)

Déclenché **uniquement** si le calcul de `04` §4 est franchi avec des volumes réels.

| Livrable | Condition |
|---|---|
| Distillation d'un modèle L vers un S sur nos tâches | ROI ≥ 20 % démontré |
| Auto-hébergement du modèle principal (vLLM/SGLang, FP8, spec decoding) | U > 60 % soutenu **et** 1–2 ETP SRE/ML alloués |
| Pool batch sur spot | volume batch significatif |
| Multimodal (image en entrée) | demande métier validée |
| Extension multi-tenant externe / produit | décision business |

> Rappel : franchir ce seuil sans les ETP dédiés est le scénario d'échec le plus courant
> de ce type de projet. Le GPU n'est pas le coût ; l'exploitation l'est.

## 6. Équipe minimale

| Rôle | ETP | Rôle des agents IA |
|---|---|---|
| Tech lead / architecte | 1 | Rédige les specs et les AC, revoit tout ADR |
| Ingénieur ML (post-training, évals) | 1 | Pilote les évals et les fine-tunes |
| Ingénieur backend/plateforme | 1–2 | Encadre les agents sur services et contrats |
| SRE / infra | 0,5 → 1 | IaC, SLO, runbooks |
| Sécurité / conformité | 0,5 | Guards, DPIA, AI Act, red team |
| Product / métier | 0,5 | Jeux dorés, charte, adoption |
| **Agents d'implémentation** | — | Code sous spec (`11`), tests, migrations, outillage, docs |

Les agents produisent le volume ; les humains produisent **les spécifications, les
critères d'acceptation et les décisions**. Toute tentative d'inverser ce rapport
(« les agents décident, les humains relisent ») échoue : c'est le retour du vibe coding,
à plus grande échelle et plus vite.

## 6bis. Adoption et conduite du changement

Le critère CS-1 (≥ 60 % d'actifs à 30 jours) ne s'atteint pas par la qualité technique
seule. Prévoir, dès la phase 1 :
- **Champions** : 2–3 relais par département pilote, formés avant l'ouverture, qui
  remontent les cas d'usage et alimentent le jeu doré (`09` — c'est le même travail).
- **Formation** : sessions courtes orientées cas d'usage réels du département, pas
  « démo générale de l'IA » ; guide interne de prompting maintenu.
- **Boucle visible** : les retours 👍/👎 donnent lieu à un changelog utilisateur mensuel
  (« vous nous avez signalé X, c'est corrigé ») — c'est le levier d'adoption le moins
  cher qui existe.
- **Mesure honnête** : suivre aussi le *shadow IT* (usage persistant d'IA grand public
  malgré l'outil interne) : c'est l'indicateur d'échec le plus fiable, avant les sondages.
- REQ-ADO-001 (MUST) : un propriétaire produit est responsable de ces actions ; elles
  figurent au même plan que les livrables techniques dans les gates de phase.

## 7. Risques majeurs et mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| On sous-estime le post-training / le comportement et on livre un assistant « techniquement correct, humainement médiocre » | Adoption nulle | `05` dès la phase 0 (charte + évals de comportement) |
| Achat de GPU prématuré | Capex gaspillé, ETP immobilisés | ADR-001, seuil `04` §4, revue trimestrielle |
| Lock-in fournisseur malgré tout | Perte du bénéfice « open » | `model-gateway` + game day mensuel de bascule |
| Guards trop stricts → contournement par les utilisateurs (shadow IT vers une IA grand public) | Risque de fuite **pire** que le risque initial | Mesurer `refusal_precision` et `guard_false_positive` (`09` §5) |
| Le modèle de référence open-weight change tous les 2 mois | Instabilité | Le pipeline d'évals rend le changement de modèle routinier — c'est justement le but |
| Injection indirecte via documents d'entreprise | Sév 1 | REQ-SEC-015 : défense **architecturale**, pas seulement par prompt |
| Le fine-tuning dégrade l'alignement | Sév 1 | REQ-PT-011 : suite de sécurité rejouée après chaque fine-tune, bloquante |
| Explosion des coûts par contexte long | Budget | Budgets durs, plafond de contexte, RAG discipliné |

## 8. Rituels

- **Hebdo** : revue qualité (métriques L6), revue des incidents, triage des faux refus.
- **Mensuel** : `model-review` (le portefeuille de `03` a-t-il bougé ?), revue FinOps
  (le seuil de `04` §4 est-il franchi ?), game day.
- **Trimestriel** : décision d'auto-hébergement, test de restauration, revue des licences,
  ouverture du jeu gelé avant release majeure.
