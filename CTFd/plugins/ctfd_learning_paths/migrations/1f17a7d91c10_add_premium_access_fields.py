"""Add premium access metadata to learning paths

Revision ID: 1f17a7d91c10
Revises:
Create Date: 2026-07-10 00:00:00.000000
"""

import sqlalchemy as sa

from CTFd.plugins.migrations import get_columns_for_table, get_all_tables

revision = "1f17a7d91c10"
down_revision = None
branch_labels = None
depends_on = None


def upgrade(op=None):
    tables = get_all_tables(op)
    if "lp_paths" in tables:
        columns = get_columns_for_table(op, "lp_paths", names_only=True)
        if "is_premium" not in columns:
            op.add_column("lp_paths", sa.Column("is_premium", sa.Boolean(), nullable=True))
        if "certificate_enabled" not in columns:
            op.add_column(
                "lp_paths", sa.Column("certificate_enabled", sa.Boolean(), nullable=True)
            )

    if "lp_steps" in tables:
        columns = get_columns_for_table(op, "lp_steps", names_only=True)
        if "is_premium" not in columns:
            op.add_column("lp_steps", sa.Column("is_premium", sa.Boolean(), nullable=True))
        if "lesson_type" not in columns:
            op.add_column(
                "lp_steps", sa.Column("lesson_type", sa.String(length=32), nullable=True)
            )


def downgrade(op=None):
    pass
