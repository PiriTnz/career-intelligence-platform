import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AgentLog(Base):
    __tablename__ = "agent_logs"
    __table_args__ = (
        Index("idx_agent_logs_agent", "agent"),
        Index("idx_agent_logs_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    agent: Mapped[str] = mapped_column(String(100), nullable=False)
    # profile_agent, job_collection, job_scoring, cv_adaptation, cover_letter,
    # feedback_learning, opportunity_discovery

    action: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok, error, retry
    error_msg: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
