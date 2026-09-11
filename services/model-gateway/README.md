# model-gateway

Responsable : `OWNERS`.

M1 (REQ-INF-012/013) : moteur de provisionnement `python3 infra/gpu.py up/down`.
Paramètres : projet/zone Scaleway, LOCAL_MODEL, GPU_CLIENT_IP, GPU_MAX_EUR_H.
SLO, runbook et dashboard : non applicables avant activation du service
au jalon correspondant dans MISSION.md.

M2 / POC-F2-A3, REQ-ENG-004/007 : `python services/model-gateway/http_gateway.py`
sert /embeddings et /rerank sur 127.0.0.1:8010 (schéma M2 approuvé).
Installer requirements-dev.txt ; premier lancement télécharge les poids épinglés,
ensuite cache local. CPU seulement, safetensors, aucun code distant autorisé.
Moteurs : embeddings multilingues 384 dimensions et cross-encoder (Apache-2.0).
Dépendances : sentence-transformers 6.0.1 (Apache-2.0), torch CPU 2.14.0 (BSD),
plusieurs Go avec poids ; alternative ONNX plus légère, intégration distincte.
Runbook : garder loopback, client timeout 30 s ; erreurs 400/413/502/504 explicites.
Les entrées longues subissent la troncature des tokenizers (128/512 tokens).
Logs embeddings/rerank : cardinalité et durée, aucun texte ; coût cloud ajouté nul.
SLO RAG/dashboard non attestés avant intégration ; /answer reste à implémenter.

## Génération M2
POST /answer suit contracts/m2-gateway.schema.json. Configuration injectée :
SCW_GENERATIVE_BASE_URL (HTTPS), SCW_GENERATIVE_API_KEY, ESCALATION_MODEL.
Le modèle L Scaleway reçoit des sources délimitées comme données non fiables,
avec prompts/rag.txt versionné. Délai fournisseur 25 s, 1024 tokens maximum,
reasoning_effort none, aucun retry automatique. Les références numériques du
modèle sont résolues vers les chunk_id fournis ; absence/invention est rejetée.
HTTP 400 entrée invalide, 413 contexte dépassé, 502 fournisseur/citation invalide,
504 timeout. Logs sans texte ni clé : durée et nombre de citations.
SLO opérationnel : réponse ou erreur bornée au délai fournisseur ; la cible
RAG <12 s sera mesurée au jalon performance. Plafond serverless confirmé dans
MISSION ; aucun GPU créé, facturation à l'usage et non horaire.
Source: https://www.scaleway.com/en/docs/generative-apis/api-cli/using-chat-api/
Source: https://www.scaleway.com/en/docs/generative-apis/reference-content/supported-models/

## Cascade M4
POST /agent/complete route les tâches simples vers LOCAL_MODEL / LOCAL_API_BASE
(produit par infra/gpu-up.sh dans BRAIN/gateway.env). Sans endpoint local,
la bascule Scaleway prend le relais ; aucun GPU nécessaire au gate M4.
Contrat : contracts/m4.md. Logs routing : classe, fournisseur, fallback ; sans texte.
Runbook : injecter les variables M3 et locales, lancer le gateway puis le harness.
Une panne locale consomme au plus 2 s avant L, dans la deadline M3. Prix L réservé
avant appel ; erreurs L restent explicites. SLO de qualité locale à mesurer en M6.
`make test-fallback` rejoue une réponse Scaleway enregistrée après panne locale
réelle ; `make eval-routing` écrit BRAIN/eval/routing.json. UI bonus non livrée.

M7 : /agent/complete accepte local_enabled=false pour une escalade directe sans
sonde GPU. observe=true ajoute provider (local/escalade) et route (simple/complexe)
à la réponse. Les anciens clients conservent leur format et leur cascade M4.

M12 : `/vision/complete` valide les images avec `packages/images.py`, réserve le
budget avant inférence et utilise `vision.yaml` pour le modèle souverain et son
tarif. Le transport n'effectue ni recherche d'URL image ni fallback texte.

M15 : dev_gateway prépare une requête code immuable et réserve octets UTF8 +512 et maximum sortant sous50000microEUR. Transport TLS unique, sans redirection ni reprise ; SSE borné2Mo et usage terminal obligatoire. Les tests rejouent de vrais deltas Scaleway (métadonnées fournisseur retirées), sans dépendance SDK externe.
