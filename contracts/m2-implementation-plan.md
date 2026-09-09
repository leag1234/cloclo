# M2 — complément concret au contrat intégré sur main

Source: contracts/m2.md, POC-F2/A3, REQ-ENG-002/004/009/011,
REQ-FIN-002 ; docs/11 R-02, R-06 et §9.2.

Le commit humain 736b421 a intégré le contrat général. Les questions E1 sont
désormais présentes ; aucune régénération des clés E1/E2/E3 n'est prévue.
Cette proposition complète les frontières techniques avant leur implémentation.

## Frontières à revoir

`m2-storage.sql` décrit l'index dérivé Postgres/pgvector, exclusivement détenu
par retrieval. Les métadonnées sont résolues par jointure document/chunk.
Une transaction remplace les chunks d'un document modifié ; une erreur conserve
l'ancien index. Une source supprimée disparaît lors d'une synchronisation complète.
Les identifiants sont SHA-256 d'un encodage JSON canonique de la source relative,
son empreinte, la version du découpage et la position. Aucun chemin absolu ni URL
externe fourni par un document n'est suivi. Refus des liens symboliques sortants.

`m2-gateway.schema.json` définit les corps JSON des trois opérations internes.
Succès HTTP 200 ; erreurs 400 invalid_input, 413 context_exceeded,
502 provider_error/invalid_citation, 504 timeout. Aucun détail fournisseur ou
secret dans l'erreur. Délai client borné à 30 secondes, aucun retry implicite.
Le gateway reçoit au maximum 128 000 caractères cumulés par requête.
Les chaînes composées uniquement d'espaces sont refusées à la frontière.

Embeddings : ordre et cardinalité de sortie égaux à l'entrée ; dimensions
constantes, valeurs finies, vecteurs non nuls. La révision opaque invalide
l'index lorsqu'elle change ; les noms de modèles restent dans model-gateway.
Reranking : un score fini par passage fourni, aucun identifiant ajouté ou omis.
Génération : chaque citation appartient aux passages fournis ; refus sans citation
si les sources sont insuffisantes. Les prompts seront versionnés sous prompts/.
Ces invariants relationnels complètent les contraintes JSON Schema.

## Incréments et tests prévus

Chaque PR d'implémentation restera sous 400 lignes de diff ; subdivision si
nécessaire. Les merges restent humains. Aucun gate ne sera présenté comme une
preuve M2 avant exécution effective du pipeline complet.

1. Extraction pdf/docx/md/html et découpage déterministe avec limites explicites
   (10 Mo par fichier, 1 million de caractères extraits), Unicode, pages vides,
   archives corrompues et décompression excessive. Tests rouges avant code.
2. Persistance : aller/retour exact, idempotence, remplacement, suppression,
   rollback sur échec et réversibilité du schéma sur une base de test isolée.
3. Gateway CPU pour embeddings multilingues et cross-encoder. Contrats testés
   contre les vrais moteurs locaux ; injection des erreurs dans les tests seuls.
4. Retrieval BM25 + cosinus dense, fusion RRF puis cross-encoder ; top-k unique
   et stable, k de 1 à 8. Tester distracteurs et absence d'accès aux clés E1.
5. Génération et résolution ; tests sur cassettes réellement enregistrées,
   timeout, erreur fournisseur, citation inventée et dépassement de contexte.
   Aucun appel LLM live dans la CI de PR, aucune cassette dans le runtime.
6. Évaluation : recall/MRR par langue, résolution effective des citations,
   rapport conforme au schéma existant. `make test` appellera le gate M2 en CI
   avec garde anti-récursion. Workflows et verify-* resteront inchangés.

Tests de chaque incrément puis couverture du diff >= 80 %, mesure de latence,
logs structurés sans contenu documentaire, runbook et SLO documentés.
Enfin `make verify-m2` local puis job `ci` GitHub, mise à jour BRAIN/ et arrêt.

## Dépendances proposées, à décider avant installation

- psycopg (LGPL-3.0, quelques Mo) pour Postgres ; psycopg2 moins adapté au
  typage moderne, sous-processus psql trop fragile pour les transactions runtime.
- pypdf (BSD-3-Clause, quelques Mo) et python-docx (MIT, avec lxml de plusieurs
  Mo) pour formats binaires ; stdlib insuffisante, LibreOffice bien plus lourd.
- pydantic (MIT, quelques Mo) pour validation des frontières et types stricts ;
  validation manuelle plus difficile à auditer. JSON Schema pour tests de contrat.
- sentence-transformers (Apache-2.0) pour embeddings/cross-encoder CPU ; coût
  disque dominant : PyTorch et poids, potentiellement plusieurs Go. Alternative
  ONNX plus légère à mesurer, API distante incompatible avec CI reproductible.
  Versions, licences des poids et tailles exactes à vérifier avant choix final.

RISK: la limite CI de 20 minutes inclut téléchargement et inférence CPU ; mesurer
le chemin froid, ne pas remplacer les moteurs par des scores factices.
RISK: aucune cassette de génération enregistrée n'est présente. L'enregistrement
nécessite un moteur réel et, si serverless, un plafond de dépense confirmé avant
appel facturé. Cette préparation ne déclenche aucun appel ni provisionnement.
CONTRADICTION: gate MISSION 0,70 versus cible docs/13 0,85 ; conserver le gate
protégé et mesurer aussi la cible 0,85. Ne pas annoncer un GO qualité sur un draft.
NOTICED BUT NOT TOUCHING: PR M1 #6 encore ouverte ; elle rapporte une preuve
locale, non réexécutée dans M2. Aucun GPU ne sera créé pour ce jalon.

Coût additionnel de cette préparation : 0 EUR/h. Aucun package installé.
Validation de cette PR : syntaxe JSON et diff ; pas de validation runtime SQL,
pas de mesure retrieval et pas de preuve M2. Revue préalable requise par R-02.
