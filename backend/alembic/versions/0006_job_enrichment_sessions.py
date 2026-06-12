"""Job-Aware Profile Enrichment Agent — job_enrichment_sessions table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_enrichment_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # pending → answering → confirmed → enriched
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # List of { requirement, classification, rationale, via_skill?, via_family? }
        sa.Column("detected_gaps", postgresql.JSONB(), nullable=False, server_default="[]"),
        # List of { id, requirement, question, question_type, classification }
        sa.Column("generated_questions", postgresql.JSONB(), nullable=False, server_default="[]"),
        # List of { question_id, requirement, answer_text, evidence_type, suggested_status, answered_at }
        sa.Column("answers", postgresql.JSONB(), nullable=False, server_default="[]"),
        # List of { question_id, requirement, confirmed, evidence_note, suggested_status }
        sa.Column("confirmations", postgresql.JSONB(), nullable=False, server_default="[]"),
        # Skill names that were successfully added to skill_evidence after confirmation
        sa.Column("enriched_skills", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_jes_user_id", "job_enrichment_sessions", ["user_id"])
    op.create_index("ix_jes_job_id", "job_enrichment_sessions", ["job_id"])
    op.create_index("ix_jes_status", "job_enrichment_sessions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_jes_status", table_name="job_enrichment_sessions")
    op.drop_index("ix_jes_job_id", table_name="job_enrichment_sessions")
    op.drop_index("ix_jes_user_id", table_name="job_enrichment_sessions")
    op.drop_table("job_enrichment_sessions")
