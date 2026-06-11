# API Reference

Base URL: `http://localhost:8000/api/v1`  
Interactive docs: `http://localhost:8000/docs`

## Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /auth/register | — | Create account |
| POST | /auth/login | — | Get JWT token |
| GET | /users/me | JWT | Current user |

## Jobs

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /jobs | JWT | List jobs with scores |
| GET | /jobs/{id} | JWT | Job detail |

## Profiles

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /profiles/me | JWT | Active profile |
| PUT | /profiles/me | JWT | Update profile |

## Applications

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /applications | JWT | All applications |
| POST | /applications | JWT | Create application |
| PATCH | /applications/{id} | JWT | Update status/notes |

## CV Versions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /cv-versions | JWT | List all CVs |
| POST | /cv-versions | JWT | Generate CV for job |

## Cover Letters

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /cover-letters | JWT | List all letters |
| POST | /cover-letters | JWT | Generate letter |

## Agents

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /agents/{name}/run | JWT | Trigger an agent |
| GET | /agents/logs | JWT | Recent agent logs |

## Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | — | DB + Ollama status |
