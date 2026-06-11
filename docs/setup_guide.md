# Setup Guide

## Prerequisites

- Docker Desktop (or Docker Engine + Compose)
- Git
- Python 3.12+ (for local dev without Docker)
- Node.js 20+ (for frontend dev without Docker)

## Quick start (Docker)

```bash
# 1. Clone and enter the project
git clone <repo>
cd job-hunter-phase1

# 2. Create your .env file
cp .env.example .env
# Edit .env — set real SECRET_KEY and API credentials

# 3. Start all services
docker compose up -d

# 4. Run database migrations
docker compose exec backend alembic upgrade head

# 5. Seed initial profile (Tanaz Piriaei)
docker compose exec backend python scripts/seed_profile.py

# 6. Pull Ollama model
docker compose exec ollama ollama pull llama3
```

## Services

| Service | URL | Notes |
|---------|-----|-------|
| Frontend | http://localhost:3000 | React dev server |
| Backend API | http://localhost:8000 | FastAPI + Swagger at /docs |
| n8n | http://localhost:5678 | Workflow orchestration |
| PostgreSQL | localhost:5432 | DB: jobhunter |
| Ollama | http://localhost:11434 | Local LLM |

## Environment variables

Copy `.env.example` to `.env` and fill in:

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | JWT signing key — generate with `openssl rand -hex 32` |
| `DATABASE_URL` | PostgreSQL DSN (default works with Docker) |
| `FRANCE_TRAVAIL_CLIENT_ID` | France Travail API credential |
| `FRANCE_TRAVAIL_CLIENT_SECRET` | France Travail API credential |
| `ADZUNA_APP_ID` | Adzuna API credential |
| `ADZUNA_API_KEY` | Adzuna API credential |
| `OPENAI_API_KEY` | Optional — Ollama used by default |
| `SERVICE_ACCOUNT_EMAIL` | n8n service account for workflow auth |
| `SERVICE_ACCOUNT_PASSWORD` | n8n service account password |

## Local backend development (without Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload
```

## Local frontend development (without Docker)

```bash
cd frontend
npm install
npm run dev
```

## Running the test suite

Tests require no running PostgreSQL — all DB calls are mocked.

```bash
cd backend

# If using the local venv (recommended — avoids Anaconda conflicts)
.venv/bin/python -m pytest

# Or inside Docker
docker compose exec backend python -m pytest
```

Coverage report:

```bash
.venv/bin/python -m pytest --cov=app --cov-report=term-missing
```

## Importing n8n workflows

1. Open n8n at http://localhost:5678
2. Create a service account matching `SERVICE_ACCOUNT_EMAIL` / `SERVICE_ACCOUNT_PASSWORD`
3. For each file in `workflows/`:
   - Click **+** → **Import from file**
   - Select the JSON file
   - Activate the workflow
4. Set n8n environment variables in **Settings → Variables**:
   - `BACKEND_URL` = `http://backend:8000`
   - `SERVICE_ACCOUNT_EMAIL`
   - `SERVICE_ACCOUNT_PASSWORD`
   - `NOTIFICATION_WEBHOOK_URL` (optional — Slack/email webhook)
