# retrieval

Responsable : `OWNERS`. Exigence : POC-F2, REQ-ENG-004/005/007.
Contrats : `contracts/m2.md`, `contracts/m2-implementation-plan.md`.

Premier incrément M2 : extraction locale et découpage, sans base ni inférence.
Commande : `python -m services.retrieval.extract corpus/01-rh-teletravail.md`
(remplacer par le chemin réel). JSON sur stdout ; événements structurés sur stderr,
sans texte documentaire. Ne pas exposer stdout dans des logs partagés.

Formats : PDF textuel (pas d'OCR), DOCX (paragraphes/tableaux dans l'ordre),
Markdown UTF-8 et HTML sans script/style/template. Aucun lien externe suivi.
Fichier <= 10 Mio ; texte <= 1 million de caractères ; DOCX décompressé <= 1 Mo.
Le CLI borne aussi l'espace mémoire à 512 Mio et le temps CPU à 15 secondes.
Les futurs appels d'ingestion doivent utiliser ce processus avec timeout mural,
pas appeler directement le parseur dans un serveur exposé à des documents non fiables.
Découpage déterministe par fenêtres de 2400 caractères, chevauchement 200.

Runbook : un document vide, chiffré, invalide ou trop grand est rejeté ; corriger
la source, ne pas ignorer l'erreur. Conserver le corpus original. Le découpage
n'est pas un index : persistance, métadonnées, embeddings et retrieval restent à livrer.
SLO provisoire du CLI : arrêt CPU <= 15 s ; aucun SLO RAG attesté avant pipeline.
Observabilité : événements `extracted` (format, caractères) et `extraction_failed`.
Dashboard : non déployé ; logs disponibles sur stderr pour cet outil ponctuel.
Coût cloud supplémentaire : 0 EUR/h, aucun GPU ou fournisseur distant.

Dépendances : pypdf (BSD-3-Clause, extraction PDF sans moteur bureautique),
python-docx (MIT, lecture OOXML avec lxml BSD), lxml-stubs (Apache-2.0, typage
uniquement). La stdlib ne décode pas le PDF ; LibreOffice est plus lourd.
Versions épinglées dans requirements-dev.txt pour la CI et cet incrément CLI.

## M2 — réponses et preuve
`make eval-retrieval` mesure E1 (recall et MRR par langue), puis génère trois
réponses FR/EN/DE depuis le retrieval et résout chaque chunk cité dans Postgres.
`ATLAS_RETRIEVAL_DSN` et `ATLAS_GATEWAY_URL` configurent ces commandes.
Une citation absente, inconnue, supprimée ou modifiée fait échouer l'évaluation.
Le rapport BRAIN/eval/retrieval.json est indicatif : les jeux métier ne sont pas
validés humainement et la fidélité sémantique E5 reste hors de ce gate.
Le gate M2 est exécuté par make test en CI, avec PostgreSQL éphémère et les vrais
moteurs CPU ; seul le fournisseur de génération est rejoué sous tests/.

M7 : `services.retrieval.api:app` expose POST /search et GET /sources/{chunk_id}
(contracts/m7.md). Seul ce service lit l'index. Le score publié est celui du
reranker utilisé pour le classement ; la résolution n'expose pas les embeddings.
