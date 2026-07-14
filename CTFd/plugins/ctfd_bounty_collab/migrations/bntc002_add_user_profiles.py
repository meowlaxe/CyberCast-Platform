# =============================================================================
# File: CTFd/plugins/ctfd_bounty_collab/migrations/bntc002_add_user_profiles.py
# Plugin: ctfd_bounty_collab
# Created: 2026-07-15  Author: Claude / CyberCast implementation
# Purpose: Add bntc_user_profiles — stores each user's bounty-system role.
#          Revision ID: bntc002  |  down_revision: bntc001
#          Roles: student | expert | partner
# =============================================================================

import sqlalchemy as sa

revision = "bntc002"
down_revision = "bntc001"
branch_labels = None
depends_on = None


def upgrade(op=None):
    from CTFd.plugins.migrations import get_all_tables
    if "bntc_user_profiles" in get_all_tables(op):
        return  # idempotent

    op.create_table(
        "bntc_user_profiles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        # student | expert | partner
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("institution", sa.String(256)),
        sa.Column("created_at", sa.DateTime),
    )


def downgrade(op=None):
    op.drop_table("bntc_user_profiles")
