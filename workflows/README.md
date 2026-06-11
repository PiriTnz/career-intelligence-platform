# n8n Workflows

## Setup

1. Start the stack: `docker compose up -d`
2. Open n8n at http://localhost:5678 (login: admin / changeme)
3. Import each JSON via **Workflows → Import from file**
4. Activate the workflows you want to run on schedule

## Credentials required

n8n uses the `SERVICE_ACCOUNT_EMAIL` and `SERVICE_ACCOUNT_PASSWORD` env vars
to authenticate against the backend. These are set in `.env` and passed to
the n8n container in `docker-compose.yml`.

The service account must already exist as a registered user in the backend.
Run `docker compose exec backend python scripts/seed_profile.py` to create it.

## Workflow reference

### 1. `job_sync.json` — Job Sync (scheduled)
**Trigger:** Every 6 hours (cron)  
**Flow:**
```
Schedule → Login → Collect Jobs → [IF fetched > 0] → Score New Jobs → Log
                                                    ↘ No New Jobs (skip)
```
**What it does:**
- Calls `POST /api/v1/agents/job_collection_agent/run` with AI/ML keywords
- If any jobs were fetched, immediately calls `POST /api/v1/agents/job_scoring_agent/run`

---

### 2. `score_explanation.json` — Score & Explain (webhook)
**Trigger:** `POST http://localhost:5678/webhook/score-explain`  
**Body:** `{ "job_id": "<uuid>" }`  
**Flow:**
```
Webhook → Validate → Login → Score Jobs → Generate Explanation → Respond
```
**What it does:**
- Scores any unscored jobs for the service account user
- Calls `POST /api/v1/scores/{job_id}/explain` to generate the LLM explanation
- Returns the explanation in the webhook response

---

### 3. `notification_flow.json` — High Score Notifications (scheduled)
**Trigger:** Every hour (cron)  
**Requires:** `NOTIFICATION_WEBHOOK_URL` set to a Slack/Discord incoming webhook  
**Flow:**
```
Schedule → Login → GET /jobs?min_score=75 → Filter (scraped last hour)
  → [IF new high-score] → Format message → POST to NOTIFICATION_WEBHOOK_URL
                       ↘ Skip
```
**What it does:**
- Checks for jobs scored ≥ 75 scraped in the past hour
- Posts a formatted alert to your Slack/Discord channel

**To enable:** Set `NOTIFICATION_WEBHOOK_URL` in `.env`, then restart n8n.

---

### 4. `human_approval.json` — Human Approval (webhook + wait)
**Trigger:** `POST http://localhost:5678/webhook/approve-cv`  
**Body:** `{ "job_id": "<uuid>", "application_id": "<uuid>", "language": "fr", "letter_type": "cover_letter" }`  
**Flow:**
```
Webhook → Validate → Login → Get Job → Prepare Summary
  → Acknowledge (respond immediately) + Wait for human approval
  → [POST /approval?approved=true] → Check Approval
  → Generate CV + Generate Cover Letter (parallel)
  → Update Application Status → Done
```
**What it does:**
1. Frontend/user POSTs a request to generate CV + letter for a job
2. Workflow responds immediately with `{ status: "pending_approval", resume_url: "..." }`
3. The **Tanaz** approves by calling the `resume_url` with `?approved=true`
4. CV Adaptation Agent + Cover Letter Agent run in parallel
5. Application status is set to `cv_generated`

**Approval call:**  
```
curl -X POST "<resume_url>&approved=true"
```

## Architecture rule

**n8n contains zero business logic.**  
Every workflow is: trigger → auth → call FastAPI endpoint → optional notify.  
All scoring, generation, and data manipulation stays in the Python backend.
