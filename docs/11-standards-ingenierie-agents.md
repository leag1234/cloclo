# 11 — Standards d'ingénierie pour agents implémenteurs

> **À lire intégralement par tout agent avant sa première ligne de code.**
> Ce document existe parce que le mode de défaillance dominant des agents de codage n'est
> pas l'incompétence : c'est **la production rapide de code plausible, non spécifié, non
> testé et non intégré**. Les règles ci-dessous sont conçues pour rendre ce mode de
> défaillance impossible, pas improbable.

## 1. Règles absolues (violation = PR rejetée automatiquement)

| # | Règle |
|---|---|
| R-01 | **Aucun code sans exigence.** Chaque PR référence ≥ 1 identifiant `REQ-*`. Pas de REQ → écrire d'abord la spec, ou ouvrir un ADR. |
| R-02 | **Contrat avant code.** Les schémas (OpenAPI, JSON Schema, SQL, protobuf) sont mergés et revus séparément, avant l'implémentation. |
| R-03 | **Test avant ou avec le code, jamais après.** Une PR sans test est une PR incomplète. Le test doit **échouer** sans le correctif (le prouver dans la description). |
| R-04 | **Interdiction de désactiver un test ou un lint** pour faire passer la CI. `@skip`, `# type: ignore`, `eslint-disable` exigent un lien vers un ticket et une date d'expiration. |
| R-05 | **Aucun nom de modèle, aucun prompt, aucun secret en dur** hors de `model-gateway` / `prompts/` / coffre. Vérifié par un grep en CI (AC-ARC-4). |
| R-06 | **Aucune dépendance nouvelle sans justification** dans la PR : pourquoi, alternatives, licence, taille, maintenance. Ajouter une bibliothèque est une décision d'architecture. |
| R-07 | **Pas de code mort, pas de code « au cas où ».** Ce qui n'est pas utilisé n'est pas mergé. |
| R-08 | **Périmètre strict.** Une PR = un objectif. Aucun refactoring opportuniste mélangé à une fonctionnalité. |
| R-09 | **Ne jamais inventer une API.** Si la signature d'une bibliothèque ou d'un endpoint est incertaine → la lire, ou l'exécuter. Une hypothèse non vérifiée est un bug livré. |
| R-10 | **Signaler le blocage.** Si une exigence est ambiguë, contradictoire ou impossible : **s'arrêter et le dire**. Ne pas deviner, ne pas produire une approximation silencieuse. Un blocage signalé coûte une heure ; une hypothèse fausse implémentée coûte une semaine. |
| R-11 | **Pas de simulation.** Aucun `mock`, `stub` ou donnée factice ne doit atteindre une branche exécutable en dev/staging/prod. Les mocks vivent dans les tests, uniquement. |
| R-12 | **Interdiction de « faire passer le test »** en modifiant l'assertion plutôt que le code. C'est un mode de défaillance connu des agents : il est traité comme une faute grave. |

## 2. Definition of Ready (une tâche n'est pas donnée à un agent sans cela)

Une tâche est prête si et seulement si elle contient :
- [ ] Les `REQ-*` couverts, et le doc de référence.
- [ ] Les contrats d'entrée/sortie (schémas), ou l'instruction explicite de les rédiger d'abord.
- [ ] Les **critères d'acceptation vérifiables** (`AC-*`), formulés comme des tests.
- [ ] Les fichiers/modules concernés, et ceux **interdits de modification**.
- [ ] Les cas limites connus et les modes d'échec attendus.
- [ ] Le budget (latence, coût, complexité) le cas échéant.
- [ ] Ce qui est **hors périmètre** de la tâche.

> Une tâche sans critères d'acceptation vérifiables ne doit pas être acceptée par l'agent.
> L'agent **doit** la renvoyer en demandant les AC. C'est une responsabilité, pas une option.

## 3. Definition of Done

- [ ] Tous les `AC-*` sont couverts par un test automatisé et passent.
- [ ] Tests unitaires + intégration ; couverture ≥ 80 % sur les lignes modifiées (la
      couverture globale n'est pas un objectif, la couverture du **diff** l'est).
- [ ] Cas limites testés : entrée vide, entrée géante, unicode, timeout, erreur du
      fournisseur, arguments d'outil invalides, contexte dépassé.
- [ ] Évals (`09`) passées ; gate vert.
- [ ] Observabilité ajoutée : spans, métriques, logs structurés pour tout nouveau chemin.
- [ ] Impact coût déclaré (REQ-FIN-002).
- [ ] Impact sécurité évalué ; nouveaux tests adversariaux si le chemin touche à une
      entrée non fiable.
- [ ] Documentation : le doc de référence concerné est **mis à jour dans la même PR**
      (la doc et le code divergent le jour où on les sépare).
- [ ] Migrations réversibles et testées.
- [ ] Pas de régression de latence > 10 % (mesurée, pas supposée).

## 4. Structure du dépôt (monorepo)

```
/contracts        # OpenAPI, JSON Schema, protobuf — source de vérité
/prompts          # artefacts versionnés (semver), testés
/policies         # charte, politiques de guards, seuils
/services
  /edge-bff       /orchestrator    /model-gateway
  /guardrails     /retrieval       /tool-runtime
/packages         # bibliothèques partagées (typées, sans I/O caché)
/evals            # jeux dorés, harness, jeu gelé (accès restreint)
/infra            # Terraform, Helm, ArgoCD
/runbooks
/docs             # ce corpus
/adr              # décisions d'architecture, numérotées, immuables
```

- REQ-ENG-001 (MUST) : un service = un `OWNERS`, un SLO, un runbook, un dashboard.
- REQ-ENG-002 (MUST) : dépendances **acycliques** entre services ; toute communication
  passe par un contrat publié. Pas d'accès à la base d'un autre service. Jamais.

## 5. Qualité du code

- REQ-ENG-003 (MUST) : typage strict obligatoire (Python : `mypy --strict` ou pyright
  strict, `pydantic` aux frontières ; TS : `strict: true`, pas de `any`). Un système
  agentique manipule des structures profondes et polymorphes : sans types, il devient
  indébogable en quelques semaines.
- REQ-ENG-004 (MUST) : les frontières valident leurs entrées à l'exécution (ne pas faire
  confiance au typage statique face à une réponse de LLM ou de fournisseur).
- REQ-ENG-005 (MUST) : erreurs typées et explicites ; interdiction du `except Exception:
  pass` et de l'avalement d'erreur. Une erreur silencieuse dans une boucle agentique
  produit une hallucination, pas un crash — c'est bien pire.
- REQ-ENG-006 (MUST) : fonctions pures pour la logique de décision (routage, budget,
  compaction) → testables sans réseau ni GPU. Les I/O sont injectées.
- REQ-ENG-007 (MUST) : déterminisme testable — toute non-déterminisme (LLM, horloge,
  aléa, uuid) passe par une interface injectable et est figée dans les tests.
- REQ-ENG-008 (MUST) : commits conventionnels, trunk-based, branches < 3 jours, PR < 400
  lignes de diff. Une PR de 2 000 lignes générée par un agent **n'est pas relisible** et
  sera rejetée sans lecture.

## 6. Tests — hiérarchie

| Type | Ce qu'il couvre | Réseau ? | Vitesse |
|---|---|---|---|
| Unitaire | logique pure, budgets, parsing, compaction | non | < 1 s |
| Contrat | conformité au schéma, compat ascendante | non | < 5 s |
| Intégration | service + base + dépendances (testcontainers) | local | < 60 s |
| LLM (enregistré) | rejeu de réponses de modèles **enregistrées** (cassettes) → déterministe | non | rapide |
| LLM (live) | appels réels, nightly, budget plafonné | oui | lent |
| Adversarial | `07` §8 | selon | — |
| Charge | `10` | oui | nightly |

- REQ-ENG-009 (MUST) : les tests de la CI par PR **ne dépendent pas** d'un appel LLM live
  (coût, flakiness). On utilise des cassettes enregistrées. Les évals live tournent en
  nightly et en gate de release.
- REQ-ENG-010 (MUST) : zéro test flaky toléré. Un test instable est corrigé ou supprimé
  sous 48 h — jamais « relancé ».

## 7. CI/CD — pipeline (bloquant dans cet ordre)

```
lint + format → typecheck → build → tests unitaires → tests de contrat
→ tests d'intégration → grep R-05 → SBOM + scan de vulnérabilités
→ scan de secrets → evals smoke (L0/L1) → evals sécurité (L4)
→ [merge] → staging → evals complètes (L2/L3/L5) → canary → prod
```

- REQ-ENG-011 (MUST) : la CI est **la** définition de la qualité. Ce qui n'est pas vérifié
  par la CI n'est pas une règle, c'est un vœu. Toute règle de ce corpus qui peut être
  automatisée **doit** l'être.

## 8. ADR

- REQ-ENG-012 (MUST) : toute décision structurante → un ADR (`/adr/NNNN-titre.md`) :
  contexte, options envisagées, décision, conséquences, statut. Les ADR sont **immuables** :
  on les remplace (`superseded by ADR-NNNN`), on ne les réécrit pas.
- REQ-ENG-013 (MUST) : un agent qui souhaite s'écarter d'un ADR **doit** ouvrir un ADR
  concurrent et attendre la décision humaine. Il ne contourne pas.

## 9. Protocole de travail des agents

1. **Lire** : `README.md` → le doc de référence de la tâche → les contrats concernés →
   le code existant du module. Ne pas commencer à écrire avant.
2. **Planifier** : produire un plan écrit (fichiers touchés, contrats, tests prévus,
   risques, questions ouvertes). Le plan est revu **avant** l'implémentation pour toute
   tâche non triviale.
3. **Poser les questions bloquantes maintenant**, pas à mi-parcours (R-10).
4. **Implémenter** par petits incréments vérifiables ; exécuter les tests à chaque étape.
5. **Vérifier soi-même** contre la Definition of Done, point par point, explicitement.
6. **Rapporter honnêtement** : ce qui marche, ce qui ne marche pas, ce qui n'a pas été
   testé, les hypothèses prises, la dette introduite. **Un rapport optimiste et faux est
   la faute la plus grave possible dans ce projet** : il détruit la capacité de l'équipe à
   faire confiance à l'ensemble du travail des agents, y compris le bon.

### Interdits comportementaux spécifiques
- Ne pas prétendre avoir exécuté un test qui ne l'a pas été.
- Ne pas « corriger » un test qui échoue en affaiblissant son assertion (R-12).
- Ne pas élargir le périmètre d'une tâche sans mandat (R-08).
- Ne pas supprimer du code qu'on ne comprend pas ; demander.
- Ne pas générer de commentaires qui paraphrasent le code ; commenter le **pourquoi**.
- Ne pas produire de fichier `*_v2`, `*_new`, `*_final`. On modifie, Git versionne.

### Marqueurs d'observabilité (adaptés d'Antigravity, Apache-2.0)
Les règles comportementales ne se testent pas unitairement ; elles s'auditent. Tout
agent **doit** émettre ces préfixes greppables dans ses journaux et rapports quand la
situation se présente : `CONTRADICTION:` (spec/code/docs en conflit), `RISK:` (demande
ou état dangereux), `NOTICED BUT NOT TOUCHING:` (défaut hors périmètre), `ASSUMPTION:`
(hypothèse prise, jamais silencieuse — cf. R-10), `Source:` (API/commande introduite,
avec provenance — cf. R-09). Un grep de ces marqueurs sur les transcripts fait partie
de la revue aux checkpoints ; leur **absence totale** sur une tâche non triviale est
elle-même un signal (aucune hypothèse, aucun conflit rencontré ? peu crédible).

## 10. Revue humaine — ce qui reste non délégable

- Charte de comportement et politiques de sécurité (`05`, `07`).
- Décisions d'architecture (ADR) et d'achat (GPU, fournisseurs).
- Contenu des jeux d'évals métier et du jeu gelé.
- Toute PR touchant : isolation des tenants, guardrails, gestion des secrets, migrations
  de données, budgets.
- Post-mortems.

> Le reste peut être largement automatisé. C'est précisément parce que ces cinq points
> restent humains que le reste peut l'être en sécurité.
