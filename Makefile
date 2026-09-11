# ATLAS-0 — cibles standard. Les verify-* sont la définition de « terminé ».
# scripts/verify-*.sh sont PROTÉGÉS (CODEOWNERS) : l'agent ne les édite pas.
.DEFAULT_GOAL := help
SHELL := /usr/bin/env bash

help: ## liste les cibles
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	 | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n",$$1,$$2}'

# --- dev ---
lint: ## lint + format check
	@bash scripts/lint.sh
typecheck: ## typage strict
	@bash scripts/typecheck.sh
test: ## tests unitaires + contrat + intégration (sans LLM live)
	@bash scripts/test.sh
scan-secrets: ## détection de secrets
	@bash scripts/scan_secrets.sh

# --- évals ---
eval-smoke: ## sous-ensemble rapide (<3 min), utilisé en CI par PR
	@bash scripts/eval.sh --smoke
eval: ## suite complète (<20 min), rapport HTML + diff + par langue
	@bash scripts/eval.sh --full

# --- démo ---
demo: ## déroule un scénario complet RAG+web+escalade
	@bash scripts/demo.sh

# --- jalons (chacun appelle son script protégé) ---
verify-m0: ## cadre vérifiable
	@PYTHONPATH=services/edge-bff python3 scripts/verify_m0.py
verify-m1: ## infra GPU reproductible + gateway
	@bash scripts/verify-m1.sh
verify-m2: ## ingestion + RAG
	@bash scripts/verify-m2.sh
verify-m3: ## harness + outils web
	@bash scripts/verify-m3.sh
verify-m4: ## cascade + UI + escalade
	@bash scripts/verify-m4.sh
verify-m5: ## évals complètes + télémétrie
	@bash scripts/verify-m5.sh
verify-m6: ## durcissement + bench + rapport
	@bash scripts/verify-m6.sh

.PHONY: help lint typecheck test scan-secrets eval-smoke eval demo \
        verify-m0 verify-m1 verify-m2 verify-m3 verify-m4 verify-m5 verify-m6

.PHONY: ingest
ingest: ## ingérer le corpus via gateway dans Postgres/pgvector
	@python3 -m services.retrieval.pipeline

.PHONY: eval-retrieval
eval-retrieval: ## évaluer E1 et résoudre les citations de réponses générées
	@python3 -m services.retrieval.evaluate

.PHONY: test-web-security test-budgets eval-tools eval-web
test-web-security: ## contrôles SSRF, robots, corps HTTP et plafonds
	@PYTHONPATH=.:tests python3 -m unittest test_web_security test_web_transport test_tool_runtime test_budgets.BudgetTests.test_fetch_limit -v
test-budgets: ## quatre budgets durs et arrêt des appels en cours
	@PYTHONPATH=.:tests python3 -m unittest test_budgets -v
eval-tools: ## E4 réel avec erreurs injectées exclusivement dans le harness de test
	@PYTHONPATH=.:tests:services/model-gateway python3 tests/agent_gate_eval.py tools
eval-web: ## E6 bout en bout ; qualité soumise aux clés et au juge humains
	@PYTHONPATH=.:tests:services/model-gateway python3 tests/agent_gate_eval.py web

.PHONY: eval-routing test-fallback
eval-routing: ## E8 : matrice de confusion et sous-routage critique
	@PYTHONPATH=services/model-gateway python3 tests/routing_eval.py
test-fallback: ## endpoint local fermé puis replay de la réponse Scaleway enregistrée
	@PYTHONPATH=services/model-gateway:tests python3 -m unittest test_cascade -v

.PHONY: report bench
report: ## rapport GO/NO-GO depuis les mesures archivées
	@python3 -m evals.decision
bench: ## micro-bench serverless borné, sans GPU
	@PYTHONPATH=.:tests:services/model-gateway python3 tests/m6_bench.py

.PHONY: serve test-ui verify-m7
serve: ## UI locale, gateway CPU, retrieval et adaptateur ; GPU désactivé par défaut
	@bash scripts/serve.sh
test-ui: ## requête HTTP intégrée avec citation et journal, fournisseur enregistré
	@PYTHONPATH=.:tests:services/model-gateway python3 tests/ui_gate.py 2>&1
verify-m7: ## vérificateur protégé UI et interactions
	@bash scripts/ui_gate.sh

.PHONY: test-serverless verify-m8
test-serverless: ## sondes M8 réelles ou rejeu explicite, sans GPU
	@PYTHONPATH=.:tests:services/model-gateway python3 tests/serverless_gate.py
verify-m8: ## vérificateur protégé serverless
	@bash scripts/verify-m8.sh
.PHONY: test-memory verify-m9
test-memory: ## tests intégrés de mémoire et projets sur données synthétiques
	@PYTHONPATH=.:tests:services/model-gateway python3 tests/memory_gate.py
verify-m9: ## mémoire persistée, isolation et effacement
	@bash scripts/verify-m9.sh
.PHONY: test-large-input verify-m10
test-large-input: ## grandes sources publiques : retrieval réel et fournisseur enregistré
	@PYTHONPATH=.:tests:services/model-gateway python3 tests/large_input_gate.py 2>&1
verify-m10: ## grandes entrées sourcées dans les budgets
	@bash scripts/verify-m10.sh
.PHONY: test-streaming verify-m11
test-streaming:
	@PYTHONPATH=.:services/model-gateway ATLAS_STREAM_REPORT=BRAIN/eval/streaming.json python3 -m unittest discover -s tests -p 'test_stream*.py' 2>&1
verify-m11:
	@bash scripts/verify-m11.sh
.PHONY: test-vision verify-m12
test-vision: ## M12 : HTTP adaptateur/gateway, transport vision enregistré ou réel
	@PYTHONPATH=.:tests:services/model-gateway python3 tests/vision_gate.py
verify-m12: ## vérificateur protégé multimodal
	@bash scripts/verify-m12.sh

.PHONY: test-imagegen verify-m13
test-imagegen: ## génération GPU réelle et extinction en fin de cycle
	@timeout 1500 bash infra/imagegen.sh 2>&1
verify-m13: ## gate protégé génération souveraine
	@bash scripts/verify-m13.sh

.PHONY: serve-imagegen
serve-imagegen: ## active le GPU pour le chat durant dix minutes après chargement
	@timeout 2400 bash infra/imagegen.sh serve 2>&1

.PHONY: test-mcp verify-m14
test-mcp: ## MCP réel ou rejeu explicite des échanges synthétiques enregistrés
	@PYTHONPATH=.:tests:services/model-gateway python3 tests/mcp_gate.py
verify-m14: ## lecture et écriture confirmée, gate protégé intact
	@bash scripts/verify-m14.sh

.PHONY: serve-devapi
serve-devapi: ## API développeurs locale, clés et quotas individuels ; sans GPU
	@bash scripts/serve-devapi.sh

.PHONY: test-devapi verify-m15
test-devapi: ## API développeurs : HTTP réel local et flux fournisseur enregistrés
	@PYTHONPATH=.:tests:services/model-gateway python3 tests/devapi_gate.py
verify-m15: ## gate protégé auth/quotas/outils/streaming/contexte/coût
	@bash scripts/verify-m15.sh

.PHONY: test-devapi-e2e
test-devapi-e2e: ## fournisseur réel : fonction puis réponse et contexte utile >=24KiB
	@PYTHONPATH=.:tests:services/model-gateway python3 tests/devapi_live.py
