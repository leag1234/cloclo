# 14 — Implémentation autonome par agent IA (« les clés du camion »)

> Objectif : que le PoC (`13`) se construise avec un minimum d'interventions humaines,
> par un agent de codage (Codex, OpenAI) disposant d'un accès réel à l'infrastructure.
> Ce document dit comment donner les clés **sans donner le camion entier**, et comment
> structurer le travail pour que l'autonomie fonctionne réellement — car l'autonomie ne
> vient pas de la confiance, elle vient de la **vérifiabilité**.

## 1. Le principe qui gouverne tout

Un agent ne doit jamais être son propre juge. La boucle qui rend l'autonomie fiable :

```
agent → commit → CI (tests + evals + lint) → vert ? → jalon suivant
                          └── rouge → l'agent corrige (il voit les logs CI)
```

**L'humain ne surveille pas le travail ; il définit les jalons et valide aux checkpoints.**
Tout ce qui suit sert à rendre cette boucle hermétique : si un critère de succès n'est
pas exécutable par une machine, l'agent ne peut pas savoir qu'il a fini, et l'autonomie
s'effondre en allers-retours.

## 2. Périmètre d'accès (donner les clés, pas le coffre)

| Accès | Portée exacte | Interdit |
|---|---|---|
| Cloud (Scaleway…) | **Un projet dédié PoC**, clé API IAM limitée à ce projet : créer/détruire instances GPU et volumes, lire la facturation | Accès à l'organisation, aux autres projets, aux moyens de paiement |
| Budget | Alerte 50/80 %, plafond projet si le fournisseur le permet | — |
| Serveurs | Clé SSH dédiée à l'agent (revocable indépendamment), utilisateur `agent` sudoteur sur la VM app et le nœud GPU | Aucune autre machine |
| Git | Dépôt PoC dédié, l'agent pousse des branches et ouvre des PR ; `main` protégée par la CI | Push direct sur `main` sans CI verte |
| Fournisseur serverless | Clé API avec **plafond de dépense** au niveau du compte | Clé sans plafond |
| Secrets | Injectés en variables d'environnement CI + `.env` chiffré (sops/age) ; jamais dans le code ni le contexte de l'agent quand évitable | Secrets en clair dans le dépôt ou les prompts |

- AUTO-1 (MUST) : toutes les clés sont créées **pour** l'agent et révocables en un geste.
  C'est ton kill switch : révoquer 3 clés arrête tout, proprement.
- AUTO-2 (MUST) : le compte cloud a une alerte budget indépendante de tout ce que
  l'agent contrôle. L'agent ne peut pas désactiver l'alarme.
- AUTO-3 (SHOULD) : cron d'extinction du GPU (POC-A2) posé **par toi** au niveau du
  fournisseur (scheduler d'instance), pas par l'agent — la facture reste bornée même si
  l'agent laisse tout allumé.

## 3. Préparer la mission (c'est 80 % du succès)

L'agent échoue rarement par manque de capacité ; il échoue par spécification ambiguë.
Avant de le lancer, le dépôt contient :

```
/docs/                    ← le corpus, dont 13-poc-spec.md
AGENTS.md                 ← instructions permanentes de l'agent (voir §3.1)
MISSION.md                ← les jalons M0→M6 avec leurs commandes de vérification
Makefile                  ← make dev / test / eval-smoke / eval / verify-mN / demo
.github/workflows/ci.yml  ← la CI, définie AVANT tout code applicatif
contracts/                ← les schémas d'API internes du PoC (même minimaux)
evals/golden/             ← le jeu doré initial (voir §5 — ta seule vraie contribution)
```

### 3.1 AGENTS.md — contenu imposé
Condensé opérationnel du doc `11`, adapté au PoC :
- lis `MISSION.md` et `docs/13-poc-spec.md` avant toute action ; en cas de conflit,
  `13` fait foi ;
- un jalon n'est terminé que si `make verify-mN` passe **sur la CI**, pas seulement en
  local ; ne modifie jamais un critère de vérification pour le faire passer — si un
  critère te semble faux, écris-le dans `BLOCKERS.md` et passe à autre chose ;
- état de session structuré (inspiré d'Antigravity, Apache-2.0, attribution en NOTICE) :
  `JOURNAL.md` (narratif : fait / décidé / bloqué), `STATUS.md` (état factuel courant :
  ressources cloud actives, jalon en cours, dernier run CI), `TASK.md` (la tâche en
  cours et son prochain pas concret). Mis à jour en fin de session ET avant toute
  opération risquée — c'est le protocole de cold-start de la session suivante ;
- **marqueurs d'observabilité obligatoires**, greppables dans les transcripts et le
  journal : `CONTRADICTION:` (docs/code en conflit découvert en cours de route),
  `RISK:` (la demande ou l'état du système présente un danger), `NOTICED BUT NOT
  TOUCHING:` (défaut repéré hors périmètre — noté, pas corrigé, cf. R-08),
  `ASSUMPTION:` (hypothèse prise faute d'information — jamais silencieuse),
  `Source:` (introduction d'une API/commande non encore utilisée, avec sa provenance).
  L'audit de conformité aux checkpoints = grep de ces marqueurs ;
- **ré-ancrage** : au début de chaque tâche et après toute compaction de contexte,
  relis la section « Règles absolues » de `docs/11` et `TASK.md` avant de continuer —
  les règles chargées en début de session se dégradent avec le remplissage du contexte ;
  si l'humain doit te rappeler une règle, c'est déjà un échec à consigner ;
- coûts : avant de créer une ressource cloud, écris son coût/h estimé dans le journal ;
  détruis toute ressource d'expérimentation en fin de session ;
- interdits : toucher aux workflows CI de vérification après M0 (fichier en CODEOWNERS),
  stocker un secret dans le dépôt, désactiver un test, dépasser le projet cloud dédié.
- anti-rationalisation : les excuses plausibles pour sauter une étape sont listées avec
  leur réfutation, et l'agent ne doit s'en autoriser aucune :

| Rationalisation | Réfutation |
|---|---|
| « Trop simple pour un test » | Les bugs vivent surtout dans le code "trop simple pour être testé" |
| « Je testerai à la fin du jalon » | Non vérifié = non fait ; la fin du jalon, c'est verify-mN, pas ta déclaration |
| « La CI est lente, je vérifie en local » | Le contrat est la CI (AUTO-4) ; le local est un brouillon |
| « C'est sûrement un problème d'environnement » | 3 tentatives max, puis BLOCKERS.md — pas une 4e |
| « J'en profite pour nettoyer ce fichier » | NOTICED BUT NOT TOUCHING: + périmètre strict (R-08) |
| « La doc dit X mais le code fait Y, je suis le code » | CONTRADICTION: obligatoire ; ne tranche pas seul |

### 3.2 MISSION.md — les jalons avec vérification exécutable

| Jalon | Livrable | `make verify-mN` vérifie (exécutable, binaire) |
|---|---|---|
| **M0** | CI + squelette + eval-harness vide mais fonctionnel | lint+tests verts sur CI ; `make eval-smoke` tourne (0 cas) ; secrets chargés ; hello-world déployé sur la VM app |
| **M1** | Nœud GPU reproductible + vLLM + gateway | script `infra/gpu-up.sh` crée le nœud de zéro ; `curl gateway /v1/models` OK ; bench TTFT/tok-s exécuté et archivé ; `infra/gpu-down.sh` détruit tout ; **re-création complète < 20 min** chronométrée |
| **M2** | Ingestion + RAG | corpus de test ingéré ; POC-E1 ≥ 0,85 ; citations résolvables (test automatique) |
| **M3** | Harness agentique + outils web | POC-E4 ≥ 90 % ; tests SSRF/robots.txt/budgets passent ; POC-E6 exécutable |
| **M4** | Cascade + UI branchée | POC-E8 ≥ 85 % ; fallback serverless testé (panne GPU simulée : `gpu-down` en plein trafic → l'UI répond encore) |
| **M5** | Suite d'évals complète + télémétrie | `make eval` complet < 20 min ; rapport HTML avec diff ; dashboard coût/latence alimenté |
| **M6** | Durcissement + bench final + rapport | POC-P1..P9 mesurés ; `make demo` déroule un scénario complet ; rapport GO/NO-GO généré avec les chiffres |

- AUTO-4 (MUST) : chaque `verify-mN` est un script du dépôt, écrit (ou validé) **avant**
  que l'agent commence le jalon. C'est le contrat. S'il n'est pas exécutable, le jalon
  n'est pas prêt à être délégué.
- AUTO-5 (MUST) : l'ordre M0→M1 n'est pas négociable : la CI et l'infra reproductible
  d'abord. Un agent qui code le harness avant d'avoir la boucle de vérification produit
  du code invérifiable — le mode d'échec n°1.

## 4. Dérouler : sessions et checkpoints humains

- Travail par **sessions d'un jalon** (pas « fais tout M0–M6 d'un trait ») : les très
  longues sessions autonomes dérivent ; la remise à zéro du contexte à chaque jalon,
  avec relecture de MISSION.md + JOURNAL.md, maintient la qualité.
- **4 checkpoints humains de ~20 minutes**, pas plus :
  1. après M1 : la facture et l'infra sont saines ? (lire le journal + la console cloud)
  2. après M3 : tester soi-même 10 requêtes web/RAG à la main — le ressenti humain
     détecte ce que les évals ratent encore ;
  3. après M5 : lire le rapport d'évals, calibrer le juge (POC-R2, 30 cas multilingues notés à la
     main — non délégable) ;
  4. après M6 : décision GO/NO-GO.
- Entre les checkpoints : zéro supervision requise. Le canal d'exception est
  `BLOCKERS.md` : l'agent y consigne ce qui le bloque et continue sur autre chose ;
  tu le lis quand tu veux.

## 5. Ce qui reste humain (le déléguer ferait échouer le PoC)

1. **Créer les comptes et les clés** (cloud, serverless) — par nature.
2. **Le jeu doré initial** : les 140 cas d'évals multilingues (FR/DE/ES/IT/EN), surtout E2/E6/E7/E9. Un agent peut en
   générer des brouillons, mais si le jeu de test est écrit par la même famille de
   modèles que celle qui est testée, la mesure ne vaut rien. Compte 1–2 jours de travail
   humain — c'est l'investissement au meilleur ROI de tout le PoC.
3. **La calibration du juge** (POC-R2).
4. **Les 10 requêtes à la main du checkpoint 2** et la décision GO/NO-GO.

## 6. Modes d'échec connus des agents en autonomie — et leur parade ici

| Mode d'échec | Parade dans ce dispositif |
|---|---|
| Déclarer « ça marche » sans preuve | Seule la CI fait foi (AUTO-4) ; le rapport de jalon cite le run CI |
| Affaiblir un test pour le faire passer | Workflows et `verify-*` en CODEOWNERS, modifiables uniquement par toi |
| Dérive de périmètre (« j'ai aussi ajouté… ») | §2 du doc 13 : extensions refusées par défaut ; revue du diff au checkpoint |
| Ressources cloud oubliées → facture | Cron d'extinction côté fournisseur (AUTO-3) + alerte budget indépendante (AUTO-2) + inventaire `infra/inventory.sh` exécuté en fin de session |
| Secrets qui fuient dans le code/logs | Scanner de secrets en CI (bloquant) dès M0 |
| Boucle sur un bug d'environnement | Règle des 3 tentatives dans AGENTS.md : après 3 échecs sur le même problème → BLOCKERS.md et on passe à autre chose |
| Contexte pollué sur longue durée | Sessions par jalon, redémarrage à contexte propre (§4) |

## 7. Résumé opérationnel — ta checklist de lancement (une demi-journée)

1. Créer le projet cloud dédié + clé IAM restreinte + alerte budget + scheduler
   d'extinction GPU. Créer la clé serverless plafonnée.
2. Créer le dépôt avec `docs/`, `AGENTS.md`, `MISSION.md`, `Makefile`, la CI, et les
   scripts `verify-m0..m6` (même simples).
3. Écrire/valider le jeu doré initial (le vrai travail).
4. Lancer l'agent sur M0. Revenir au checkpoint 1.

À partir de là, ton rôle est celui que le corpus assigne aux humains depuis le début :
définir les critères, valider aux jalons, trancher les ADR. Le reste roule tout seul —
précisément parce que rien de ce qui roule tout seul n'est invérifiable.
