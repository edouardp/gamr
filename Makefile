# Makefile for gamr
#
# This Makefile provides convenient shortcuts for common development tasks.
# All targets are thin wrappers around scripts in ./scripts/ or direct tool invocations.
#
# Usage:
#   make help              Show all available targets with descriptions
#   make <target>          Run a specific target
#
# Common workflows:
#   make test              Run all tests
#   make deploy-infra      Deploy CloudFormation infrastructure
#   make deploy-website    Upload website and invalidate CDN

.PHONY: help
help: ## Show this help message
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Common workflows:"
	@echo "  make test                # Run all tests"
	@echo "  make deploy-infra        # Deploy AWS infrastructure"
	@echo "  make deploy-website      # Upload website to S3 + invalidate CDN"

# ============================================================================
# Development
# ============================================================================

.PHONY: install
install: ## Install dependencies with uv
	uv sync

.PHONY: run
run: ## Run gamr in the current directory
	uv run gamr

.PHONY: test
test: ## Run all tests
	uv run pytest

.PHONY: test-quick
test-quick: ## Run tests stopping on first failure
	uv run pytest -x -q

.PHONY: lint
lint: ## Run linting (ruff)
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

.PHONY: format
format: ## Auto-fix formatting and linting issues
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

# ============================================================================
# Release
# ============================================================================

.PHONY: release
release: ## Create a release (interactive version bump selector)
	@BUMP=$$(uv run scripts/chooser.py --title "Release type:" '{"patch": "Bug fixes, minor changes", "minor": "New features, backwards compatible", "major": "Breaking changes"}' 3>&1 1>&2) || exit 1; \
	echo "Creating $$BUMP release..."; \
	./scripts/release.sh $$BUMP

# ============================================================================
# Website Deployment
# ============================================================================

.PHONY: deploy-infra
deploy-infra: ## Deploy CloudFormation infrastructure (S3, CloudFront, DNS)
	./scripts/deploy-cloudformation.sh

.PHONY: deploy-website
deploy-website: ## Upload website to S3 and invalidate CloudFront
	./scripts/upload-website.sh

.PHONY: deploy-all
deploy-all: deploy-infra deploy-website ## Deploy infrastructure then upload website

# ============================================================================
# Website Development
# ============================================================================

.PHONY: serve
serve: ## Serve the website locally on port 8000
	python3 -m http.server 8000 --directory website

# ============================================================================
# Cleanup
# ============================================================================

.PHONY: clean
clean: ## Remove cache files and build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov dist build *.egg-info

# ============================================================================
# Default Target
# ============================================================================

.DEFAULT_GOAL := help
