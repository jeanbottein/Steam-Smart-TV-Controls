ifneq (,$(wildcard ./.env))
	include .env
	export
endif

SHELL := bash

help: ## List tasks
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "\033[36m%-18s\033[0m %s\n",$$1,$$2}'

vendor: ## Install dependencies
	@pnpm install

build: ## Build frontend
	@pnpm run build

release: ## Build the distributable zip
	@bash scripts/build_release.sh

deploy: ## Build and install onto a local Deck
	@bash scripts/deploy.sh

test: ## Run unit tests (core + release tooling)
	@PYTHONPATH=backend python3 -m pytest backend/tv_core/tests .github/scripts/tests -q

.PHONY: help vendor build release deploy test
