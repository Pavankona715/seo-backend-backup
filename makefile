# SEO Intelligence Platform - Makefile
# Convenience commands for development

.PHONY: help setup install-backend install-frontend db-setup db-reset
.PHONY: dev-backend dev-frontend dev-worker dev-flower
.PHONY: test lint format clean

PYTHON = backend/venv/bin/python
PIP = backend/venv/bin/pip
UVICORN = backend/venv/bin/uvicorn
CELERY = backend/venv/bin/celery

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================================
# Setup
# ============================================================

setup: ## Full setup (backend + frontend + database)
	bash scripts/setup.sh

install-backend: ## Install Python dependencies
	cd backend && pip install -r requirements.txt
	playwright install chromium --with-deps

install-frontend: ## Install Node dependencies
	cd frontend && npm install

# ============================================================
# Database
# ============================================================

db-setup: ## Create database and apply schema
	psql postgres -c "CREATE USER seouser WITH PASSWORD 'seopassword';" 2>/dev/null || true
	psql postgres -c "CREATE DATABASE seodb OWNER seouser;" 2>/dev/null || true
	psql postgresql://seouser:seopassword@localhost:5432/seodb -f backend/database/schema.sql

db-reset: ## Drop and recreate database (DESTRUCTIVE!)
	psql postgres -c "DROP DATABASE IF EXISTS seodb;"
	$(MAKE) db-setup

# ============================================================
# Development Servers
# ============================================================

dev-backend: ## Start FastAPI backend (dev mode with reload)
	cd backend && source venv/bin/activate && \
		uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level info

dev-frontend: ## Start Next.js frontend (dev mode)
	cd frontend && npm run dev

dev-worker: ## Start Celery crawl worker
	cd backend && source venv/bin/activate && \
		celery -A workers.celery_app worker \
		-Q crawl,analysis,report,default \
		-c 4 \
		--loglevel=info \
		-n crawl-worker@%h

dev-worker-beat: ## Start Celery beat scheduler
	cd backend && source venv/bin/activate && \
		celery -A workers.celery_app beat --loglevel=info

dev-flower: ## Start Flower (Celery monitoring UI)
	cd backend && source venv/bin/activate && \
		celery -A workers.celery_app flower \
		--port=5555 \
		--broker_api=redis://localhost:6379/1

# Start all services in parallel (requires GNU parallel or tmux)
dev: ## Start all services (requires tmux)
	tmux new-session -d -s seo-platform
	tmux send-keys -t seo-platform "make dev-backend" C-m
	tmux split-window -h -t seo-platform
	tmux send-keys -t seo-platform "make dev-worker" C-m
	tmux split-window -v -t seo-platform
	tmux send-keys -t seo-platform "make dev-frontend" C-m
	tmux attach-session -t seo-platform

# ============================================================
# Quality
# ============================================================

test: ## Run backend tests
	cd backend && source venv/bin/activate && \
		python -m pytest tests/ -v --tb=short

lint: ## Run linters
	cd backend && source venv/bin/activate && \
		python -m ruff check . && \
		python -m mypy . --ignore-missing-imports
	cd frontend && npm run lint

format: ## Format code
	cd backend && source venv/bin/activate && \
		python -m black . && \
		python -m ruff check --fix .
	cd frontend && npx prettier --write "src/**/*.{ts,tsx}"

# ============================================================
# Cleanup
# ============================================================

clean: ## Clean build artifacts
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf frontend/.next frontend/node_modules/.cache 2>/dev/null || true

clean-all: clean ## Full clean (removes venv and node_modules)
	rm -rf backend/venv frontend/node_modules