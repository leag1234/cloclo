# PoC v2 — Banc d'essai crédible, souverain

> Objet : élargir le PoC v1 (fondation prouvée) en un **banc d'essai** qui ressemble
> assez à un assistant frontier pour évaluer honnêtement la qualité de fond avant
> tout investissement produit. **Ce n'est PAS le produit final** : l'UI reste basique,
> la robustesse multi-utilisateur, la sécurité durcie et le polish sont hors périmètre.
> Contrainte inchangée : **100 % souverain** (tout sur infrastructure Scaleway / GPU
> loué en UE ; aucun runtime propriétaire non-européen dans le chemin d'exécution).

## Principe directeur

**Approcher le comportement d'un frontier, jamais se défausser.** Chaque fois qu'une
capacité est raisonnablement attendue, le système la fournit au mieux plutôt que de
renvoyer un message d'erreur ou une excuse. Concrètement : on ne « tronque/rejette »
pas une grande entrée, on la **synthétise** ; on ne dit pas « je ne vois pas les
images », on les **analyse** ; etc. Un message d'échec n'est acceptable que pour une
impossibilité réelle (ressource indisponible, budget dépassé), jamais pour éviter un
travail attendu.

## Confidentialité des interactions (RÈGLE ABSOLUE)

Les journaux d'interaction (`BRAIN/interactions/*.jsonl`) contiennent des requêtes
réelles, potentiellement personnelles. Ils sont **strictement locaux à la VM** :
- jamais commités (déjà dans `.gitignore` ; à re-vérifier à chaque jalon) ;
- jamais résumés, cités, ni évoqués dans un fichier versionné, une PR, un rapport
  ou un message ;
- l'analyse d'observabilité produit des **métriques agrégées anonymes** (latences,
  taux d'échec, distribution de routage, types d'erreur) — jamais le contenu ni des
  extraits de requêtes.
Toute violation de cette règle est un incident de sécurité (arrêt immédiat).

## Jalons

### M8 — Modèle serverless (choix et configuration)
**Décision d'architecture (PoC v2)** : TOUT en serverless Scaleway Generative APIs.
Pas de GPU local pour l'inférence texte : à faible volume, le serverless est moins cher
(paiement au token, ~0,006 €/requête) et donne accès aux gros modèles que l'on ne peut
pas héberger soi-même. Le GPU n'est loué que PONCTUELLEMENT pour la génération d'images
(M13). L'auto-hébergement souverain est une décision de PRODUCTION à prendre après le
PoC, selon le volume (rentable au-delà de ~50M tokens/mois) et le niveau de qualité requis.
**Livrables** : configuration des modèles serverless : généraliste (qwen3.5-397b),
code (glm-5.2 ou qwen3-coder), vision (pixtral-12b), embeddings (qwen3-embedding-8b) ;
fenêtre de contexte et function-calling vérifiés ; le routeur M4 devient un routage
par TYPE de tâche (texte/code/vision) entre modèles serverless, plus une cascade
local/escalade. Le fallback M4 est conservé entre modèles serverless.
**Validation** : chaque type de tâche est servi par le modèle prévu ; function calling
et streaming fonctionnent sur le modèle principal ; coût par requête tracé.

### M9 — Mémoire + projets
**But** : contexte consolidé et partagé entre conversations (manque n°1 pour l'usage réel).
**Livrables** :
- notion de **projet** (regroupe conversations + documents ingérés + notes) ;
- **mémoire de conversation** persistée (l'assistant se souvient des échanges passés
  d'une même conversation et d'un même projet) ;
- **consolidation** : résumés/faits persistés par projet, injectés dans le contexte
  des requêtes du projet (via le RAG existant, étendu au contexte projet) ;
- UI : sélection de projet, mémoire visible/effaçable (basique, non soignée).
**Architecture (modèle Claude/ChatGPT), deux couches** :
- **Projet** : espace regroupant conversations + documents ingérés + instructions
  permanentes ; contexte documentaire partagé entre toutes les conversations du projet
  (extension du RAG M2 à un scope projet).
- **Mémoire de faits** : extraction AUTOMATIQUE de faits durables et saillants depuis
  les échanges (préférences, contexte de travail, décisions), stockés séparément,
  **éditables et effaçables par l'utilisateur**, réinjectés dans le contexte quand
  pertinents. PAS de résumé brut ni de réinjection de tout l'historique : des faits
  sélectionnés, comme le font Claude (memory) et ChatGPT (memory).
**Principe frontier** : le système exploite le contexte accumulé sans qu'on ait à tout
répéter ; il distingue clairement « ceci vient de ta mémoire » de « ceci vient d'une
source ». La mémoire est inspectable et corrigeable par l'utilisateur.
**Validation** : une info donnée dans une conversation d'un projet est réutilisée dans
une autre conversation du même projet ; l'effacement de la mémoire est effectif ;
isolation entre projets (pas de fuite de contexte d'un projet à l'autre).

### M10 — Grandes entrées gérées par synthèse
**But** : absorber les grandes entrées (pages web volumineuses, longs documents)
comme un frontier, par synthèse hiérarchique / retrieval, **jamais par troncature-excuse**.
**Livrables** :
- pour le contenu web : découpe en chunks + sélection des passages pertinents
  (retrieval sur le contenu fetché) OU résumé hiérarchique avant génération ;
- pour les longs documents : même logique ;
- gestion propre du plafond de contexte du modèle (REQ-MOD-004), avec un budget de
  synthèse borné.
**Principe frontier** : une requête sur un contenu volumineux produit une réponse utile
et sourcée, pas un message « contexte dépassé ».
**Validation** : une question sur une page web longue (qui faisait échouer le PoC v1)
produit une réponse correcte et sourcée, sous le budget temps/coût.

### M11 — Streaming + réflexion visible
**But** : réponses affichées au fur et à mesure ; trace de raisonnement pour les
réponses longues.
**Livrables** :
- l'adaptateur relaie le flux SSE token-par-token à l'UI (fin du « bloc après attente ») ;
- si le modèle expose une trace de raisonnement (reasoning_effort), l'afficher
  séparément quand pertinent, avec le surcoût tokens signalé/borné.
**Cible d'évaluation** : latence perçue fortement réduite ; ressenti proche d'un frontier.
**Validation** : les tokens s'affichent progressivement ; le budget par requête reste tenu.

### M12 — Description d'image (multimodal entrée)
**But** : le système voit et analyse les images envoyées.
**Livrables** : routage des requêtes contenant une image vers un modèle vision
souverain (pixtral-12b, Scaleway) ; intégration dans le gateway et l'UI (upload image).
**Principe frontier** : une image + une question produit une réponse pertinente sur
le contenu de l'image, pas « je ne traite pas les images ».
**Validation** : description correcte d'une image de test ; réponse à une question
portant sur son contenu.

### M13 — Génération d'image (local sur GPU, souverain)
**But** : produire des images à partir d'une description, **en local sur GPU**.
**Livrables** :
- sélection d'un modèle open-weight de génération d'images (Flux / SDXL) et de son
  serveur (diffusers/ComfyUI), hébergé sur le **GPU déjà loué** (partagé avec vLLM).
  Pour un banc d'essai à usage séquentiel (un seul utilisateur, pas de chat + image
  simultanés), le partage VRAM est acceptable : SDXL (~12 Go) cohabite avec le modèle
  texte sur un L40S 48 Go. **Modèle retenu : Flux** (qualité proche des références
  grand public). Comme Flux est lourd en VRAM, prévoir une **bascule séquentielle**
  sur le GPU partagé : décharger/mettre en veille le modèle texte pendant une
  génération d'image, puis recharger (acceptable en mono-utilisateur banc d'essai).
  GPU dédié réservé au produit. Le même GPU pourra porter un STT plus tard ;
- intégration : une requête de génération route vers ce service ; l'image revient
  dans l'UI ;
- garde-fous : budget GPU, extinction, pas de contenu illicite (filtre minimal).
**Contrainte** : 100 % local/souverain — aucun service de génération d'images externe.
**Validation** : une requête « génère une image de X » produit une image cohérente,
servie par le GPU local, sous budget.

## Organisation en deux phases

**Phase A — l'assistant** : M8 (serverless), M9 (mémoire/projets), M10 (synthèse),
M11 (streaming/raisonnement), M12 (vision), M13 (génération d'images).
→ **TEST INTERMÉDIAIRE** : l'utilisateur re-teste l'assistant complet ; analyse des
journaux d'interaction (métriques agrégées, jamais le contenu) ; corrections.

**Phase B — les intégrations** : M14 (client MCP), M15 (API OpenAI-compatible durcie).
→ Test final.

### M14 — Client MCP (agir sur les outils de l'entreprise)
**But** : l'assistant se connecte à des serveurs MCP (GitLab, WordPress, etc.) et peut
lire/agir dessus (lister/créer des issues, publier, rechercher…).
**Livrables** : client MCP dans le harness d'outils (extension de M3) ; configuration
des serveurs MCP autorisés ; les actions à effet de bord (créer, publier, modifier)
passent par une confirmation utilisateur ; journalisation des actions.
**Principe frontier** : l'assistant enchaîne lecture + action sur les outils comme un
collaborateur, avec confirmation avant tout effet de bord.
**Validation** : lecture d'une ressource GitLab via MCP ; création d'une issue après
confirmation ; refus d'une action non confirmée ; aucun secret MCP exposé.

### M15 — API OpenAI-compatible durcie (pour les développeurs)
**But** : exposer l'assistant comme fournisseur de modèle utilisable par Codex, Claude
Code et tout client OpenAI, afin que les développeurs le testent dans leurs outils.
**Livrables** : durcissement de l'adaptateur M7 : authentification par clé API,
multi-utilisateur (clés/quotas par dev), function-calling et streaming complets et
conformes, grande fenêtre de contexte (les outils de dev envoient des dépôts entiers),
modèle code par défaut. Documentation d'intégration Codex / Claude Code.
**Validation** : Codex ET Claude Code configurés sur l'API réalisent une tâche de code
de bout en bout ; une clé invalide est refusée ; quotas appliqués ; coût par clé tracé.

## Ce qui reste HORS périmètre (produit, plus tard)
UI soignée/ergonomique, reconnaissance vocale de qualité, multi-utilisateur de l'UI de chat,
authentification/HTTPS/exposition publique, haute disponibilité, sécurité durcie
production, observabilité SRE complète, calibration humaine du juge.

> Note STT (phase produit) : une brique de reconnaissance vocale offline temps-réel, déjà éprouvée sur /e/OS (repos publics), pourra être intégrée en phase produit sur le même GPU. Choix technique validé côté /e/OS : **Parakeet TDT (ONNX) via transcribe-rs**, streaming temps-réel, préféré à Whisper. Hors périmètre PoC v2.

## Méthode (inchangée depuis v1)
Specs d'abord ; l'agent implémente sous contrat + CI ; `verify-mN` testé en amont ;
jalons mergés via PR à CI verte ; auto-merge autorisé à CI verte ; contradictions
mineures tranchées en autonomie, sécurité/budget = arrêt. Logs d'interaction locaux
uniquement (règle ci-dessus).

M8 : le contrat `contracts/m8.md` précise le routage serverless. La politique dans
le gateway valide tarifs et capacités avant transport et réserve primaire + fallback
sous 0,05 EUR. Les fenêtres fournisseur sont bornées par ce budget applicatif ;
les identifiants alternatifs nécessitent une entrée de capacités et de prix validée.
Le chemin chat sans GPU utilise cette politique et un seul fallback dans le délai
initial. Le coût d'une tentative échouée sans usage reste réservé par le ledger ;
les logs du gateway distinguent coût mesuré et réserve inconnue. Les clients M4
explicitement locaux conservent leur comportement antérieur.
