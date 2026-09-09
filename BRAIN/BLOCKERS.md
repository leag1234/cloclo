
## 2026-09-09 — M0
- Contrat absent au bootstrap : PR https://github.com/leag1234/cloclo/pull/1
  préparée sur m0-contrats. Revue et merge humains requis avant code par docs/11 R-02.
- Lecture de la CI bloquée après trois tentatives : API actions/runs, commit
  check-runs et commit status renvoient toutes HTTP 403. Pas de quatrième essai.
  Donner au jeton de remplacement les droits de lecture Actions, Checks et statuts.
- Incident : jeton intégré au remote affiché dans une sortie outil. Le révoquer et
  le remplacer sans le transmettre dans la conversation. Aucun secret ajouté à Git.
- M0 non terminé ; make verify-m0 non exécuté, aucun run vert attesté.
