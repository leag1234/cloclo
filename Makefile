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
