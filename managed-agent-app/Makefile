# Managed Agent kit -- common tasks. Run `make` (or `make help`) for the list.
.DEFAULT_GOAL := help
SHELL := /bin/bash

RUNTIME     ?= python
PROMPT      ?= Hello! Please introduce yourself in one sentence.
DEPLOY_ARGS ?=

.PHONY: help install run verify test typecheck deploy clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-11s\033[0m %s\n", $$1, $$2}'

install: ## Install deps (python venv + pytest, node modules)
	python3 -m venv python/.venv
	./python/.venv/bin/pip install -q -U pip
	./python/.venv/bin/pip install -q -r python/requirements.txt pytest
	cd node && npm install --no-audit --no-fund

run: ## Run the client (RUNTIME=python|node PROMPT="...")
	RUNTIME=$(RUNTIME) ./deploy/run.sh "$(PROMPT)"

verify: ## Run all checks (compile, lint, JSON, pytest, tsc)
	@PATH="$(CURDIR)/python/.venv/bin:$$PATH" ./verify.sh

test: ## Run unit tests only
	./python/.venv/bin/python -m pytest -q tests/

typecheck: ## Type-check the TypeScript client
	cd node && npx --yes tsc --noEmit

deploy: ## Deploy to a host, e.g. make deploy DEPLOY_ARGS="--host 1.2.3.4 --key ~/.ssh/id_ed25519"
	./deploy/deploy.sh $(DEPLOY_ARGS)

clean: ## Remove venv, node_modules, caches
	rm -rf python/.venv node/node_modules node/package-lock.json
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true
