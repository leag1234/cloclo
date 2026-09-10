# Décision : NO-GO

Rapport généré depuis les évals et mesures archivées, sans valeurs simulées.
Sources : reports/bench.json.gz, reports/demo.json.gz ; évaluation et calibration : make eval (voir reports/M5.md).

| Critère | Mesure | Cible | Critère prouvé | Provenance / limite |
|---|---:|---|---|---|
| P1 | 0.2735169830120867 | < 2.0 | oui | TTFT p95, serverless, secondes |
| P2 | 124.14582000928351 | > 30.0 | oui | décodage p95, serverless, tok/s |
| P3 | 4.90906582500611 | < 12.0 | non | une requête live, secondes ; pas un p95 de charge |
| P4 | 3.572405473998515 | < 30.0 | non | une requête live, secondes ; pas un p95 de charge |
| P5 | 0.20360010414507257 | ≤ 0.2 | non | dégradation maximale moyenne, deux vagues de huit |
| P6 | 10 outils / 120 s / 0,05 EUR | tests des budgets durs | oui | make test-budgets enregistré |
| P7 | indisponible | > 0.5 | non | cache vLLM local ; aucun GPU M6 |
| P8 | indisponible | < 0.02 | non | GPU amorti absent ; moyenne serverless bench + démo, hors diagnostics : 0.00077778 EUR |
| P9 | indisponible | > 0.97 | non | uptime sur deux semaines, historique absent |

## Qualité

| Suite | Score normalisé |
|---|---:|
| E1 | 0.9750 |
| E2 | 0.9600 |
| E3 | 1.0000 |
| E4 | 0.9000 |
| E5 | 0.9429 |
| E6 | 0.8800 |
| E7 | 1.0000 |
| E8 | 1.0000 |
| E9 | 0.8400 |

Calibration croisée : κ=0.5288. GO qualité M5 : False.

Le micro-bench mesure le serverless, pas le GPU local. Les parcours RAG/web sont des observations unitaires, pas une distribution de charge. Les durées de rejeu CI ne sont pas des temps d'inférence.

Écarts conservés : citation E2-30 incorrecte, source web E6-004 périmée, terminologie E9-004 imprécise, écarts linguistiques. L'adaptateur RAG agentique tronque à 400 octets et peut masquer une réponse présente.

Actions avant GO : corriger ces écarts, mesurer le cache et le coût GPU amorti, effectuer une charge RAG/web représentative et collecter quatorze jours d'uptime. Décision humaine de phase 1 requise.
