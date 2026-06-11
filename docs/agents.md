# Agents Reference

All agents are FastAPI services. n8n calls them via HTTP — it never contains agent logic.

## Agent 0 — Profile Agent
**Trigger**: POST /api/v1/agents/profile_agent/run  
**Input**: multipart PDF upload or form data  
**Output**: Profile record in DB

## Agent 1 — Job Collection Agent
**Trigger**: POST /api/v1/agents/job_collection_agent/run (n8n cron: every 6h)  
**Sources**: France Travail API, Adzuna API  
**Output**: Normalized Job records + deduplication

## Agent 2 — Job Scoring Agent
**Trigger**: POST /api/v1/agents/job_scoring_agent/run  
**Logic**: 100% deterministic weighted scoring  
**LLM use**: explanation text only, never affects the score  
**Output**: Score records with optional llm_explanation

## Agent 3 — CV Adaptation Agent
**Trigger**: POST /api/v1/agents/cv_adaptation_agent/run  
**Input**: job_id, language (fr|en), profile  
**Output**: ATS-optimized CV file stored, CVVersion record

## Agent 4 — Cover Letter Agent
**Trigger**: POST /api/v1/agents/cover_letter_agent/run  
**Types**: cover_letter, motivation, email_hr  
**Output**: CoverLetter record (content as text)

## Agent 5 — Feedback Learning Agent
**Trigger**: application status change (applied/interview/rejected)  
**Output**: FeedbackEvent records, adjusted scoring weights in profile

## Agent 6 — Opportunity Discovery Agent
**Trigger**: POST /api/v1/agents/opportunity_discovery_agent/run  
**Targets**: CIFRE, PhD, Research Engineer, MLOps, startup, AI Engineer  
**Output**: Job records tagged with opportunity type
