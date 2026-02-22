#!/usr/bin/env bash
# =============================================================================
# SEO Intelligence Platform - Setup Script
# Installs all dependencies and configures the development environment
# =============================================================================

set -euo pipefail

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

info() { echo -e "${GREEN}[INFO]${RESET} $1"; }
warn() { echo -e "${YELLOW}[WARN]${RESET} $1"; }
error() { echo -e "${RED}[ERROR]${RESET} $1"; exit 1; }

echo -e "${BOLD}SEO Intelligence Platform - Setup${RESET}"
echo "========================================"

# Check required tools
info "Checking prerequisites..."
command -v python3 >/dev/null 2>&1 || error "Python 3.11+ required"
command -v node >/dev/null 2>&1 || error "Node.js 18+ required"
command -v npm >/dev/null 2>&1 || error "npm required"
command -v psql >/dev/null 2>&1 || warn "PostgreSQL client not found - install postgres"
command -v redis-cli >/dev/null 2>&1 || warn "Redis client not found - install redis"

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python version: $PY_VERSION"

NODE_VERSION=$(node --version)
info "Node version: $NODE_VERSION"

# ============================================================
# Backend Setup
# ============================================================
info "Setting up backend..."
cd "$(dirname "$0")/../backend"

# Create virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
    info "Created Python virtual environment"
fi

# Activate venv
source venv/bin/activate

# Install Python dependencies
info "Installing Python dependencies (this may take a minute)..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
info "Python dependencies installed"

# Install Playwright browsers
info "Installing Playwright browsers..."
playwright install chromium --with-deps
info "Playwright browsers installed"

# Copy environment file if not exists
if [ ! -f ".env" ]; then
    cp .env.example .env
    warn "Created .env from .env.example - please update with your credentials"
fi

# ============================================================
# Database Setup
# ============================================================
info "Setting up database..."

source .env 2>/dev/null || true
DB_URL="${DATABASE_URL:-postgresql://seouser:seopassword@localhost:5432/seodb}"

# Create database and user
psql postgres -c "CREATE USER seouser WITH PASSWORD 'seopassword';" 2>/dev/null || warn "User seouser may already exist"
psql postgres -c "CREATE DATABASE seodb OWNER seouser;" 2>/dev/null || warn "Database seodb may already exist"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE seodb TO seouser;" 2>/dev/null || true

# Run SQL schema
psql "$DB_URL" -f database/schema.sql
info "Database schema applied"

# Initialize Alembic
if [ ! -d "database/migrations" ]; then
    alembic init database/migrations
    info "Alembic initialized"
fi

# ============================================================
# Frontend Setup
# ============================================================
info "Setting up frontend..."
cd "$(dirname "$0")/../frontend"

npm install
info "Frontend dependencies installed"

# Create .env.local if not exists
if [ ! -f ".env.local" ]; then
    echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
    echo "NEXT_PUBLIC_APP_NAME=SEO Intelligence" >> .env.local
    info "Created frontend .env.local"
fi

echo ""
echo -e "${GREEN}${BOLD}Setup complete!${RESET}"
echo ""
echo "Next steps:"
echo "  1. Ensure PostgreSQL is running: brew services start postgresql@15"
echo "  2. Ensure Redis is running: brew services start redis"
echo "  3. Start backend: cd backend && source venv/bin/activate && uvicorn main:app --reload"
echo "  4. Start worker: cd backend && source venv/bin/activate && celery -A workers.celery_app worker -Q crawl,analysis,report -l info"
echo "  5. Start frontend: cd frontend && npm run dev"
echo ""
echo "  API: http://localhost:8000/docs"
echo "  Frontend: http://localhost:3000"