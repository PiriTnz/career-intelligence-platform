from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import asyncpg
import os
import json

router = APIRouter()
DB_URL = os.getenv("DATABASE_URL")


class JobUpsert(BaseModel):
    source: str
    url: str
    title: str
    company_name: str
    location: Optional[str] = None
    contract_type: Optional[str] = None
    remote: Optional[str] = "none"
    required_skills: Optional[list] = []
    experience_level: Optional[str] = None
    language: Optional[str] = "fr"
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    description: Optional[str] = None
    published_at: Optional[str] = None
    score: Optional[dict] = None
    status: Optional[str] = "found"


@router.post("/upsert")
async def upsert_job(job: JobUpsert):
    conn = await asyncpg.connect(DB_URL)
    try:
        # Upsert job
        row = await conn.fetchrow("""
            INSERT INTO jobs (
                source, url, title, company_name, location,
                contract_type, remote, required_skills, experience_level,
                language, salary_min, salary_max, description, published_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
            ON CONFLICT (url) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                required_skills = EXCLUDED.required_skills,
                salary_min = EXCLUDED.salary_min,
                salary_max = EXCLUDED.salary_max
            RETURNING id
        """,
            job.source, job.url, job.title, job.company_name, job.location,
            job.contract_type, job.remote, job.required_skills, job.experience_level,
            job.language, job.salary_min, job.salary_max, job.description, job.published_at
        )
        job_id = row["id"]

        # Save score (user_id = NULL for now, Phase 1)
        if job.score:
            s = job.score
            await conn.execute("""
                INSERT INTO scores (
                    job_id, user_id, profile_version,
                    skill_match, experience_match, location_score,
                    salary_score, contract_score, company_score, freshness_score,
                    extraction_confidence, needs_review
                ) VALUES ($1,NULL,1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                ON CONFLICT (job_id, user_id) DO NOTHING
            """,
                job_id,
                s.get("skill_match", 0), s.get("experience_match", 0),
                s.get("location_score", 0), s.get("salary_score", 0),
                s.get("contract_score", 0), s.get("company_score", 0),
                s.get("freshness_score", 0),
                s.get("extraction_confidence", 50),
                s.get("needs_review", False)
            )

        # Log event
        await conn.execute("""
            INSERT INTO event_logs (agent, action, payload, status)
            VALUES ('scraper', 'upsert_job', $1, 'ok')
        """, json.dumps({"job_id": str(job_id), "title": job.title, "status": job.status}))

        return {"job_id": str(job_id), "status": job.status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await conn.close()


@router.get("/")
async def list_jobs(status: Optional[str] = None, limit: int = 50):
    conn = await asyncpg.connect(DB_URL)
    try:
        if status:
            rows = await conn.fetch("""
                SELECT j.*, s.total as score_total, s.needs_review
                FROM jobs j
                LEFT JOIN scores s ON s.job_id = j.id
                ORDER BY s.total DESC NULLS LAST, j.scraped_at DESC
                LIMIT $1
            """, limit)
        else:
            rows = await conn.fetch("""
                SELECT j.*, s.total as score_total, s.needs_review
                FROM jobs j
                LEFT JOIN scores s ON s.job_id = j.id
                ORDER BY s.total DESC NULLS LAST, j.scraped_at DESC
                LIMIT $1
            """, limit)
        return [dict(r) for r in rows]
    finally:
        await conn.close()
