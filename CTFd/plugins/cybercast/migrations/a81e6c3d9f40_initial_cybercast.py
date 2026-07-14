"""Initial CyberCast profile and working-room tables.

Revision ID: a81e6c3d9f40
Revises:
Create Date: 2026-07-13 00:00:00.000000
"""

import sqlalchemy as sa

from CTFd.plugins.migrations import get_all_tables

revision = "a81e6c3d9f40"
down_revision = None
branch_labels = None
depends_on = None


def upgrade(op=None):
    tables = get_all_tables(op)

    if "cybercast_user_profiles" not in tables:
        op.create_table(
            "cybercast_user_profiles",
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("role", sa.String(length=16), nullable=False, server_default="student"),
            sa.Column("rating_points", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.CheckConstraint(
                "role IN ('student', 'expert', 'admin')",
                name="ck_cybercast_user_profile_role",
            ),
            sa.CheckConstraint(
                "rating_points >= 0", name="ck_cybercast_user_profile_rating"
            ),
        )

    if "cybercast_challenge_profiles" not in tables:
        op.create_table(
            "cybercast_challenge_profiles",
            sa.Column(
                "challenge_id",
                sa.Integer(),
                sa.ForeignKey("challenges.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("difficulty_tier", sa.String(length=32), nullable=False),
            sa.Column(
                "owner_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.CheckConstraint(
                "difficulty_tier IN ('sandbox_practice', 'enterprise_arena')",
                name="ck_cybercast_challenge_profile_tier",
            ),
        )

    if "cybercast_working_rooms" not in tables:
        op.create_table(
            "cybercast_working_rooms",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("room_token", sa.String(length=100), nullable=False, unique=True),
            sa.Column(
                "expert_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "challenge_id",
                sa.Integer(),
                sa.ForeignKey("challenges.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
            sa.CheckConstraint(
                "status IN ('active', 'completed')", name="ck_cybercast_room_status"
            ),
        )
        op.create_index(
            "ix_cybercast_rooms_challenge", "cybercast_working_rooms", ["challenge_id"]
        )

    if "cybercast_room_members" not in tables:
        op.create_table(
            "cybercast_room_members",
            sa.Column(
                "room_id",
                sa.Integer(),
                sa.ForeignKey("cybercast_working_rooms.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "joined_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index(
            "ix_cybercast_room_members_user", "cybercast_room_members", ["user_id"]
        )

    if "cybercast_room_submissions" not in tables:
        op.create_table(
            "cybercast_room_submissions",
            sa.Column(
                "submission_id",
                sa.Integer(),
                sa.ForeignKey("submissions.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "room_id",
                sa.Integer(),
                sa.ForeignKey("cybercast_working_rooms.id", ondelete="CASCADE"),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_cybercast_room_submissions_room",
            "cybercast_room_submissions",
            ["room_id"],
        )


def downgrade(op=None):
    pass
