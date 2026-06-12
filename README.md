# Career Intelligence Platform

An evidence-based AI career toolkit — CV adaptation, cover letter generation, interview workspace, and intelligent job matching.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite + TailwindCSS + React Query |
| Backend | FastAPI + Python 3.12 + SQLAlchemy 2.0 (async) + Alembic |
| Database | PostgreSQL 16 |
| LLM | Ollama + Llama3 (local) / OpenAI (fallback) |
| Orchestration | n8n (triggers only — no business logic) |
| Deployment | Docker Compose |

## Quick start

```bash
# 1. Clone and enter the project
git clone https://github.com/PiriTnz/career-intelligence-platform.git
cd career-intelligence-platform

# 2. Create your environment file
cp .env.example .env
# Edit .env — set SECRET_KEY and POSTGRES_PASSWORD (see below)

# 3. Start all services
docker compose up -d

# 4. Pull the local LLM model
docker compose exec ollama ollama pull llama3

# 5. Visit the app
#    Frontend:   http://localhost:3000
#    API + docs: http://localhost:8000/docs
#    n8n:        http://localhost:5678
```

> **Note:** Database migrations run automatically on backend startup via `alembic upgrade head`.
> To run them manually: `docker compose exec backend alembic upgrade head`

## Generating a secure SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Project structure

```
backend/
  app/
    api/v1/endpoints/   ← REST endpoints (one file per resource)
    agents/             ← AI agents (profile, scoring, CV, cover letter, interview)
    core/               ← config, security, database, rate limiter
    db/models/          ← SQLAlchemy models (20 tables, 5 migrations)
    llm/                ← Ollama + OpenAI providers
    schemas/            ← Pydantic schemas
    services/           ← business logic (scoring, matching, CV parser, etc.)
  alembic/              ← database migrations (0001 → 0005)
frontend/
  src/
    api/                ← Axios calls to backend
    components/         ← shared UI components
    pages/              ← pages (Login, Dashboard, Jobs, Applications, …)
    types/              ← TypeScript interfaces
workflows/              ← n8n workflow JSON files
docker/                 ← Postgres init SQL
docs/                   ← architecture, API reference, setup guide
scripts/                ← demo and seed scripts
```

## API endpoints (v1)

All endpoints are prefixed `/api/v1`. Full interactive docs at `/docs`.

| Resource | Method | Path | Description |
|----------|--------|------|-------------|
| Auth | POST | `/auth/register` | Create account |
| Auth | POST | `/auth/login` | Get JWT token |
| Profile | GET/POST/PUT | `/profiles/me` | Manage profile |
| Profile | POST | `/profiles/upload-cv` | Upload PDF CV |
| Profile | POST | `/profiles/assistant/message` | AI profile assistant |
| Jobs | GET | `/jobs` | List scored jobs |
| Jobs | GET | `/jobs/recommendations` | Personalized recommendations |
| Scores | POST | `/scores/{job_id}/compute` | Compute job score |
| Scores | POST | `/scores/{job_id}/explain` | LLM explanation |
| Scores | POST | `/scores/batch-compute` | Score all jobs |
| Applications | GET/POST | `/applications` | Manage applications |
| Applications | POST | `/applications/{job_id}/prepare` | Generate CV + cover letter |
| Interview | POST | `/interview/prepare/{job_id}` | Full interview workspace |
| Interview | GET | `/interview/workspace/{job_id}` | Get workspace |
| Interview | POST | `/interview/confirm-evidence` | Confirm skill evidence |
| Interview | GET | `/interview/knowledge-base` | View evidence KB |
| Interview | GET | `/interview/application-pipeline` | Full pipeline view |
| Opportunities | POST | `/opportunities/discover` | Discover non-job opportunities |

## API usage examples

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secure123", "name": "Jane"}'

# Login → get token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secure123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Get job recommendations
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/jobs/recommendations

# Prepare an interview workspace
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/interview/prepare/<job-uuid>
```

## Agents

| # | Name | Purpose |
|---|------|---------|
| 0 | Profile Agent | Parse PDF CV → structured profile |
| 1 | Job Collection | France Travail + Adzuna → normalized jobs |
| 2 | Job Scoring | Deterministic score (LLM for explanation only) |
| 3 | CV Adaptation | Evidence-based, ATS-optimized CV per job |
| 4 | Cover Letter | Evidence-based cover letter (4 skill tiers) |
| 5 | Feedback Learning | Learn from interview/reject outcomes |
| 6 | Opportunity Discovery | CIFRE, PhD, startup, MLOps leads |
| 7 | Interview Workspace | Readiness score, recruiter concerns, KB |

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

## Core design rules

1. **LLM explains scores, never produces them** — all scoring is deterministic
2. **Evidence-based CV only** — fabricated skills, employers, or degrees are forbidden
3. **n8n triggers only** — zero business logic in workflows
4. **Human approval required** before any application is sent
5. **All secrets in environment variables** — nothing hardcoded

## Running tests

Tests require no running PostgreSQL — all DB calls are mocked.

```bash
cd backend
.venv/bin/pytest --tb=short -q
```

Expected: **797 tests, 0 failures**

## Private beta checklist

Before inviting external users, verify:

- [ ] `SECRET_KEY` is a random 64-character hex string (not "changeme")
- [ ] `POSTGRES_PASSWORD` is a strong, unique password
- [ ] `APP_ENV=production` is set in the production `.env`
- [ ] `CORS_ORIGINS` lists only your production frontend domain(s)
- [ ] HTTPS is enabled (reverse proxy / load balancer with TLS termination)
- [ ] CV upload directory (`CV_UPLOAD_DIR`) points to a persistent, backed-up volume
- [ ] `N8N_PASSWORD` and `SERVICE_ACCOUNT_PASSWORD` are strong unique values
- [ ] Backend health check passes: `curl http://localhost:8000/health`
- [ ] All 5 Alembic migrations applied: `alembic upgrade head`
- [ ] Ollama model pulled: `ollama pull llama3`
- [ ] Backend logs contain no secrets, tokens, or CV content
- [ ] Rate limits verified: `/auth/register` (5/min), `/auth/login` (10/min), LLM endpoints (5-10/min)

## Docs

- [Architecture](docs/architecture.md)
- [API Reference](docs/api_reference.md)
- [Agents](docs/agents.md)
- [Setup Guide](docs/setup_guide.md)
- [Development Roadmap](docs/development_roadmap.md)
