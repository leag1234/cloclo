# Kit de génération E1/E2/E3 — les ~80 cas cœur sur VOS documents

À exécuter par un agent (idéalement d'une famille de modèles ≠ Qwen/GLM/DeepSeek) au
jalon M2, sur 10–15 documents représentatifs du corpus PoC. Sortie : trois fichiers YAML
au format ci-dessous, statut `genere-a-valider`. **Aucun cas ne passe `valide` sans une
relecture humaine** (checklist en fin de document, ~1 min/cas).

## Quotas

| Suite | Cas | Répartition |
|---|---|---|
| E1 retrieval | 40 | ≥ 6 par langue ; ≥ 8 cas **cross-lingues** (question dans une langue ≠ langue du document) ; ≥ 5 cas « multi-documents » (la réponse exige 2 sources) |
| E2 RAG bout-en-bout | 30 | ≥ 5 par langue ; mélange factuel simple / synthèse / comparaison |
| E3 refus honnête | 10 | 2 par langue ; questions **plausibles** mais sans réponse dans le corpus |

## Prompt de génération (à adapter, un document à la fois)

```
Tu génères des cas d'évaluation pour un système RAG. Voici un document du corpus :

<document id="{doc_id}" lang="{lang}">
{contenu}
</document>

Génère {n} cas au format YAML ci-dessous. Règles STRICTES :
1. La réponse attendue doit être INTÉGRALEMENT contenue dans le document — cite le
   passage exact (champ `passage_source`). Si tu ne peux pas coller le passage, ne
   génère pas le cas.
2. Varie la difficulté : 40 % lecture directe, 40 % reformulation/synthèse d'une
   section, 20 % nécessitant de croiser deux passages du document.
3. Les questions doivent ressembler à ce qu'un employé demanderait réellement
   (naturelles, parfois imprécises), pas à des questions d'examen.
4. {k} questions doivent être posées dans une AUTRE langue que celle du document
   (indique `lang` de la question).
5. N'utilise AUCUNE connaissance externe au document.

Format:
- id: E1-XXX
  lang: <langue de la question>
  doc_lang: {lang}
  source: genere-a-valider
  statut: draft
  input: "<question>"
  attendu:
    doc_id: {doc_id}
    passage_source: "<citation exacte du document>"
    doit_contenir: ["<élément clé 1>", "<élément clé 2>"]
```

Pour **E3**, prompt inversé : « génère des questions qu'un employé pourrait
naturellement poser sur ce thème mais dont la réponse NE FIGURE PAS dans le document
ni, à ta connaissance, dans les autres documents listés : {liste des titres} ».
Attendu : `"signale l'absence d'information ; zéro invention"`.

## Checklist de validation humaine (par cas, ~1 minute)

- [ ] La question est naturelle (un collègue pourrait la poser telle quelle).
- [ ] Le `passage_source` existe bien dans le document et suffit à répondre.
- [ ] Les `doit_contenir` sont les bons éléments discriminants (ni trop vagues — un
      faux positif passerait — ni trop verbeux — une bonne réponse reformulée échouerait).
- [ ] Pour E3 : j'ai vérifié que la réponse n'est vraiment nulle part dans le corpus.
- [ ] Passer `statut: valide` + `valide_par: <nom>` + `date_validation`.

## Pièges connus à rejeter pendant la validation

- Questions qui recopient la formulation exacte du document (retrieval trivial —
  n'importe quel BM25 réussit ; ça ne mesure rien).
- Réponses attendues qui dépendent d'une interprétation (les évals veulent du binaire).
- Cas E3 « trop faciles » (question absurde) : le refus doit être testé sur des
  questions crédibles.
- Sur-représentation d'un seul document (max 5 cas par document).
