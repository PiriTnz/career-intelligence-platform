"""Add CV-extracted fields to profiles and create profile_versions table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Add CV-enrichment columns to profiles ─────────────────────────────────
    op.add_column("profiles", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column(
        "profiles",
        sa.Column(
            "certifications",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "profiles",
        sa.Column("education", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "profiles",
        sa.Column("experience", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column("profiles", sa.Column("cv_file_path", sa.String(500), nullable=True))

    # ── Create profile_versions table ─────────────────────────────────────────
    op.create_table(
        "profile_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("version", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(50), nullable=False, server_default="cv_upload"),
        sa.Column("cv_file_path", sa.String(500), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email_extracted", sa.String(255), nullable=True),
        sa.Column("location_raw", sa.String(255), nullable=True),
        sa.Column("education", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("experience", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "certifications",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "extracted_skills",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "inferred_skills",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "missing_fields",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "suggested_roles",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "extraction_confidence",
            sa.SmallInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_profile_versions_user_id", "profile_versions", ["user_id"])
    op.create_index(
        "ix_profile_versions_user_created",
        "profile_versions",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_profile_versions_user_created", table_name="profile_versions")
    op.drop_index("ix_profile_versions_user_id", table_name="profile_versions")
    op.drop_table("profile_versions")

    op.drop_column("profiles", "cv_file_path")
    op.drop_column("profiles", "experience")
    op.drop_column("profiles", "education")
    op.drop_column("profiles", "certifications")
    op.drop_column("profiles", "phone")
