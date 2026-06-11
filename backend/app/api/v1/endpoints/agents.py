"""
POST /agents/{name}/run — trigger any agent by name.
GET  /agents/logs      — retrieve recent AgentLog entries.

Callable by the frontend or n8n webhooks.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.db.models import AgentLog, User
from app.llm import get_provider

router = APIRouter()

_AGENT_NAMES = {
    "profile_agent",
    "job_collection_agent",
    "job_scoring_agent",
    "cv_adaptation_agent",
    "cover_letter_agent",
    "feedback_learning_agent",
    "opportunity_discovery_agent",
}


class AgentRunRequest(BaseModel):
    params: dict[str, Any] = {}


class AgentRunResponse(BaseModel):
    agent: str
    result: dict[str, Any]


class AgentLogRead(BaseModel):
    id: int
    agent: str
    status: str
    action: str
    payload: dict | None
    created_at: Any

    class Config:
        from_attributes = True


@router.post("/{agent_name}/run", response_model=AgentRunResponse)
async def run_agent(
    agent_name: str,
    body: AgentRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentRunResponse:
    if agent_name not in _AGENT_NAMES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown agent '{agent_name}'. Available: {sorted(_AGENT_NAMES)}",
        )

    provider = get_provider()
    params = body.params

    try:
        result = await _dispatch(agent_name, db=db, user_id=current_user.id, provider=provider, params=params)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return AgentRunResponse(agent=agent_name, result=result)


@router.get("/logs", response_model=list[AgentLogRead])
async def get_agent_logs(
    limit: int = Query(default=50, le=200),
    agent_name: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AgentLogRead]:
    query = (
        select(AgentLog)
        .where(AgentLog.user_id == current_user.id)
        .order_by(AgentLog.created_at.desc())
        .limit(limit)
    )
    if agent_name:
        query = query.where(AgentLog.agent == agent_name)
    result = await db.execute(query)
    return list(result.scalars().all())


async def _dispatch(
    agent_name: str,
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    provider: Any,
    params: dict,
) -> dict:
    if agent_name == "profile_agent":
        from app.agents.profile_agent import ProfileAgent
        return await ProfileAgent(db, user_id, provider).run(**params)

    if agent_name == "job_collection_agent":
        from app.agents.job_collection_agent import JobCollectionAgent
        return await JobCollectionAgent(db, user_id).run(**params)

    if agent_name == "job_scoring_agent":
        from app.agents.job_scoring_agent import JobScoringAgent
        return await JobScoringAgent(db, user_id).run(**params)

    if agent_name == "cv_adaptation_agent":
        from app.agents.cv_adaptation_agent import CVAdaptationAgent
        raw_job_id = params.pop("job_id", None)
        if not raw_job_id:
            return {"success": False, "error": "job_id required"}
        return await CVAdaptationAgent(db, user_id, provider).run(job_id=uuid.UUID(str(raw_job_id)), **params)

    if agent_name == "cover_letter_agent":
        from app.agents.cover_letter_agent import CoverLetterAgent
        raw_job_id = params.pop("job_id", None)
        if not raw_job_id:
            return {"success": False, "error": "job_id required"}
        return await CoverLetterAgent(db, user_id, provider).run(job_id=uuid.UUID(str(raw_job_id)), **params)

    if agent_name == "feedback_learning_agent":
        from app.agents.feedback_learning_agent import FeedbackLearningAgent
        return await FeedbackLearningAgent(db, user_id).run(**params)

    if agent_name == "opportunity_discovery_agent":
        from app.agents.opportunity_discovery_agent import OpportunityDiscoveryAgent
        return await OpportunityDiscoveryAgent(db, user_id).run(**params)

    return {"success": False, "error": "Unreachable"}
