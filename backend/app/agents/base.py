from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentLog


class BaseAgent(ABC):
    name: str = "base"

    def __init__(self, db: AsyncSession, user_id: uuid.UUID):
        self.db = db
        self.user_id = user_id

    @abstractmethod
    async def run(self, **kwargs) -> dict:
        """Execute the agent and return a result dict."""

    async def _log(self, status: str, message: str, details: dict | None = None) -> None:
        entry = AgentLog(
            agent=self.name,
            user_id=self.user_id,
            status=status if status in ("ok", "error", "retry") else "ok",
            action=message,
            payload=details or {},
            error_msg=message if status == "error" else None,
        )
        self.db.add(entry)
        await self.db.flush()
