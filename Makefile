# Makefile for Gamr — Git-aware Agent Monitor & Review
#
# Usage:
#   make              Show all available targets
#   make <target>     Run a specific target

.PHONY: help
help: ## Show this help message
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Common workflows:"
	@echo "  make install test     # Set up and run tests"
	@echo "  make lint format      # Check and fix code"
	@echo "  make security test    # Full validation"

# ============================================================================
# Setup and Installation
# ============================================================================

.PHONY: install
install: ## Install dependencies with uv
	uv sync

.PHONY: install-hooks
install-hooks: ## Install pre-commit git hooks
	uv run pre-commit install

# ============================================================================
# Code Quality
# ============================================================================

.PHONY: lint
lint: ## Run linting checks (ruff check + format check)
	./scripts/lint.sh

.PHONY: format
format: ## Auto-fix formatting and linting issues
	./scripts/lint.sh --fix

.PHONY: pre-commit
pre-commit: ## Run all pre-commit hooks manually
	uv run pre-commit run --all-files

.PHONY: security
security: ## Run security scans (bandit + pip-audit)
	uv run bandit -r src/ -c .bandit
	uv run pip-audit

# ============================================================================
# Testing
# ============================================================================

.PHONY: test
test: ## Run all tests
	uv run pytest tests/ -q

.PHONY: test-verbose
test-verbose: ## Run tests with verbose output
	uv run pytest tests/ -v

.PHONY: coverage
coverage: ## Run tests with coverage report
	uv run pytest tests/ -q --cov=gamr --cov-report=term-missing

# ============================================================================
# Dependencies
# ============================================================================

.PHONY: update-deps
update-deps: ## Update dependencies (7-day lag for supply chain protection)
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║  Updating dependencies with 7-day publication lag            ║"
	@echo "║  (packages published less than 7 days ago are excluded)      ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	uv lock --upgrade --exclude-newer "$$(date -v-7d +%Y-%m-%dT00:00:00Z)"
	uv sync
	@echo ""
	@echo "Running security audit..."
	uv run pip-audit
	@echo ""
	@echo "✅ Dependencies updated. Run 'make test' to verify."

# ============================================================================
# Build
# ============================================================================

.PHONY: build
build: ## Build wheel and sdist
	uv build

# ============================================================================
# Run
# ============================================================================

.PHONY: run
run: ## Run the app on the current directory
	uv run gamr .

# ============================================================================
# Release
# ============================================================================

.PHONY: release
release: ## Release (interactive — asks for bump type)
	@CHOICE=$$(uv run scripts/chooser.py --title "Release type?" patch minor major 3>&1 1>&2) || exit 1; \
	./scripts/release.sh $$CHOICE

.PHONY: release-patch
release-patch: ## Release a patch version (bug fixes)
	./scripts/release.sh patch

.PHONY: release-minor
release-minor: ## Release a minor version (new features)
	./scripts/release.sh minor

.PHONY: release-major
release-major: ## Release a major version (breaking changes)
	./scripts/release.sh major

# ============================================================================
# Cleanup
# ============================================================================

.PHONY: clean
clean: ## Remove build artifacts and caches
	rm -rf dist/ .pytest_cache .ruff_cache .coverage

# ============================================================================
# Validation (Full Quality Check)
# ============================================================================

.PHONY: validate
validate: lint security test ## Run lint, security, and tests
	@echo ""
	@echo "✅ Validation complete!"

# ============================================================================
# Default Target
# ============================================================================

.DEFAULT_GOAL := help
