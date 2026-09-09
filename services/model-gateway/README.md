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
