# Development Roadmap

## Phase 1 — Project structure ✅
Full directory layout, configuration files, stubs for all modules.

## Phase 2 — Backend foundation ✅
- FastAPI app factory with lifespan
- pydantic-settings config from .env
- SQLAlchemy async engine + session
- All 10 SQLAlchemy models
- Alembic initial migration
- GET /health endpoint (DB + Ollama)
- Backend Docker service running

## Phase 3 — Authentication ✅
- POST /auth/register (email + hashed password)
- POST /auth/login → JWT access token
- GET /users/me — protected route
- Rate limiting on auth endpoints

## Phase 4 — Core job pipeline ✅
- Normalized job Pydantic schemas
- France Travail API client
- Adzuna API client
- Deduplication by URL + (company, title, location)
- Deterministic scoring service (100 pts, 7 dimensions)
- Save jobs + scores to PostgreSQL

## Phase 5 — LLM abstraction ✅
- BaseLLMProvider ABC
- OllamaProvider (calls local llama3)
- OpenAIProvider (fallback when OPENAI_API_KEY is set)
- Score explanation generation only (never affects scores)

## Phase 6 — Agents ✅
- Agent 0: Profile Agent (PDF CV parser)
- Agent 1: Job Collection Agent
- Agent 2: Job Scoring Agent
- Agent 3: CV Adaptation Agent (fr + en)
- Agent 4: Cover Letter Agent (3 types)
- Agent 5: Feedback Learning Agent
- Agent 6: Opportunity Discovery Agent

## Phase 7 — React frontend ✅
All pages (Dashboard, Jobs, Profile, Applications, CV, Cover Letters, Agent Logs, Settings)
implemented with React Query v5, AuthContext, ProtectedRoute.

## Phase 8 — n8n workflows ✅
4 workflows:
- `job_sync.json` — every 6h: collect + score
- `score_explanation.json` — on-demand LLM explanation
- `notification_flow.json` — hourly high-score alerts
- `human_approval.json` — webhook-driven CV/CL generation with wait node

## Phase 9 — Evidence-based application toolkit ✅
- Application Package Agent: 3-tier skill classification, ATS CV draft, cover letter
- Interview Optimization Workspace: 4-category evidence KB, readiness score, recruiter concerns
- Career Interview Agent: evidence questions, pending/confirm/reject flow
- 797 automated tests across 24 test files (0 failures)
- No PostgreSQL required for tests — DB mocked via AsyncMock

## Phase A — Production readiness (private beta) ✅
- Startup security gate: refuses to start with insecure defaults in production
- CORS origins read from CORS_ORIGINS env var
- Rate limiting on all LLM-backed endpoints
- Async PDF extraction (no longer blocks event loop)
- Removed `--reload` from production Dockerfile
- Alembic upgrade head runs via entrypoint before uvicorn
- `.dockerignore` prevents secrets/cache from image build
- .env.example sanitized (no real credentials)
- alembic.ini no longer contains credentials
- GitHub Actions CI (backend tests + frontend build)
- Inactive user raises 403 Forbidden (was 400)

## Phase B — MVP completion (next)
See [audit report](../AUDIT.md) for prioritized roadmap.
- Password reset flow
- Refresh tokens
- Background task queue for LLM calls
- Consolidated skill classification module
- Pagination on all list endpoints
