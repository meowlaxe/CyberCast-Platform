# =============================================================================
# File: CTFd/plugins/ctfd_bounty_collab/migrations/bntc001_create_tables.py
# Plugin: ctfd_bounty_collab
# Created: 2026-07-15  Author: Claude / CyberCast implementation
# Purpose: Initial migration — create all nine bntc_ tables.
#          Revision ID: bntc001  |  down_revision: None (first migration)
# =============================================================================

from alembic import op
import sqlalchemy as sa

revision = "bntc001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade(op=None):
    from CTFd.plugins.migrations import get_all_tables
    existing = get_all_tables(op)
    if "bntc_projects" in existing:
        return  # already applied — idempotent

    op.create_table(
        "bntc_projects",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("category", sa.String(64)),
        sa.Column("problem_statement", sa.Text, nullable=False),
        sa.Column("scope_of_work", sa.Text),
        sa.Column("deliverables", sa.Text),
        sa.Column("required_expertise", sa.String(512)),
        sa.Column("team_size_min", sa.Integer, server_default="1"),
        sa.Column("team_size_max", sa.Integer, server_default="5"),
        sa.Column("application_deadline", sa.DateTime),
        sa.Column("research_duration_days", sa.Integer),
        sa.Column("budget_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_nda_required", sa.Boolean, server_default=sa.false()),
        sa.Column("nda_full_brief", sa.Text),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invoice_id", sa.Integer, sa.ForeignKey("mon_invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )

    op.create_table(
        "bntc_applications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("bntc_projects.id", ondelete="CASCADE")),
        sa.Column("applicant_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("team_name", sa.String(128)),
        sa.Column("cover_note", sa.Text),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime),
    )

    op.create_table(
        "bntc_team_members",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("bntc_projects.id", ondelete="CASCADE")),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_team_lead", sa.Boolean, server_default=sa.false()),
        sa.Column("payout_percentage", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("joined_at", sa.DateTime),
    )

    op.create_table(
        "bntc_nda_acceptances",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("bntc_projects.id", ondelete="CASCADE")),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("accepted_at", sa.DateTime),
        sa.UniqueConstraint("project_id", "user_id", name="uq_bntc_nda"),
    )

    op.create_table(
        "bntc_deliverables",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("bntc_projects.id", ondelete="CASCADE")),
        sa.Column("submitted_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content", sa.Text),
        sa.Column("file_ref", sa.String(512)),
        sa.Column("version_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="submitted"),
        sa.Column("reviewer_note", sa.Text),
        sa.Column("created_at", sa.DateTime),
    )

    op.create_table(
        "bntc_escrow_ledger",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("bntc_projects.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("total_funded", sa.Integer, nullable=False, server_default="0"),
        sa.Column("platform_commission_amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("researcher_pool_amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="unfunded"),
        sa.Column("funded_at", sa.DateTime),
        sa.Column("released_at", sa.DateTime),
    )

    op.create_table(
        "bntc_wallets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("pending_balance", sa.Integer, nullable=False, server_default="0"),
        sa.Column("internal_balance", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime),
    )

    op.create_table(
        "bntc_wallet_transactions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("wallet_id", sa.Integer, sa.ForeignKey("bntc_wallets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("bntc_projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("balance_after", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime),
    )

    op.create_table(
        "bntc_audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("bntc_projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("before_state", sa.JSON),
        sa.Column("after_state", sa.JSON),
        sa.Column("created_at", sa.DateTime),
    )


def downgrade(op=None):
    op.drop_table("bntc_audit_log")
    op.drop_table("bntc_wallet_transactions")
    op.drop_table("bntc_wallets")
    op.drop_table("bntc_escrow_ledger")
    op.drop_table("bntc_deliverables")
    op.drop_table("bntc_nda_acceptances")
    op.drop_table("bntc_team_members")
    op.drop_table("bntc_applications")
    op.drop_table("bntc_projects")
