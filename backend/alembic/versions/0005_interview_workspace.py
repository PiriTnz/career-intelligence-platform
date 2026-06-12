"""Interview Optimization Workspace — skill_evidence, evidence_pending, interview_workspaces.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── skill_evidence ─────────────────────────────────────────────────────────
    op.create_table(
        "skill_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("evidence_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "skill", name="uq_skill_evidence_user_skill"),
    )
    op.create_index("ix_skill_evidence_user_id", "skill_evidence", ["user_id"])
    op.create_index("ix_skill_evidence_status", "skill_evidence", ["status"])

    # ── evidence_pending ───────────────────────────────────────────────────────
    op.create_table(
        "evidence_pending",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill", sa.String(255), nullable=False),
        sa.Column("suggested_status", sa.String(20), nullable=False),
        sa.Column("agent_question", sa.Text(), nullable=False),
        sa.Column("agent_reasoning", sa.Text(), nullable=True),
        sa.Column("source_context", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evidence_pending_user_id", "evidence_pending", ["user_id"])

    # ── interview_workspaces ───────────────────────────────────────────────────
    op.create_table(
        "interview_workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("verified_matches", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("transferable_matches", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("learning_skills", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("real_gaps", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("recruiter_concerns", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("mitigation_strategies", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("cv_draft", sa.Text(), nullable=False, server_default=""),
        sa.Column("cover_letter_draft", sa.Text(), nullable=False, server_default=""),
        sa.Column("readiness_label", sa.String(20), nullable=False, server_default="weak"),
        sa.Column("readiness_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("readiness_explanation", sa.Text(), nullable=False, server_default=""),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "job_id", name="uq_iw_user_job"),
    )
    op.create_index("ix_iw_user_id", "interview_workspaces", ["user_id"])
    op.create_index("ix_iw_job_id", "interview_workspaces", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_iw_job_id", table_name="interview_workspaces")
    op.drop_index("ix_iw_user_id", table_name="interview_workspaces")
    op.drop_table("interview_workspaces")

    op.drop_index("ix_evidence_pending_user_id", table_name="evidence_pending")
    op.drop_table("evidence_pending")

    op.drop_index("ix_skill_evidence_status", table_name="skill_evidence")
    op.drop_index("ix_skill_evidence_user_id", table_name="skill_evidence")
    op.drop_table("skill_evidence")
