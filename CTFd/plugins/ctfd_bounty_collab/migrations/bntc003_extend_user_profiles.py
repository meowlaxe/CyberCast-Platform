# =============================================================================
# File: CTFd/plugins/ctfd_bounty_collab/migrations/bntc003_extend_user_profiles.py
# Plugin: ctfd_bounty_collab
# Created: 2026-07-15  Author: Claude / CyberCast implementation
# Purpose: Add expert credential fields to bntc_user_profiles.
#          Revision ID: bntc003  |  down_revision: bntc002
# =============================================================================

import sqlalchemy as sa

revision = "bntc003"
down_revision = "bntc002"
branch_labels = None
depends_on = None


def upgrade(op=None):
    from CTFd.plugins.migrations import get_all_tables

    # Check if columns already exist by inspecting the table
    try:
        conn = op.get_bind()
        result = conn.execute(
            sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='bntc_user_profiles'")
        )
        existing_cols = {row[0] for row in result}
    except Exception:
        existing_cols = set()

    if "bntc_user_profiles" not in get_all_tables(op):
        return  # table not yet created — bntc002 will handle it

    if "bio" not in existing_cols:
        op.add_column("bntc_user_profiles", sa.Column("bio", sa.Text))
    if "expertise_areas" not in existing_cols:
        op.add_column("bntc_user_profiles", sa.Column("expertise_areas", sa.String(512)))
    if "profile_url" not in existing_cols:
        op.add_column("bntc_user_profiles", sa.Column("profile_url", sa.String(512)))
    if "credential_id" not in existing_cols:
        op.add_column("bntc_user_profiles", sa.Column("credential_id", sa.String(128)))


def downgrade(op=None):
    op.drop_column("bntc_user_profiles", "bio")
    op.drop_column("bntc_user_profiles", "expertise_areas")
    op.drop_column("bntc_user_profiles", "profile_url")
    op.drop_column("bntc_user_profiles", "credential_id")
