# Index dérivé M2

POC-F2 ; REQ-ENG-002/004/005/007. Contrat SQL approuvé dans PR #8.
Le service retrieval est le seul propriétaire du schéma atlas_retrieval.

Installer requirements-dev.txt, fournir ATLAS_RETRIEVAL_DSN hors dépôt,
puis `python -m services.retrieval.store init` sur une base dédiée possédant
pgvector. `sync` lit une liste JSON de chunks sur stdin ; `read` restitue l'index.
Ne pas journaliser la sortie : elle contient les documents. Aucune donnée source
n'est supprimée. Le CLI est administratif, jamais exposé à l'utilisateur final.

Chaque sync remplace l'index entier dans une transaction : révision/dimension
uniformes, vecteurs finis non nuls, métadonnées cohérentes, contraintes SQL.
Un échec restaure l'index précédent. Les sources absentes sont supprimées.
Le remplacement complet privilégie la simplicité pour le petit corpus PoC ;
les identifiants stables conservent les citations lors d'une ingestion identique.
La résolution inconnue lève KeyError ; erreurs SQL et de validation explicites.

Retour arrière sur cette base dédiée : transaction `DROP SCHEMA atlas_retrieval
CASCADE`, puis init et réingestion. Ne pas supprimer l'extension partagée vector.
Migration aller/retour et rollback testés sur PostgreSQL/pgvector réel en conteneur
éphémère ; le nettoyage est enregistré avant l'initialisation des tests.
Le port de test est dynamique et lié uniquement à 127.0.0.1.

Dépendances : psycopg[binary] 3.3.5 (LGPL-3.0, pilote typé ; alternative psql
fragile pour transactions runtime), pydantic 2.13.5 (MIT, validation stricte ;
alternative validation manuelle plus difficile à auditer). Versions compatibles
avec Python 3.14 local et 3.12 CI. Aucun appel distant ni coût GPU.
Observabilité : événement index_synced avec cardinalités, sans documents.
SLO RAG et dashboard attendent l'intégration ; aucun résultat retrieval revendiqué.
