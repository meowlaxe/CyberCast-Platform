"""Initial CyberCast Student Teams tables

Revision ID: 8b2d41e9c3a7
Revises:
Create Date: 2026-07-11 00:00:00.000000
"""

import sqlalchemy as sa

from CTFd.plugins.migrations import get_all_tables

revision = "8b2d41e9c3a7"
down_revision = None
branch_labels = None
depends_on = None


def upgrade(op=None):
    tables = get_all_tables(op)

    if "st_teams" not in tables:
        op.create_table(
            "st_teams",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("name", sa.String(length=128), nullable=False, unique=True),
            sa.Column("slug", sa.String(length=128), nullable=False, unique=True),
            sa.Column("description", sa.Text()),
            sa.Column("avatar", sa.String(length=256)),
            sa.Column("banner", sa.String(length=256)),
            sa.Column("visibility", sa.String(length=32), nullable=False, server_default="public"),
            sa.Column("invite_code", sa.String(length=64), unique=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
        )

    if "st_team_members" not in tables:
        op.create_table(
            "st_team_members",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("team_id", sa.Integer(), sa.ForeignKey("st_teams.id", ondelete="CASCADE")),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
            sa.Column("role", sa.String(length=32), nullable=False, server_default="member"),
            sa.Column("joined_at", sa.DateTime()),
            sa.Column("left_at", sa.DateTime()),
            sa.UniqueConstraint("team_id", "user_id", name="uq_st_team_user"),
        )

    if "st_team_invites" not in tables:
        op.create_table(
            "st_team_invites",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("team_id", sa.Integer(), sa.ForeignKey("st_teams.id", ondelete="CASCADE")),
            sa.Column(
                "invited_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
            ),
            sa.Column("invited_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("expires_at", sa.DateTime()),
            sa.Column("resolved_at", sa.DateTime()),
            sa.UniqueConstraint(
                "team_id", "invited_user_id", "status", name="uq_st_active_invite"
            ),
        )

    if "st_team_join_requests" not in tables:
        op.create_table(
            "st_team_join_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("team_id", sa.Integer(), sa.ForeignKey("st_teams.id", ondelete="CASCADE")),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
            sa.Column("message", sa.String(length=512)),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("resolved_at", sa.DateTime()),
            sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.UniqueConstraint(
                "team_id", "user_id", "status", name="uq_st_active_join_request"
            ),
        )

    if "st_team_score_events" not in tables:
        op.create_table(
            "st_team_score_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("team_id", sa.Integer(), sa.ForeignKey("st_teams.id", ondelete="CASCADE")),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
            sa.Column("solve_id", sa.Integer(), sa.ForeignKey("solves.id", ondelete="CASCADE")),
            sa.Column(
                "challenge_id",
                sa.Integer(),
                sa.ForeignKey("challenges.id", ondelete="CASCADE"),
            ),
            sa.Column("category", sa.String(length=64)),
            sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("solve_date", sa.DateTime(), nullable=False),
            sa.Column("member_joined_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime()),
            sa.UniqueConstraint("solve_id", name="uq_st_score_event_solve"),
        )
        op.create_index(
            "ix_st_score_team_date", "st_team_score_events", ["team_id", "solve_date"]
        )
        op.create_index(
            "ix_st_score_user_date", "st_team_score_events", ["user_id", "solve_date"]
        )

    if "st_team_score_cache" not in tables:
        op.create_table(
            "st_team_score_cache",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "team_id",
                sa.Integer(),
                sa.ForeignKey("st_teams.id", ondelete="CASCADE"),
                unique=True,
            ),
            sa.Column("total_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("solve_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "last_score_event_id",
                sa.Integer(),
                sa.ForeignKey("st_team_score_events.id", ondelete="SET NULL"),
            ),
            sa.Column("updated_at", sa.DateTime()),
        )


def downgrade(op=None):
    pass
