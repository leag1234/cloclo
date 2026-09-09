# Contrats M0 — à revoir et merger avant implémentation

Source: MISSION.md M0 ; docs/11 R-02, REQ-ENG-002/004/009/011.

`edge-bff.openapi.json` définit GET /health : HTTP 200, JSON `{"status":"ok"}`.
Ce contrôle de vie ne dépend d'aucun fournisseur et ne promet aucune disponibilité
GPU. Le serveur écoutera par défaut sur 127.0.0.1:8080 ; BFF_URL reste utilisable
par le healthcheck existant. Les chemins inconnus retourneront HTTP 404.

Plan de la PR d'implémentation, après merge humain de ce contrat :
- serveur edge-bff minimal et squelettes des services prescrits par docs/11 ;
- scripts lint/typecheck/test bloquants, dépendances de développement justifiées ;
- eval-harness à vide, sans appel live, avec compte explicite de zéro cas ;
- tests de contrat et HTTP réel, chemins inconnus, arrêt du processus de test ;
- make verify-m0 local, PR, job ci vert, mise à jour BRAIN/ puis arrêt.

Tests d'acceptation prévus : conformité exacte du JSON au contrat, HTTP 200 réel
via le healthcheck protégé par verify-m0, HTTP 404 pour un chemin inconnu,
exécution à vide du harness et propagation des erreurs des outils de qualité.
Les nouveaux tests seront montrés en échec avant ajout du serveur.

Périmètre exclu : M1+, infra GPU, nouvelle UI, appels LLM, workflows et verify-*.
Coût cloud supplémentaire : 0 €/h. Aucune dépendance ajoutée par cette PR.
