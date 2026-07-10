"""Add enterprise payment gate fields

Revision ID: 4b83f2a901ef
Revises:
Create Date: 2026-07-10 00:00:00.000000
"""

import sqlalchemy as sa

from CTFd.plugins.migrations import get_all_tables, get_columns_for_table

revision = "4b83f2a901ef"
down_revision = None
branch_labels = None
depends_on = None


def upgrade(op=None):
    if "bnt_programs" not in get_all_tables(op):
        return
    columns = get_columns_for_table(op, "bnt_programs", names_only=True)
    if "review_status" not in columns:
        op.add_column("bnt_programs", sa.Column("review_status", sa.String(length=32)))
    if "payment_status" not in columns:
        op.add_column("bnt_programs", sa.Column("payment_status", sa.String(length=32)))
    if "invoice_id" not in columns:
        op.add_column("bnt_programs", sa.Column("invoice_id", sa.Integer()))


def downgrade(op=None):
    pass
