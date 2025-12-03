.PHONY: help setup clean install dev test lint format infra-up infra-down migrate migrate-auto migrate-down db-shell redis-shell logs

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

##@ General

help: ## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\n$(BLUE)Usage:$(NC)\n  make $(GREEN)<target>$(NC)\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(BLUE)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Setup & Installation

setup: ## Initial project setup (install deps, copy env, init db)
	@echo "$(GREEN)🚀 Setting up Colink project...$(NC)"
	@cp .env.example .env 2>/dev/null || echo "$(YELLOW).env already exists, skipping$(NC)"
	@echo "$(GREEN)✓ Created .env file$(NC)"
	@$(MAKE) install
	@echo "$(GREEN)✅ Setup complete!$(NC)"
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Edit .env with your configuration"
	@echo "  2. Run 'make infra-up' to start infrastructure"
	@echo "  3. Run 'make migrate' to initialize database"
	@echo "  4. Run 'make dev' to start services"

install: ## Install Python dependencies
	@echo "$(GREEN)📦 Installing dependencies...$(NC)"
	pip install -r requirements-dev.txt
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

clean: ## Clean up build artifacts and caches
	@echo "$(RED)🧹 Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -name ".coverage" -delete
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

##@ Development

dev: ## Start all services in development mode
	@echo "$(GREEN)🚀 Starting development services...$(NC)"
	docker-compose up

dev-detached: ## Start services in background
	@echo "$(GREEN)🚀 Starting services in background...$(NC)"
	docker-compose up -d

stop: ## Stop all running services
	@echo "$(YELLOW)⏸  Stopping services...$(NC)"
	docker-compose stop

down: ## Stop and remove all containers
	@echo "$(RED)🛑 Stopping and removing containers...$(NC)"
	docker-compose down

restart: ## Restart all services
	@echo "$(YELLOW)♻️  Restarting services...$(NC)"
	docker-compose restart

##@ Infrastructure

infra-up: ## Start infrastructure services only (Postgres, Redis, Kafka, etc.)
	@echo "$(GREEN)🏗️  Starting infrastructure services...$(NC)"
	docker-compose up -d postgres redis redpanda minio keycloak opensearch
	@echo "$(GREEN)✓ Infrastructure is running$(NC)"
	@echo "$(YELLOW)Waiting for services to be ready...$(NC)"
	@sleep 5
	@echo "$(GREEN)✅ Infrastructure ready!$(NC)"

infra-down: ## Stop infrastructure services
	@echo "$(RED)🛑 Stopping infrastructure...$(NC)"
	docker-compose stop postgres redis redpanda minio keycloak opensearch

infra-logs: ## View infrastructure logs
	docker-compose logs -f postgres redis redpanda minio keycloak

##@ Database

migrate: ## Run database migrations
	@echo "$(GREEN)🗄️  Running database migrations...$(NC)"
	alembic upgrade head
	@echo "$(GREEN)✓ Migrations complete$(NC)"

migrate-auto: ## Auto-generate migration from models
	@echo "$(GREEN)📝 Generating migration...$(NC)"
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"
	@echo "$(GREEN)✓ Migration generated$(NC)"
	@echo "$(YELLOW)Review the migration file before running 'make migrate'$(NC)"

migrate-down: ## Rollback last migration
	@echo "$(YELLOW)⏪ Rolling back last migration...$(NC)"
	alembic downgrade -1
	@echo "$(GREEN)✓ Rollback complete$(NC)"

migrate-history: ## Show migration history
	@alembic history

migrate-current: ## Show current migration
	@alembic current

db-shell: ## Open PostgreSQL shell
	@docker-compose exec postgres psql -U colink -d colink

db-reset: ## ⚠️  DANGER: Drop and recreate database (dev only!)
	@echo "$(RED)⚠️  WARNING: This will DELETE all data!$(NC)"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker-compose exec postgres psql -U colink -d postgres -c "DROP DATABASE IF EXISTS colink;"; \
		docker-compose exec postgres psql -U colink -d postgres -c "CREATE DATABASE colink;"; \
		$(MAKE) migrate; \
		echo "$(GREEN)✓ Database reset complete$(NC)"; \
	else \
		echo "$(YELLOW)Aborted$(NC)"; \
	fi

seed: ## Seed database with test data
	@echo "$(GREEN)🌱 Seeding database...$(NC)"
	python scripts/seed_db.py
	@echo "$(GREEN)✓ Database seeded$(NC)"

##@ Redis

redis-shell: ## Open Redis CLI
	@docker-compose exec redis redis-cli

redis-flush: ## ⚠️  DANGER: Flush all Redis data
	@echo "$(RED)⚠️  WARNING: This will DELETE all Redis data!$(NC)"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker-compose exec redis redis-cli FLUSHALL; \
		echo "$(GREEN)✓ Redis flushed$(NC)"; \
	else \
		echo "$(YELLOW)Aborted$(NC)"; \
	fi

##@ Testing

test: ## Run all tests
	@echo "$(GREEN)🧪 Running tests...$(NC)"
	pytest

test-unit: ## Run unit tests only
	@echo "$(GREEN)🧪 Running unit tests...$(NC)"
	pytest backend/tests/unit

test-integration: ## Run integration tests only
	@echo "$(GREEN)🧪 Running integration tests...$(NC)"
	pytest backend/tests/integration

test-cov: ## Run tests with coverage report
	@echo "$(GREEN)🧪 Running tests with coverage...$(NC)"
	pytest --cov=shared --cov=services --cov-report=html --cov-report=term
	@echo "$(GREEN)✓ Coverage report generated in htmlcov/index.html$(NC)"

test-watch: ## Run tests in watch mode
	@echo "$(GREEN)👀 Running tests in watch mode...$(NC)"
	pytest-watch

##@ Code Quality

lint: ## Run all linters
	@echo "$(GREEN)🔍 Running linters...$(NC)"
	@$(MAKE) lint-ruff
	@$(MAKE) lint-mypy
	@echo "$(GREEN)✅ All linters passed!$(NC)"

lint-ruff: ## Run Ruff linter
	@echo "$(GREEN)Running Ruff...$(NC)"
	ruff check .

lint-mypy: ## Run MyPy type checker
	@echo "$(GREEN)Running MyPy...$(NC)"
	mypy backend/shared/ backend/services/

format: ## Format code with Black and isort
	@echo "$(GREEN)✨ Formatting code...$(NC)"
	black .
	isort .
	@echo "$(GREEN)✓ Code formatted$(NC)"

format-check: ## Check code formatting without changes
	@echo "$(GREEN)🔍 Checking code format...$(NC)"
	black --check .
	isort --check-only .

##@ Logs & Monitoring

logs: ## View logs from all services
	docker-compose logs -f

logs-service: ## View logs from specific service (usage: make logs-service SERVICE=messaging-service)
	@if [ -z "$(SERVICE)" ]; then \
		echo "$(RED)Error: SERVICE not specified$(NC)"; \
		echo "Usage: make logs-service SERVICE=messaging-service"; \
		exit 1; \
	fi
	docker-compose logs -f $(SERVICE)

ps: ## Show running containers
	docker-compose ps

stats: ## Show container resource usage
	docker stats

##@ Service Management

service-shell: ## Open shell in service container (usage: make service-shell SERVICE=messaging-service)
	@if [ -z "$(SERVICE)" ]; then \
		echo "$(RED)Error: SERVICE not specified$(NC)"; \
		echo "Usage: make service-shell SERVICE=messaging-service"; \
		exit 1; \
	fi
	docker-compose exec $(SERVICE) /bin/bash

service-restart: ## Restart specific service (usage: make service-restart SERVICE=messaging-service)
	@if [ -z "$(SERVICE)" ]; then \
		echo "$(RED)Error: SERVICE not specified$(NC)"; \
		echo "Usage: make service-restart SERVICE=messaging-service"; \
		exit 1; \
	fi
	docker-compose restart $(SERVICE)

##@ Health Checks

health: ## Check health of all services
	@echo "$(GREEN)🏥 Checking service health...$(NC)"
	@echo "\n$(BLUE)Infrastructure:$(NC)"
	@curl -s http://localhost:5432 > /dev/null 2>&1 && echo "  $(GREEN)✓ PostgreSQL$(NC)" || echo "  $(RED)✗ PostgreSQL$(NC)"
	@curl -s http://localhost:6379 > /dev/null 2>&1 && echo "  $(GREEN)✓ Redis$(NC)" || echo "  $(RED)✗ Redis$(NC)"
	@curl -s http://localhost:9092 > /dev/null 2>&1 && echo "  $(GREEN)✓ Kafka$(NC)" || echo "  $(RED)✗ Kafka$(NC)"
	@echo "\n$(BLUE)Services:$(NC)"
	@curl -sf http://localhost:8001/health > /dev/null 2>&1 && echo "  $(GREEN)✓ Auth Proxy$(NC)" || echo "  $(YELLOW)- Auth Proxy (not running)$(NC)"
	@curl -sf http://localhost:8002/health > /dev/null 2>&1 && echo "  $(GREEN)✓ Users Service$(NC)" || echo "  $(YELLOW)- Users Service (not running)$(NC)"

##@ Documentation

docs-serve: ## Serve documentation locally
	@echo "$(GREEN)📚 Serving documentation...$(NC)"
	@echo "Open http://localhost:8000"
	@cd docs && python -m http.server 8000

##@ Cleanup

prune: ## Remove all unused Docker resources
	@echo "$(RED)🗑️  Pruning Docker resources...$(NC)"
	docker system prune -af --volumes
	@echo "$(GREEN)✓ Prune complete$(NC)"

reset: clean down ## Complete reset (stop containers, clean artifacts)
	@echo "$(GREEN)✅ Project reset complete$(NC)"

##@ CI/CD

ci-test: ## Run tests in CI mode
	@echo "$(GREEN)🤖 Running CI tests...$(NC)"
	pytest --cov=shared --cov=services --cov-report=xml --cov-report=term -v

ci-lint: ## Run linters in CI mode
	@echo "$(GREEN)🤖 Running CI linters...$(NC)"
	ruff check --output-format=github .
	mypy backend/shared/ backend/services/ --junit-xml=mypy-report.xml

ci-build: ## Build Docker images for CI
	@echo "$(GREEN)🤖 Building Docker images...$(NC)"
	docker-compose build --parallel

##@ Quick Commands

up: infra-up migrate ## Quick start: infra + migrations
	@echo "$(GREEN)✅ Ready for development!$(NC)"
	@echo "Run '$(GREEN)make dev$(NC)' to start application services"

quick-start: setup up ## Complete quick start for new developers
	@echo "$(GREEN)✅ Project is ready!$(NC)"
	@echo "$(YELLOW)Next: Run 'make dev' to start all services$(NC)"
