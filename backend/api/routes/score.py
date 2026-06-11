from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.scorer import score_job
from core.llm import explain_score
import httpx
import os

router = APIRouter()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")


class ScoreRequest(BaseModel):
    job: dict
    profile: dict
    explain: bool = True


@router.post("/job")
async def score_single_job(req: ScoreRequest):
    breakdown, confidence = score_job(req.job, req.profile)
    result = {
        "breakdown": {
            "skill_match": breakdown.skill_match,
            "experience_match": breakdown.experience_match,
            "location_score": breakdown.location_score,
            "salary_score": breakdown.salary_score,
            "contract_score": breakdown.contract_score,
            "company_score": breakdown.company_score,
            "freshness_score": breakdown.freshness_score,
        },
        "total": breakdown.total,
        "extraction_confidence": confidence,
        "needs_review": breakdown.needs_review,
        "explanation": None,
    }
    if req.explain and breakdown.total >= 40:
        result["explanation"] = await explain_score(
            req.job, req.profile, breakdown, confidence
        )
    return result
