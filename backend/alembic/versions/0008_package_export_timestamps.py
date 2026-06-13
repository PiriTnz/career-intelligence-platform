"""ApplicationPackage — add export timestamps.

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "application_packages",
        sa.Column("exported_cv_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "application_packages",
        sa.Column("exported_cover_letter_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("application_packages", "exported_cover_letter_at")
    op.drop_column("application_packages", "exported_cv_at")
