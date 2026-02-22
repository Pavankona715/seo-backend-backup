# SEO Intelligence Platform

A production-ready, full-stack SEO crawler and analysis platform. Crawls entire websites, extracts all SEO signals, computes multi-dimensional scores, detects issues, and surfaces keyword opportunities.

---

## Architecture

```
seo-platform/
├── backend/                  # Python FastAPI backend
│   ├── core/                 # Config, logging, exceptions
│   ├── crawler/              # Async crawler engine (Playwright + httpx)
│   ├── analyzer/             # SEO signal extraction
│   ├── scorer/               # Multi-dimensional scoring engine
│   ├── recommendations/      # Issue detection & fix recommendations
│   ├── keyword_engine/       # Opportunity scoring
│   ├── api/                  # FastAPI routes + middleware
│   ├── database/             # SQLAlchemy models + repositories + schema
│   ├── workers/              # Celery task definitions
│   └── main.py               # Application entry point
├── frontend/                 # Next.js 14 dashboard
│   └── src/
│       ├── app/              # App Router pages
│       ├── components/       # React UI components
│       └── lib/              # API client + utilities
├── scripts/                  # Setup automation
└── Makefile                  # Development commands
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI + Python 3.11 |
| Crawler | Playwright + httpx + asyncio |
| Task Queue | Celery + Redis |
| Database | PostgreSQL 15 + SQLAlchemy (async) |
| SEO Analysis | BeautifulSoup4 + extruct + trafilatura |
| Frontend | Next.js 14 + Tailwind CSS + shadcn/ui |
| Monitoring | Flower (Celery) |

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+

### macOS Installation

```bash
# Install Homebrew dependencies
brew install python@3.11 node postgresql@15 redis

# Start services
brew services start postgresql@15
brew services start redis
```

### Ubuntu/Debian Installation

```bash
# Python, Node.js
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm

# PostgreSQL
sudo apt install -y postgresql-15
sudo systemctl start postgresql

# Redis
sudo apt install -y redis-server
sudo systemctl start redis
```

---

## Setup Instructions

### 1. Clone and Configure

```bash
git clone <repo-url> seo-platform
cd seo-platform

# Run automated setup
bash scripts/setup.sh
```

Or manually:

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium --with-deps

# Configure environment
cp .env.example .env
# Edit .env with your database credentials
```

### 3. Database Setup

```bash
# Create PostgreSQL user and database
psql postgres -c "CREATE USER seouser WITH PASSWORD 'seopassword';"
psql postgres -c "CREATE DATABASE seodb OWNER seouser;"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE seodb TO seouser;"

# Apply schema (from backend directory)
psql postgresql://seouser:seopassword@localhost:5432/seodb -f database/schema.sql
```

### 4. Frontend Setup

```bash
cd frontend
npm install
# .env.local is pre-configured for local development
```

---

## Running the Platform

### Terminal 1 – FastAPI Backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API available at: http://localhost:8000
Swagger docs: http://localhost:8000/docs

### Terminal 2 – Celery Worker

```bash
cd backend
source venv/bin/activate
celery -A workers.celery_app worker \
  -Q crawl,analysis,report,default \
  -c 4 \
  --loglevel=info
```

### Terminal 3 – Frontend

```bash
cd frontend
npm run dev
```

Dashboard at: http://localhost:3000

### Terminal 4 – Flower (Celery Monitor, optional)

```bash
cd backend
source venv/bin/activate
celery -A workers.celery_app flower --port=5555
```

Flower UI: http://localhost:5555

---

## API Reference

### Start a Crawl

```http
POST /api/v1/crawl
Content-Type: application/json

{
  "url": "https://example.com",
  "max_depth": 5,
  "max_pages": 1000,
  "use_js_rendering": false,
  "respect_robots": true
}
```

Response:
```json
{
  "job_id": "uuid",
  "site_id": "uuid",
  "status": "pending",
  "domain": "example.com",
  "message": "Crawl job started..."
}
```

### Get Report

```http
GET /api/v1/report/{domain}
```

### Get Issues

```http
GET /api/v1/issues/{domain}?severity=critical&limit=100
```

### Get Keyword Opportunities

```http
GET /api/v1/opportunities/{domain}?min_score=20&limit=50
```

### Get Pages

```http
GET /api/v1/pages/{domain}?skip=0&limit=100&status_code=404
```

---

## Scoring System

Each page receives scores across 5 dimensions (weighted to produce an overall score):

| Dimension | Weight | Factors |
|-----------|--------|---------|
| Technical | 35% | HTTPS, status codes, page speed, viewport, canonical, schema |
| Content | 30% | Title length, meta description, headings, word count, alt text |
| Authority | 20% | Inbound internal links, link diversity |
| Internal Linking | 10% | Outgoing links count, orphan page detection |
| AI Visibility | 5% | Schema types, heading structure, entity clarity |

---

## Keyword Opportunity Formula

```
Opportunity Score = Volume × CTR × RankGap ÷ Difficulty
```

- **Volume**: Estimated monthly search volume
- **CTR**: Click-through rate for target position (based on position CTR curve)
- **RankGap**: Number of positions to climb to reach target rank
- **Difficulty**: Keyword competition score (0-100)

---

## Scaling

### Horizontal Worker Scaling

```bash
# Start multiple crawl workers
celery -A workers.celery_app worker -Q crawl -c 8 -n crawl-worker-1@%h
celery -A workers.celery_app worker -Q crawl -c 8 -n crawl-worker-2@%h

# Configure Redis for worker discovery
# Each worker will pick up jobs from the same Redis queues
```

### Concurrency Configuration

Edit `backend/.env`:
```env
CRAWLER_MAX_CONCURRENT=100    # Max concurrent page fetches per job
CELERY_WORKER_CONCURRENCY=8   # Celery worker thread count
CRAWLER_RATE_LIMIT_RPS=10     # Max requests per second per domain
```

### Database Scaling

For high-volume deployments:
- Use PostgreSQL read replicas for reporting queries
- Enable `pg_partman` for time-based table partitioning on `pages` and `crawl_jobs`
- Use connection pooling (PgBouncer) in front of PostgreSQL

---

## Project Structure Details

```
backend/
├── core/
│   ├── config.py           # Pydantic settings from .env
│   ├── logging.py          # Structured JSON logging (structlog)
│   └── exceptions.py       # Custom exception hierarchy
├── crawler/
│   ├── crawler.py          # AsyncCrawler - main BFS crawl engine
│   ├── robots.py           # robots.txt fetching and compliance
│   ├── sitemap.py          # XML sitemap discovery and parsing
│   └── rate_limiter.py     # Token bucket per-domain rate limiter
├── analyzer/
│   └── analyzer.py         # Full SEO extraction (titles, meta, schema, etc.)
├── scorer/
│   └── scorer.py           # Multi-dimensional score computation
├── recommendations/
│   └── engine.py           # Issue detection + actionable fix generation
├── keyword_engine/
│   └── engine.py           # Keyword aggregation + opportunity scoring
├── api/
│   ├── routes.py           # All FastAPI endpoint handlers
│   ├── schemas.py          # Pydantic request/response models
│   └── middleware.py       # Rate limiting + request logging
├── database/
│   ├── models.py           # SQLAlchemy ORM models
│   ├── session.py          # Async session management
│   ├── repositories.py     # Repository pattern (data access layer)
│   └── schema.sql          # Raw SQL schema + indexes
└── workers/
    ├── celery_app.py        # Celery configuration + queue definitions
    ├── crawl_worker.py      # Main crawl orchestration task
    ├── analysis_worker.py   # Per-page re-analysis task
    └── report_worker.py     # Report generation task
```

---

## Testing

```bash
cd backend
source venv/bin/activate

# Run full test suite
pytest tests/ -v

# Test a single crawl via API
curl -X POST http://localhost:8000/api/v1/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "max_pages": 10}'

# Get the report after crawl completes
curl http://localhost:8000/api/v1/report/example.com
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `CRAWLER_MAX_CONCURRENT` | `100` | Max concurrent crawl requests |
| `CRAWLER_RATE_LIMIT_RPS` | `10` | Requests per second per domain |
| `CRAWLER_MAX_DEPTH` | `10` | Maximum crawl depth |
| `CELERY_WORKER_CONCURRENCY` | `8` | Celery worker concurrency |
| `SCORE_TECHNICAL_WEIGHT` | `0.35` | Technical score weight |
| `SCORE_CONTENT_WEIGHT` | `0.30` | Content score weight |

---

## Production Checklist

- [ ] Set `DEBUG=false` in backend `.env`
- [ ] Set a strong `SECRET_KEY` (32+ chars)
- [ ] Configure `CORS_ORIGINS` to your actual frontend URL
- [ ] Use a production PostgreSQL instance with SSL
- [ ] Use a managed Redis instance (ElastiCache, Upstash)
- [ ] Set up process managers: `systemd` or `supervisord` for uvicorn + celery
- [ ] Configure `nginx` as reverse proxy for uvicorn
- [ ] Set up log aggregation (Datadog, Loki, CloudWatch)
- [ ] Configure Prometheus metrics scraping (`/metrics` endpoint)
- [ ] Set up alerting on crawl job failures