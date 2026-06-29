ifneq (,$(wildcard ./.env))
	include .env
	export
endif

SHELL := bash

# Prefer the project venv (created by `make venv-dev`); fall back to system python3.
PYTHON := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

help: ## List tasks
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "\033[36m%-18s\033[0m %s\n",$$1,$$2}'

vendor: ## Install dependencies
	@pnpm install

venv-dev: ## Create .venv and install Python dev tools (pytest)
	@python3 -m venv .venv && .venv/bin/pip install -q -r requirements-dev.txt

build: ## Build frontend
	@pnpm run build

release: ## Build the distributable zip
	@bash scripts/build_release.sh

deploy: ## Build and install onto a local Deck
	@bash scripts/deploy.sh

test: ## Run unit tests (core + release tooling); run `make venv-dev` first
	@PYTHONPATH=backend $(PYTHON) -m pytest backend/tv_core/tests backend/tv_driver_lg/tests .github/scripts/tests -q

.PHONY: help vendor venv-dev build release deploy test
