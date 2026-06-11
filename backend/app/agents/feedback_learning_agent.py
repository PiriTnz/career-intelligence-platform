"""
Agent 5 — Feedback Learning Agent.
Analyses outcome history and surfaces profile improvement suggestions.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.services.feedback_service import compute_insights


class FeedbackLearningAgent(BaseAgent):
    name = "feedback_learning_agent"

    async def run(self, **kwargs) -> dict:
        await self._log("started", "Analysing feedback history")

        try:
            insights = await compute_insights(self.db, self.user_id)
            await self._log(
                "completed",
                f"Feedback analysis done — {insights['total_events']} events",
                {"insights_count": len(insights.get("insights", []))},
            )
            await self.db.commit()
            return {"success": True, **insights}
        except Exception as exc:
            await self._log("error", f"Feedback analysis failed: {exc}")
            await self.db.commit()
            return {"success": False, "error": str(exc)}
