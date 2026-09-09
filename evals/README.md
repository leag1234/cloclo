# Pack d'évals ATLAS-0 — jeu doré initial

Généré le 2026-07-23 par Claude (Anthropic) — famille de modèles **distincte** du système
testé (Qwen/GLM/DeepSeek) et du juge : l'indépendance de la mesure est préservée.

## Statuts et provenance (champ obligatoire sur chaque cas)

| `source` | Signification |
|---|---|
| `verifie-web` | Clé de correction vérifiée contre une source web à la date indiquée |
| `genere-a-valider` | Généré par Claude, **doit être validé humainement** avant de faire foi |
| `flores` | Issu de FLORES-200 (traductions professionnelles) via `tools/fetch_flores.py` |
| `incident` | Créé suite à un bug/incident (à alimenter en continu) |

| `statut` | `draft` → `valide` (par un humain, champ `valide_par` + date) |

**Règle : un cas `draft` tourne dans les rapports (à titre indicatif) mais ne compte
pas dans les seuils GO/NO-GO tant qu'il n'est pas `valide`.** Ta passe de validation
(~1 min/cas) consiste à passer chaque `draft` en `valide` ou à le corriger/rejeter.

## Contenu

```
golden/e4_tool_calling.yaml   20 cas — draft, validation rapide (assertions mécaniques)
golden/e6_web.yaml            20 cas — 2 vérifiés ce jour, 18 avec méthode de vérification
golden/e7_comportement.yaml   15 cas — draft
golden/e8_routage.yaml        30 cas — draft, validation = relire les étiquettes
golden/e9_traduction.yaml      5 cas d'amorce + FLORES à échantillonner (script fourni)
generation/KIT-E1-E2-E3.md    kit de génération des ~80 cas cœur sur VOS documents
tools/fetch_flores.py         échantillonne 20 paires FLORES-200 sur FR/DE/ES/IT/EN
```

## Ce qui manque et pourquoi

E1/E2/E3 (retrieval, RAG, refus) exigent **vos documents**. Deux voies :
1. Uploader 10–15 documents représentatifs (non confidentiels) à Claude → génération
   immédiate des cas, mêmes schémas, statut `genere-a-valider`.
2. Laisser l'agent d'implémentation exécuter `generation/KIT-E1-E2-E3.md` sur le corpus
   au jalon M2 — le kit impose le format, les quotas par langue et la checklist de
   validation humaine.

## Répartition linguistique du pack livré

E4 : FR 6 / DE 4 / ES 4 / IT 3 / EN 3 · E6 : 4 par langue · E7 : FR 4 / DE 3 / ES 3 /
IT 2 / EN 3 · E8 : 6 par langue · E9 : couvre les 10 directions principales via FLORES.
