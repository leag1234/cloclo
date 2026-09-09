# 04 — FinOps : modèle de coût, seuils, leviers

> Ce document contient la décision la plus structurante du projet : **quand (ne pas)
> acheter des GPU**. Les chiffres de prix sont des ordres de grandeur au T3 2026 et
> **DOIVENT** être re-sourcés par devis avant tout engagement. La *méthode*, elle, tient.

## 1. Principe

- **REQ-FIN-001 (MUST)** : le coût est une métrique produit, exposée au même titre que la
  latence. Tableau de bord : €/requête, €/utilisateur actif/mois, €/tenant, € par
  fonctionnalité.
- **REQ-FIN-002 (MUST)** : toute PR modifiant le chemin d'inférence déclare dans sa
  description l'impact estimé sur €/1 000 requêtes. La CI publie la mesure réelle depuis
  le benchmark de charge.
- **REQ-FIN-003 (MUST)** : budgets durs par tenant et global, avec coupe-circuit
  (arrêt gracieux + alerte) à 100 % du budget et alerte à 80 %.

## 2. Décomposition du coût unitaire

```
C_requête = C_prefill + C_decode + C_embedding + C_rerank + C_guardrails
            + C_outils + C_stockage + C_plateforme

C_prefill = (tokens_entrée × (1 - taux_hit_cache)) × prix_entrée_par_token
C_decode  = tokens_sortie × prix_sortie_par_token      # ~3 à 5× le prix d'entrée
```

Deux constats qui pilotent toutes les optimisations :
1. **Le prefill domine en RAG.** Avec 6 000 tokens d'entrée et 700 de sortie, l'entrée
   représente ~60–70 % du coût malgré son prix unitaire plus faible. → attaquer d'abord
   la taille du contexte et le cache de préfixe, pas la longueur des réponses.
2. **Les tokens de raisonnement (« thinking ») sont facturés en sortie.** Un modèle de
   raisonnement peut multiplier le coût par 5–10. → n'activer le mode raisonnement que
   sur les classes de tâches qui le justifient (REQ-INF-003).

## 3. Ordres de grandeur (à revalider par devis)

| Poste | Fourchette T3 2026 |
|---|---|
| Serverless open-weight, modèle S (~30B MoE) | ~0,05–0,20 € / Mtok entrée ; 0,20–0,60 € / Mtok sortie |
| Serverless open-weight, modèle L (~1T MoE) | ~0,40–1,00 € / Mtok entrée ; 1,50–3,00 € / Mtok sortie |
| GPU H100 80 Go à la demande | ~2,0–3,0 € / h |
| GPU H100 réservé 1 an | ~1,3–2,0 € / h |
| GPU spot / preemptible | −60 à −80 % vs à la demande |
| Nœud 8×H100 (auto-hébergement modèle L) | ~11 000–17 000 € / mois en réservé |

## 4. Seuil de bascule serverless → auto-hébergement (le calcul à faire)

```
Coût_selfhost_par_Mtok = (coût_horaire_nœud × 730) / (débit_tok_par_s × 3600 × 730 × U) × 1e6
                       = coût_horaire_nœud / (débit_tok_par_s × 3600 × U) × 1e6

  U = taux d'utilisation réel (fraction du temps où le GPU décode réellement)
```

**Exemple travaillé — modèle L sur un nœud 8×H100 :**
- Coût nœud : 15 € / h.
- Débit agrégé réaliste en régime batché : ~4 000 tokens de sortie / s (à mesurer !).
- À `U = 100 %` : 15 / (4 000 × 3 600) × 1e6 ≈ **1,04 € / Mtok sortie**.
- À `U = 30 %` (réalité d'un trafic interne aux heures ouvrées) : ≈ **3,5 € / Mtok**.
- Prix serverless comparable : 1,50–3,00 € / Mtok.

> **Conclusion (ADR-001).** L'auto-hébergement d'un modèle frontier n'est rentable
> qu'au-delà d'environ **60–70 % d'utilisation soutenue**, ce qui, avec nos hypothèses
> A-1 à A-6, exige un ordre de grandeur de **plusieurs milliards de tokens de sortie
> par mois** — soit ~10× notre volume à 2 000 DAU. **On n'achète pas de GPU en phase 1
> ni en phase 2.** On réévalue le calcul chaque trimestre avec les volumes réels.

Cas particuliers où l'auto-hébergement gagne malgré tout, et qu'il faut savoir identifier :
- Modèles **XS/S** utilisés à très haute fréquence (routage, guardrails, embeddings,
  reranking, classification) : ils tournent sur 1 GPU bon marché (L4/L40S), à taux
  d'utilisation élevé, et représentent un volume d'appels énorme. → **héberger ces
  modèles-là dès la phase 2** est souvent le meilleur ROI du projet.
- Traitements **batch** massifs (ingestion, ré-indexation, génération de données
  synthétiques) : GPU spot, U ≈ 100 %. → très rentable.
- Contrainte réglementaire absolue interdisant tout tiers.

## 5. Leviers de réduction, par ROI décroissant

| # | Levier | Gain typique | Effort | Exigence |
|---|---|---|---|---|
| 1 | **Prefix caching** (system prompt + outils + docs stables en tête de prompt) | −40 à −70 % sur le prefill | Faible | REQ-FIN-004 (MUST) |
| 2 | **Cascade de routage** S→M→L | −40 à −70 % global | Moyen | REQ-INF-003 |
| 3 | **Contexte discipliné** : RAG précis plutôt que contexte long ; élaguer l'historique par résumé | −30 à −50 % sur l'entrée | Moyen | REQ-FIN-005 (MUST) |
| 4 | **Cache exact + cache sémantique** des réponses | −10 à −30 % (dépend de la redondance des questions internes ; souvent élevée) | Faible | REQ-FIN-006 (SHOULD) |
| 5 | **Auto-héberger les petits modèles** (embeddings, rerank, guards, routage) | −60 à −90 % sur ces postes | Moyen | REQ-FIN-007 (SHOULD) |
| 6 | **Mode raisonnement sélectif** | −50 % sur les tâches où il était inutile | Faible | REQ-INF-003 |
| 7 | **Batch API / off-peak** pour l'asynchrone | −50 % | Faible | REQ-FIN-008 (SHOULD) |
| 8 | **Distillation** d'un modèle L vers un S sur nos tâches | −70 à −90 % sur les tâches couvertes | Élevé | phase 3, cf. `05` |
| 9 | Quantization FP8 (auto-hébergement) | −40 % VRAM, +débit | Faible | REQ-INF-008 |

- **REQ-FIN-004 (MUST)** : l'ordre des blocs du prompt est **stable et normalisé**
  (system → outils → politiques → documents → historique → message courant). Toute
  variation en tête de prompt détruit le cache de préfixe. Interdire l'injection de
  timestamps, d'UUID ou de contenus aléatoires en début de prompt — c'est l'erreur la
  plus fréquente et la plus coûteuse.
- **REQ-FIN-006** : le cache sémantique **NE DOIT PAS** être partagé entre tenants
  (fuite de données + réponses hors contexte). Clé de cache = `hash(tenant_id, corpus_version, prompt_normalisé)`.

## 6. Attention aux faux coûts « gratuits »

L'auto-hébergement déplace le coût plus qu'il ne le supprime :
ingénieurs SRE/ML d'astreinte, capacity planning, gestion des pannes GPU, mises à jour
de drivers, tests de charge, gestion des poids. Compter **1 à 2 ETP** dédiés dès qu'un
cluster GPU est en production 24/7. Ce coût dépasse souvent l'économie visée à notre
échelle — c'est la raison principale d'ADR-001, plus encore que le calcul de §4.

## 7. Critères d'acceptation

- AC-FIN-1 : dashboard € temps réel (coût par requête, tenant, classe de tâche, modèle).
- AC-FIN-2 : le taux de hit du prefix cache est > 60 % en prod, alerte si < 40 %.
- AC-FIN-3 : le coupe-circuit budgétaire est testé (test d'intégration, pas seulement en théorie).
- AC-FIN-4 : revue de coût mensuelle produisant une décision documentée sur le seuil §4.
