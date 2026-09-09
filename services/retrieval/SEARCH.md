# Retrieval hybride — REQ-ENG-004/006/009, POC-F2/A3

`rank(question, chunks, gateway, k=8)` combine BM25 (k1=1.2, b=0.75)
et cosinus dense, fusion RRF (60), puis cross-encoder sur 32 candidats.
Les égalités sont départagées par chunk_id. Les labels d'évaluation ne sont
jamais chargés par le service. Les caractères CJK sont indexés individuellement.

Le gateway HTTP est la seule frontière modèle ; timeout 30 s, aucun retry,
limites de corps et validation stricte des cardinalités, identifiants, valeurs
finies et dimensions. Changer la révision impose une réingestion explicite.
Erreurs ValueError explicites ; aucun repli silencieux sur scores lexicaux.
Le log retrieved expose nombre de candidats/résultats, sans contenu des requêtes.

Index PoC parcouru en mémoire ; coût O(nombre de chunks), hors périmètre de
l'optimisation grande échelle. Aucun coût cloud ajouté. SLO final POC-P3 à
mesurer avec le pipeline complet ; cet incrément ne valide pas M2.
Tests : classement avec distracteurs, unicode, révision, entrées invalides,
erreurs HTTP/timeout et réponses fournisseur invalides. Mocks limités aux tests.

`make ingest` exige ATLAS_RETRIEVAL_DSN et un gateway démarré
(ATLAS_GATEWAY_URL, défaut http://127.0.0.1:8010). Markdown : front matter
avec doc_id/langue ; pdf/docx/html : fichier adjacent `<nom.ext>.json` avec
ces deux champs. Aucune source symlink n'est acceptée. Identifiants SHA-256
canoniques de source relative/empreinte/version de découpage/position.
L'ingestion prépare et valide tous les embeddings avant la transaction ;
un corpus vide est refusé pour prévenir une suppression accidentelle.

`services.retrieval.answer.answer` appelle /answer au gateway puis résout chaque
référence dans le Store. Toute citation inconnue, dupliquée, absente du texte,
hors des passages récupérés, ou modifiée depuis le retrieval est rejetée.
Les cassettes multilingues et le refus ont été enregistrés via le fournisseur réel.
