# 05 — Post-training, caractère et alignement

> C'est le poste que tout le monde sous-estime. Un modèle open-weight brut, même excellent
> en benchmark, ne « se comporte » pas comme un assistant de qualité : il flatte, il
> hallucine avec aplomb, il refuse mal, il perd le fil des outils, son ton est instable.
> **Le comportement ne se télécharge pas.** Il se construit.

## 1. Stratégie : trois niveaux, dans cet ordre

| Niveau | Coût | Délai | Quand |
|---|---|---|---|
| **N1 — Ingénierie de contexte** : charte + system prompt + politiques + few-shots + format | € | jours | **Toujours, en premier.** 80 % du bénéfice perçu. |
| **N2 — SFT / DPO sur adaptateurs LoRA** | €€ | semaines | Phase 2, quand N1 plafonne et que les évals le prouvent |
| **N3 — Distillation / RL sur tâches métier** | €€€€ | mois | Phase 3+, seulement avec un ROI chiffré |

- **REQ-PT-001 (MUST)** : on ne passe pas au niveau suivant sans une eval démontrant que
  le niveau courant a plafonné. « On va fine-tuner » n'est pas une réponse à un problème
  qu'on n'a pas mesuré.

## 2. N1 — La charte de comportement (l'artefact central)

Un document en langage naturel, versionné, qui définit ce qu'est l'assistant. Il est la
source unique dont dérivent : le system prompt de production, les jeux d'évals de
comportement, et plus tard les données de préférence pour le DPO.

- **REQ-PT-002 (MUST)** : `policies/charter/<semver>.md` contient, avec des exemples
  positifs **et négatifs** pour chaque point :
  1. **Honnêteté épistémique** : dire « je ne sais pas » ; ne jamais inventer de source,
     de chiffre ou de citation ; distinguer fait / inférence / opinion ; exprimer
     l'incertitude calibrée.
  2. **Anti-flagornerie** (sycophancy) : ne pas changer d'avis sous la seule pression
     sociale ; désaccord respectueux ; ne pas valider une prémisse fausse.
  3. **Format et concision** : structure par défaut, quand utiliser des listes, longueur
     cible selon le canal.
  4. **Ton** : direct, chaleureux, sans emphase creuse ; pas de préambule ni de flatterie.
  5. **Refus** : ce qui est refusé, comment (bref, sans sermon, avec alternative).
  6. **Utilisation des sources** : citer, ne jamais extrapoler au-delà du document,
     signaler les conflits entre sources.
  7. **Comportement agentique** : demander confirmation avant les actions irréversibles ;
     ne pas boucler ; signaler l'échec au lieu de le masquer.
- **REQ-PT-003 (MUST)** : chaque clause de la charte est reliée à ≥ 3 cas de test dans la
  suite d'évals comportementales (`09` §4). Une clause non testable est une clause à
  réécrire.
- **REQ-PT-004 (MUST)** : la charte est un artefact **produit** (revue par le métier, le
  juridique, la sécurité), pas un fichier de dev.

## 3. N1 — Ingénierie du system prompt

- REQ-PT-005 (MUST) : le system prompt est **compilé** depuis des blocs versionnés
  (charte → politiques → outils → contexte tenant), avec un ordre **stable** (impératif
  pour le prefix cache, REQ-FIN-004).
- REQ-PT-006 (MUST) : chaque modification du system prompt déclenche la suite d'évals
  complète. Un prompt est du code : revue, versionnage, rollback.
- REQ-PT-007 (SHOULD) : le prompt est **spécifique au modèle**. Un prompt optimisé pour
  un modèle L ne se transpose pas tel quel sur un S. La matrice `prompt × modèle` est
  évaluée, pas supposée.

## 4. N2 — Fine-tuning (phase 2)

**Ce qu'on fine-tune, et ce qu'on ne fine-tune pas.**

| Bon usage du fine-tuning | Mauvais usage |
|---|---|
| Format de sortie strict, jargon métier, style maison | Ajouter des connaissances factuelles (→ RAG) |
| Fiabilité du tool-calling sur **nos** outils | Corriger un prompt mal écrit |
| Distiller un gros modèle vers un petit (coût) | « Améliorer la qualité » sans cible mesurée |
| Réduire la verbosité / la flagornerie | Rattraper un modèle de base inadapté |

Pipeline :
1. **Collecte** : conversations de production (avec consentement et anonymisation),
   feedback 👍/👎, corrections d'experts, données synthétiques générées par un modèle L
   puis **filtrées par des humains**.
2. **Curation** : c'est 80 % du travail. Déduplication, filtrage qualité, équilibrage des
   catégories, retrait des PII. REQ-PT-008 (MUST) : chaque exemple d'entraînement porte
   une provenance traçable (`source`, `licence`, `validé_par`, `date`).
3. **SFT (LoRA/QLoRA)** : adaptateurs, pas de full fine-tune. Un adaptateur LoRA sur un
   modèle de 30–70B se pilote sur 1–2 GPU (QLoRA rend même le 70B accessible sur un
   24 Go). Coût : centaines d'euros, pas centaines de milliers.
4. **Préférences (DPO/ORPO)** : paires (préféré, rejeté) issues de la charte et du
   feedback. Plus efficace que le SFT seul contre la flagornerie et la verbosité.
5. **RLAIF / feedback par IA guidé par la charte** : un modèle juge, contraint par la
   charte, génère les préférences à grande échelle ; échantillon audité par des humains.
   REQ-PT-009 (MUST) : ≥ 5 % des préférences générées par IA sont vérifiées humainement,
   avec accord inter-annotateur mesuré (κ de Cohen ≥ 0,6).

**Garde-fous d'entraînement**
- REQ-PT-010 (MUST) : jeu de test **gelé** et jamais vu à l'entraînement ; toute
  contamination invalide le run.
- REQ-PT-011 (MUST) : mesurer la **régression** hors domaine (le fine-tuning dégrade
  fréquemment des capacités générales et — point de sécurité majeur — **affaiblit
  l'alignement du modèle de base**, même avec des données bénignes). La suite de sécurité
  (`07`) est rejouée après chaque fine-tune. Bloquant.
- REQ-PT-012 (MUST) : traçabilité complète du run (données, hyperparamètres, seed, code,
  hash des poids de sortie) dans le registre de modèles. Un modèle non reproductible ne
  va pas en prod.

## 5. N3 — Distillation (phase 3, piloté par le coût)

Objectif : remplacer un modèle L coûteux par un modèle S spécialisé sur nos 5 à 10 tâches
les plus fréquentes.
Méthode : le modèle L génère des traces (raisonnement + réponse) sur un large corpus de
requêtes réelles → filtrage par vérificateur automatique + juge → SFT du modèle S.
Critère de succès : **≥ 95 % du score du L sur nos évals, à ≤ 20 % du coût.** Si non
atteint, on abandonne — pas d'acharnement.

## 6. Registre de modèles

- REQ-PT-013 (MUST) : tout artefact modèle (base, adaptateur, quantifié) est enregistré
  avec : hash, licence, lignage (parent), évals passées, date, propriétaire, statut
  (`candidate` / `champion` / `deprecated`).
- REQ-PT-014 (MUST) : promotion en `champion` uniquement via le gate d'eval (`09` §6) et
  un déploiement progressif (canary 5 % → 25 % → 100 %) avec rollback automatique sur
  dégradation des métriques.

## 7. Critères d'acceptation

- AC-PT-1 : la charte existe, est versionnée, et chaque clause est couverte par ≥ 3 evals.
- AC-PT-2 : un run de fine-tuning est intégralement reproductible depuis le registre.
- AC-PT-3 : la suite de sécurité est rejouée automatiquement après chaque fine-tune (gate bloquant).
- AC-PT-4 : aucune donnée personnelle non anonymisée dans les jeux d'entraînement (contrôle automatisé).
