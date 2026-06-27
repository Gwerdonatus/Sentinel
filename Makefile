# =============================================================================
# Sentinel Makefile
# Convenience targets for common development tasks.
# All targets wrap Docker Compose commands.
# =============================================================================

.DEFAULT_GOAL := help
.PHONY: help up down build logs shell-backend shell-frontend migrate test test-backend test-frontend lint typecheck coverage clean

# Colors
CYAN  := $(shell tput setaf 6)
GREEN := $(shell tput setaf 2)
RESET := $(shell tput sgr0)

help: ## Show this help message
	@echo "$(CYAN)Sentinel Development Commands$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# =============================================================================
# Stack Management
# =============================================================================

up: ## Start the full Sentinel stack
	docker compose up

up-d: ## Start the full stack in detached mode
	docker compose up -d

down: ## Stop all services
	docker compose down

build: ## Rebuild all Docker images
	docker compose build

rebuild: ## Force rebuild without cache
	docker compose build --no-cache

logs: ## Follow logs for all services
	docker compose logs -f

logs-backend: ## Follow backend logs only
	docker compose logs -f backend

logs-worker: ## Follow worker logs only
	docker compose logs -f worker

# =============================================================================
# Database
# =============================================================================

migrate: ## Run Django migrations
	docker compose exec backend python manage.py migrate

makemigrations: ## Create new Django migrations
	docker compose exec backend python manage.py makemigrations

shell-db: ## Connect to PostgreSQL CLI
	docker compose exec postgres psql -U sentinel -d sentinel_db

# =============================================================================
# Testing
# =============================================================================

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests with coverage
	docker compose exec backend pytest --cov=sentinel --cov-report=term-missing -v

test-backend-unit: ## Run unit tests only (fast, no DB)
	docker compose exec backend pytest tests/unit/ -v -m unit

test-backend-integration: ## Run integration tests only
	docker compose exec backend pytest tests/integration/ -v -m integration

test-frontend: ## Run frontend type check and lint
	docker compose exec frontend npm run type-check
	docker compose exec frontend npm run lint

coverage: ## Generate HTML coverage report
	docker compose exec backend pytest --cov=sentinel --cov-report=html
	@echo "$(GREEN)Coverage report at apps/backend/htmlcov/index.html$(RESET)"

# =============================================================================
# Code Quality
# =============================================================================

lint: ## Run all linters
	docker compose exec backend ruff check .
	docker compose exec frontend npm run lint

format: ## Format all code
	docker compose exec backend ruff format .

typecheck: ## Run type checkers
	docker compose exec backend mypy sentinel/ config/
	docker compose exec frontend npm run type-check

check: lint typecheck test ## Run lint + typecheck + tests (full CI simulation)

security-scan: ## Scan Python dependencies for vulnerabilities
	docker compose exec backend pip-audit -r requirements.txt

# =============================================================================
# Shell Access
# =============================================================================

shell-backend: ## Open Django shell
	docker compose exec backend python manage.py shell

shell-py: ## Open Python shell in backend container
	docker compose exec backend python

shell-frontend: ## Open shell in frontend container
	docker compose exec frontend sh

# =============================================================================
# Observability
# =============================================================================

prometheus: ## Open Prometheus in browser
	@open http://localhost:9090 || xdg-open http://localhost:9090

grafana: ## Open Grafana in browser
	@open http://localhost:3001 || xdg-open http://localhost:3001

flower: ## Open Celery Flower in browser
	@open http://localhost:5555 || xdg-open http://localhost:5555

# =============================================================================
# Cleanup
# =============================================================================

clean: ## Remove containers, volumes, and build artifacts
	docker compose down -v --remove-orphans
	find apps/backend -name "*.pyc" -delete
	find apps/backend -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null; true
	find apps/backend -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null; true
	find apps/backend -name ".mypy_cache" -type d -exec rm -rf {} + 2>/dev/null; true
	find apps/backend -name ".ruff_cache" -type d -exec rm -rf {} + 2>/dev/null; true
	@echo "$(GREEN)Clean complete$(RESET)"

clean-db: ## Remove only database volume (resets all data)
	docker compose down -v postgres
	@echo "$(GREEN)Database volume removed. Run 'make up' to recreate.$(RESET)"
