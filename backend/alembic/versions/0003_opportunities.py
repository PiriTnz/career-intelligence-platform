"""Opportunity Discovery Agent — opportunities, preferences, feedback.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── opportunities ─────────────────────────────────────────────────────────
    op.create_table(
        "opportunities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("remote", sa.String(20), nullable=False, server_default="none"),
        sa.Column("opportunity_type", sa.String(100), nullable=False, server_default="employment"),
        sa.Column("industry", sa.String(255), nullable=True),
        sa.Column("sector", sa.String(255), nullable=True),
        sa.Column("contract_type", sa.String(50), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(10), nullable=False, server_default="EUR"),
        sa.Column("required_skills", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("experience_level", sa.String(50), nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_opp_source_id", "opportunities", ["source", "source_id"])
    op.create_index("ix_opp_type", "opportunities", ["opportunity_type"])
    op.create_index("ix_opp_is_active", "opportunities", ["is_active"])
    op.create_index("ix_opp_scraped_at", "opportunities", ["scraped_at"])

    # ── opportunity_preferences ────────────────────────────────────────────────
    op.create_table(
        "opportunity_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "preferred_opportunity_types",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "preferred_industries",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "preferred_sectors",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "preferred_locations",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "preferred_contract_types",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("keywords", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_opp_pref_user", "opportunity_preferences", ["user_id"], unique=True)

    # ── opportunity_feedback_events ────────────────────────────────────────────
    op.create_table(
        "opportunity_feedback_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("outcome", sa.String(50), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_opp_fb_user", "opportunity_feedback_events", ["user_id"])
    op.create_index("ix_opp_fb_opportunity", "opportunity_feedback_events", ["opportunity_id"])


def downgrade() -> None:
    op.drop_table("opportunity_feedback_events")
    op.drop_table("opportunity_preferences")
    op.drop_table("opportunities")
