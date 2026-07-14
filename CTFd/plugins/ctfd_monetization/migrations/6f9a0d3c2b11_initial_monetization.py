"""Initial CyberCast monetization tables

Revision ID: 6f9a0d3c2b11
Revises:
Create Date: 2026-07-10 00:00:00.000000
"""

import sqlalchemy as sa

from CTFd.plugins.migrations import get_all_tables

revision = "6f9a0d3c2b11"
down_revision = None
branch_labels = None
depends_on = None


def upgrade(op=None):
    tables = get_all_tables(op)

    if "mon_subscriptions" not in tables:
        op.create_table(
            "mon_subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
            sa.Column("plan", sa.String(length=32), nullable=False, server_default="free"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("started_at", sa.DateTime()),
            sa.Column("current_period_start", sa.DateTime()),
            sa.Column("current_period_end", sa.DateTime()),
            sa.Column("cancelled_at", sa.DateTime()),
            sa.Column("provider", sa.String(length=64), nullable=False, server_default="manual"),
            sa.Column("provider_subscription_id", sa.String(length=128)),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
        )

    if "mon_invoices" not in tables:
        op.create_table(
            "mon_invoices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("invoice_number", sa.String(length=64), nullable=False, unique=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column(
                "enterprise_program_id",
                sa.Integer(),
                sa.ForeignKey("bnt_programs.id", ondelete="SET NULL"),
            ),
            sa.Column("purpose", sa.String(length=64), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=8), nullable=False, server_default="IDR"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("provider", sa.String(length=64), nullable=False, server_default="manual"),
            sa.Column("provider_invoice_id", sa.String(length=128)),
            sa.Column("payment_url", sa.String(length=512)),
            sa.Column("metadata_json", sa.Text()),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
            sa.Column("paid_at", sa.DateTime()),
        )

    if "mon_payment_history" not in tables:
        op.create_table(
            "mon_payment_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "invoice_id",
                sa.Integer(),
                sa.ForeignKey("mon_invoices.id", ondelete="CASCADE"),
            ),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("provider", sa.String(length=64), nullable=False, server_default="manual"),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=8), nullable=False, server_default="IDR"),
            sa.Column("raw_payload", sa.Text()),
            sa.Column("created_at", sa.DateTime()),
        )


def downgrade(op=None):
    pass
