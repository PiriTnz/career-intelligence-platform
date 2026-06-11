# Job Intelligence Platform

AI-powered job hunting platform for **Tanaz Piriaei** — AI/ML Engineer, Lyon, France.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite + TailwindCSS + React Query |
| Backend | FastAPI + Python 3.12 + SQLAlchemy (async) + Alembic |
| Database | PostgreSQL 16 |
| LLM | Ollama + Llama3 (local) / OpenAI (fallback) |
| Orchestration | n8n (triggers only — no business logic) |
| Deployment | Docker Compose |

## Quick start

```bash
cp .env.example .env        # fill in your secrets
docker compose up -d        # start all services
docker compose exec ollama ollama pull llama3

# Visit http://localhost:8000/docs  ← API + Swagger
# Visit http://localhost:3000       ← Frontend
# Visit http://localhost:5678       ← n8n
```

## Project structure

```
backend/
  app/
    api/v1/endpoints/   ← REST endpoints (one file per resource)
    agents/             ← 7 AI agents
    core/               ← config, security, database
    db/models/          ← SQLAlchemy models (10 tables)
    llm/                ← Ollama + OpenAI providers
    schemas/            ← Pydantic schemas
    services/           ← business logic (scoring, normalizer, etc.)
  alembic/              ← database migrations
frontend/
  src/
    api/                ← Axios calls to backend
    components/         ← shared UI components
    pages/              ← 8 pages (Login, Dashboard, …)
    types/              ← TypeScript interfaces
workflows/              ← n8n workflow JSON files (import into n8n)
docker/                 ← Postgres init SQL + Nginx config
docs/                   ← architecture, API reference, roadmap
scripts/                ← seed_profile, init_db, dev_start
```

## Agents

| # | Name | Purpose |
|---|------|---------|
| 0 | Profile Agent | Parse PDF CV → structured profile |
| 1 | Job Collection | France Travail + Adzuna → normalized jobs |
| 2 | Job Scoring | Deterministic score (LLM for explanation only) |
| 3 | CV Adaptation | ATS-optimized CV in fr/en per job |
| 4 | Cover Letter | cover_letter / motivation / email_hr |
| 5 | Feedback Learning | Learn from interview/reject outcomes |
| 6 | Opportunity Discovery | CIFRE, PhD, startup, MLOps leads |

## Scoring weights

| Dimension | Max |
|-----------|-----|
| Skill match | 30 |
| Experience match | 20 |
| Location / remote | 15 |
| Salary range | 15 |
| Contract type | 10 |
| Company quality | 5 |
| Freshness | 5 |
| **Total** | **100** |

Score ≥ 70 → shortlisted | Score < 40 → archived | Score ≥ 40 + confidence < 60% → needs_review

## Application status flow

```
found → shortlisted → cv_generated → approved → applied
     → viewed → replied → interview / rejected / archived
```

## Development phases

See [docs/development_roadmap.md](docs/development_roadmap.md).

**Phase 1** ✅ Full project structure  
**Phase 2** → Backend foundation (models, migrations, health endpoint)

## Core design rules

- LLM explains scores, never produces them
- n8n triggers only — zero business logic in workflows
- Human approval required before any application is sent
- All secrets in environment variables — nothing hardcoded
- Profile versioned — scores recalculated on profile change

## Docs

- [Architecture](docs/architecture.md)
- [API Reference](docs/api_reference.md)
- [Agents](docs/agents.md)
- [Setup Guide](docs/setup_guide.md)
- [Development Roadmap](docs/development_roadmap.md)
