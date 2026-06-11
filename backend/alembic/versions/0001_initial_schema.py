"""Initial schema — all tables.

Revision ID: 0001
Revises:
Create Date: 2026-06-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── profiles ─────────────────────────────────────────────────────────────
    op.create_table(
        "profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("target_roles", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("avoid_roles", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("skills", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("experience_level", sa.String(50), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_target", sa.Integer(), nullable=True),
        sa.Column("remote_preference", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("countries", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("cities", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("contract_types", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("languages", postgresql.ARRAY(sa.String()), nullable=False, server_default="'{fr,en}'"),
        sa.Column("raw_json", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── companies ────────────────────────────────────────────────────────────
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("size", sa.String(50), nullable=True),
        sa.Column("quality_score", sa.SmallInteger(), nullable=False, server_default="50"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_companies_name", "companies", ["name"], unique=True)

    # ── jobs ─────────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("remote", sa.String(20), nullable=False, server_default="none"),
        sa.Column("contract_type", sa.String(50), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(10), nullable=False, server_default="EUR"),
        sa.Column("required_skills", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("experience_level", sa.String(50), nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="fr"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_url", "jobs", ["url"], unique=True)
    op.create_index("idx_jobs_source", "jobs", ["source"])
    op.create_index("idx_jobs_scraped_at", "jobs", ["scraped_at"])
    op.create_index("idx_jobs_contract_type", "jobs", ["contract_type"])

    # ── applications ─────────────────────────────────────────────────────────
    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="found"),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interview_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "job_id", name="uq_application_user_job"),
    )
    op.create_index("idx_applications_status", "applications", ["status"])
    op.create_index("idx_applications_user", "applications", ["user_id"])

    # ── scores ───────────────────────────────────────────────────────────────
    op.create_table(
        "scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("skill_match", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("experience_match", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("location_score", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("salary_score", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("contract_score", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("company_score", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("freshness_score", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("total", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("extraction_confidence", sa.SmallInteger(), nullable=False, server_default="100"),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("llm_explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("job_id", "user_id", name="uq_score_job_user"),
    )

    # ── cv_versions ──────────────────────────────────────────────────────────
    op.create_table(
        "cv_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="fr"),
        sa.Column("ats_score", sa.SmallInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── cover_letters ────────────────────────────────────────────────────────
    op.create_table(
        "cover_letters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("type", sa.String(50), nullable=False, server_default="cover_letter"),
        sa.Column("language", sa.String(10), nullable=False, server_default="fr"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── feedback_events ──────────────────────────────────────────────────────
    op.create_table(
        "feedback_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("outcome", sa.String(50), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_feedback_user", "feedback_events", ["user_id"])
    op.create_index("idx_feedback_outcome", "feedback_events", ["outcome"])

    # ── agent_logs ───────────────────────────────────────────────────────────
    op.create_table(
        "agent_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("agent", sa.String(100), nullable=False),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ok"),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_agent_logs_agent", "agent_logs", ["agent"])
    op.create_index("idx_agent_logs_created", "agent_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("agent_logs")
    op.drop_table("feedback_events")
    op.drop_table("cover_letters")
    op.drop_table("cv_versions")
    op.drop_table("scores")
    op.drop_table("applications")
    op.drop_table("jobs")
    op.drop_table("companies")
    op.drop_table("profiles")
    op.drop_table("users")
