# STATUS
- M1 non terminé : moteur/tests PR #5 ouvert, intégration complète préparée sur m1-gpu-cycle (base m1-gpu-core).
- Cycle réel local réussi le 2026-09-09 : make verify-m1, 378 s ; bench m1-20260909T104731Z.json : 64 tokens, 1,97 s, 32,5 tok/s.
- Dernier run CI vérifié : https://github.com/leag1234/cloclo/actions/runs/34342197303 ; job ci success, commit 3ec1570 (moteur/tests uniquement).
- PR https://github.com/leag1234/cloclo/pull/5 non mergée ; seconde PR d'intégration en attente du merge humain conformément au plan (<400 lignes par PR).
- Inventaire final API toutes zones du projet : aucun GPU ; gpu-down explicite exécuté après le nettoyage du vérificateur.
- Préexistants conservés : VM CPU BASIC3-X4C-16G fr-par-2, disque système 50 Go et IP ; coût CPU non établi.
- Ressource M1 conservée selon contrat : atlas-weights 200 Go, disponible/détaché, environ 0,026 EUR/h HT ; aucun autre disque/IP expérimental restant.
- Coût actif pendant essai L40S : environ 1,511316 EUR/h HT ; coût additionnel courant : 0,026 EUR/h HT (poids).
- Budget/alertes/extinction autorisés dans MISSION ; aucune confirmation supplémentaire nécessaire.
