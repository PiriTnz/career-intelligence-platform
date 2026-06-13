"""Application Tracker — timeline table + new timestamp fields.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new timestamp fields to applications
    op.add_column("applications", sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column("offer_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))

    # Create application_timeline table
    op.create_table(
        "application_timeline",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_atl_application_id", "application_timeline", ["application_id"])
    op.create_index("ix_atl_created_at", "application_timeline", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_atl_created_at", table_name="application_timeline")
    op.drop_index("ix_atl_application_id", table_name="application_timeline")
    op.drop_table("application_timeline")
    op.drop_column("applications", "rejected_at")
    op.drop_column("applications", "offer_at")
    op.drop_column("applications", "follow_up_at")
