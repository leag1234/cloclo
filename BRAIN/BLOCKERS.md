
## 2026-09-09 — M0
- Contrat absent au bootstrap : PR https://github.com/leag1234/cloclo/pull/1
  préparée sur m0-contrats. Revue et merge humains requis avant code par docs/11 R-02.
- Lecture de la CI bloquée après trois tentatives : API actions/runs, commit
  check-runs et commit status renvoient toutes HTTP 403. Pas de quatrième essai.
  Donner au jeton de remplacement les droits de lecture Actions, Checks et statuts.
- Incident : jeton intégré au remote affiché dans une sortie outil. Le révoquer et
  le remplacer sans le transmettre dans la conversation. Aucun secret ajouté à Git.
- M0 non terminé ; make verify-m0 non exécuté, aucun run vert attesté.

## 2026-09-09 — prérequis confirmé à la reprise
L’API GitHub confirme que la PR #1 est ouverte et non mergée.
Le contrat et le plan sont prêts ; docs/11 R-02 impose leur revue et merge
séparés avant implémentation. Attente du merge humain ; aucun contournement.
Le blocage antérieur CI n’a pas été retenté. Aucun test M0 exécuté à la reprise.

## 2026-09-09 — actualisation après merge humain
- RÉSOLU : PR de contrat #1 mergée à 08:16:57 UTC, confirmé par GET pulls/1 ; les mentions antérieures de contrat non mergé sont historiques.
- RESTANT : trois HTTP 403 de lecture CI consignés précédemment ; aucun nouvel essai. Confirmer/rétablir les droits de lecture Actions, Checks et statuts du dépôt avant reprise.
- Révocation/remplacement du jeton exposé toujours non confirmés ; ne pas transmettre de secret dans la conversation.
- Arrêt propre ; M0 non terminé, aucune preuve CI verte.

## 2026-09-09 — nouvelle reprise, blocage inchangé
Aucune confirmation de résolution des trois HTTP 403 reçue. Aucun quatrième essai effectué. Confirmer le rétablissement des accès CI et le remplacement du jeton exposé sans communiquer de secret. M0 non terminé ; aucun test exécuté à cette reprise.

## 2026-09-09 — résolution humaine appliquée
RÉSOLU : accès Actions HTTP 200 confirmé à cette reprise.
Le jeton est assumé par l'humain dans HUMAN_ANSWER.md et ne bloque plus M0.
Les arrêts historiques ci-dessus ne décrivent plus l'état courant.

## 2026-09-09 — M1 : prérequis avant implémentation (R-02/R-10/AUTO-4)
- Contrat et plan proposés dans contracts/m1.md ; revue et merge humains requis.
- Gate protégé incomplet au regard de MISSION/docs/13 : vLLM direct, pas de
  TTFT/débit ni second cycle ; CI sans appel M1 ni credentials cloud.
  Le propriétaire doit valider la manière de prouver M1 réellement dans le job ci.
- Credentials cloud absents, aucun .env ; injecter hors dépôt les accès au projet
  dédié et attester budget/alarme/scheduler avant création. Aucun secret demandé ici.
Aucune tentative de provisionnement ; blocage de spécification, pas trois échecs
techniques. Aucun fichier protégé modifié, M1 non terminé.
