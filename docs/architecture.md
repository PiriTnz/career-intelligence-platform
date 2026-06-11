# Architecture

## Component overview

```
┌─────────────────────────────────────────────────────────┐
│  Browser                                                │
│  React + TypeScript + Vite + TailwindCSS + React Query  │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / REST
┌────────────────────────▼────────────────────────────────┐
│  FastAPI  (backend:8000)                                │
│  ├── api/v1/  ← all business logic lives here          │
│  ├── agents/  ← 7 agents, called by API or n8n         │
│  ├── services/ ← scoring, normalization, LLM calls     │
│  ├── llm/    ← Ollama (primary) / OpenAI (fallback)    │
│  └── db/     ← SQLAlchemy async + PostgreSQL           │
└────────┬───────────────────────────────────────────────┘
         │ asyncpg
┌────────▼───────────────┐   ┌───────────────────────────┐
│  PostgreSQL:5432       │   │  Ollama:11434             │
│  (jobs, scores, apps)  │   │  (llama3 — local LLM)     │
└────────────────────────┘   └───────────────────────────┘
         ▲
┌────────┴───────────────┐
│  n8n:5678              │
│  Orchestration only:   │
│  - cron triggers       │
│  - HTTP calls to API   │
│  - notification flows  │
│  - human approval gate │
└────────────────────────┘
```

## Core rule

> Business logic MUST stay inside FastAPI services.  
> n8n MUST only trigger, schedule, and notify — never implement logic.

## Agent responsibilities

| # | Agent | Phase | Input | Output |
|---|-------|-------|-------|--------|
| 0 | Profile Agent | 6 | PDF CV | Structured profile in DB |
| 1 | Job Collection | 6 | API credentials | Normalized jobs in DB |
| 2 | Job Scoring | 6 | job_id + profile | Score record + explanation |
| 3 | CV Adaptation | 6 | job_id + profile | ATS CV file (fr/en) |
| 4 | Cover Letter | 6 | job_id + type | Cover letter record |
| 5 | Feedback Learning | 6 | application status | Adjusted weights |
| 6 | Opportunity Discovery | 6 | profile | CIFRE/PhD/startup leads |

## Scoring weights (deterministic)

| Dimension | Max |
|-----------|-----|
| Skill match | 30 |
| Experience match | 20 |
| Location | 15 |
| Salary | 15 |
| Contract type | 10 |
| Company quality | 5 |
| Freshness | 5 |
| **Total** | **100** |
