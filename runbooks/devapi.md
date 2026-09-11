# API développeurs M15

REQ-DEV-001..005 ; contrat `contracts/m15.md`. `make serve-devapi` écoute sur
127.0.0.1:8030, accessible par tunnel SSH8030. Aucun GPU. Les clients n'ont accès
ni aux conversations, ni au RAG, ni aux outils MCP du chat privé8020.

Administrer les clés localement, avec la même variable ATLAS_DEVAPI_DB que le serveur
(défaut BRAIN/devapi/usage.sqlite) :

```sh
python -m services.orchestrator.dev_auth create alice --key-file /chemin/prive/alice.key --daily-requests 20 --daily-micro-eur 50000
python -m services.orchestrator.dev_auth revoke alice
```

Le fichier de remise est créé exclusivement en0600 ; aucune clé sur stdout. Le
transmettre par canal privé. Conserver SQLite entre les démarrages : réservations
inconnues et quotas quotidiens UTC persistent. GET /v1/usage expose seulement le
compteur de la clé authentifiée. Ne pas supprimer la base pour réinitialiser un quota.

Alias public `atlas-code`, rôle code du gateway ; une tentative par requête,
0,05EUR maximum réservé AVANT l'appel. Les octets UTF8 et le maximum sortant sont
majorés : la capacité financière peut être inférieure à la fenêtre du fournisseur.
Le cas validé contient24 616octets de code utile. Réduire explicitement contexte ou
max_tokens si400 ; aucune troncature silencieuse. Quota quotidien insuffisant429,
clé absente/invalide/révoquée401, erreur fournisseur502. Après annulation/usage
absent, la réserve reste débitée ; un coût fournisseur connu la remplace.

Chat Completions, Responses et Messages acceptent texte et fonctions exécutées
par le client. Pas d'images/audio, outils hébergés, previous_response_id ou stockage
Responses. Les options non prises en charge sont refusées. Les métadonnées/cache
n'accordent ni identité ni garantie de cache. Messages fonctionne sans thinking.
Les sorties tronquées restent length/incomplete/max_tokens ; ne pas exécuter un
appel tronqué comme une fonction complète. Journaux : identifiants, tokens/coût,
durée ; aucun contenu ni credential.

Profil Codex0.153.4 : clé ATLAS_API_KEY chargée depuis le fichier privé dans
l'environnement du client, base du tunnel. Fragment de configuration :

```toml
model = "atlas-code"
model_provider = "atlas"
model_reasoning_effort = "none"
model_reasoning_summary = "none"
model_instructions_file = "/chemin/atlas/prompts/dev-client-system.txt"
web_search = "disabled"
[model_providers.atlas]
name = "Atlas"
base_url = "http://127.0.0.1:8030/v1"
env_key = "ATLAS_API_KEY"
wire_api = "responses"
[features]
enable_request_compression = false
multi_agent = false
goals = false
remote_plugin = false
```

Le profil court borne les instructions initiales ; le contexte d'un dépôt entier
peut dépasser le budget. Conserver les protections d'exécution habituelles du client.
Source: [configuration Codex](https://learn.chatgpt.com/docs/config-file/config-advanced).

Profil Claude Code2.1.268 : ANTHROPIC_BASE_URL=http://127.0.0.1:8030,
ANTHROPIC_API_KEY issue de sa propre clé privée, CLAUDE_CODE_DISABLE_THINKING=1,
CLAUDE_CODE_MAX_OUTPUT_TOKENS=512, CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 et
CLAUDE_CODE_ATTRIBUTION_HEADER=0. Commande `claude --bare --model atlas-code --tools Bash
--allowedTools Bash --system-prompt "$(cat prompts/dev-client-system.txt)" -p "tâche"`.
Ce pont vers un modèle non-Claude est expérimental et non pris en charge par le
fournisseur du client ; pas de promesse de compatibilité avec les versions futures.
Source: [protocole gateway](https://code.claude.com/docs/en/llm-gateway-protocol).

`make verify-m15` exécute le rejeu HTTP sans secret puis, si la clé Scaleway est
présente, un vrai aller-retour fonction/résultat et le grand contexte. Chaque clé
de test live a un plafond50000microEUR. Preuves locales BRAIN/eval/devapi*.json ;
la CI par PR ne consomme aucune inférence. Les clients natifs sont testés séparément
sur des dossiers synthétiques, avec assertions externes sur le fichier généré.
