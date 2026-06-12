"""Application Package Agent — application_packages table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_packages",
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
        sa.Column("cv_draft", sa.Text(), nullable=False, server_default=""),
        sa.Column("cover_letter_draft", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "requirement_analysis",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "ready_to_apply_score", sa.Integer(), nullable=False, server_default="0"
        ),
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
        sa.UniqueConstraint("user_id", "job_id", name="uq_app_pkg_user_job"),
    )
    op.create_index("ix_app_pkg_user_id", "application_packages", ["user_id"])
    op.create_index("ix_app_pkg_job_id", "application_packages", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_app_pkg_job_id", table_name="application_packages")
    op.drop_index("ix_app_pkg_user_id", table_name="application_packages")
    op.drop_table("application_packages")
