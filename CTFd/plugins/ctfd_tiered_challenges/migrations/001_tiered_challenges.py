# CTFd/plugins/ctfd_tiered_challenges_business/migrations/001_tiered_challenges.py
"""
Add tiered challenges tables

Revision ID: tier_001
Revises: None
Create Date: 2026-07-11
"""

from alembic import op
import sqlalchemy as sa


revision = "tier_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade(op=None):
    op.create_table(
        "cybercast_challenge_tiers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("tier_type", sa.String(32), nullable=False, server_default="community"),
        sa.Column("require_premium", sa.Boolean(), default=False),
        sa.Column("require_subscription_plan", sa.String(64)),
        sa.Column("bounty_program_id", sa.Integer()),
        sa.Column("bounty_reward_pool", sa.Numeric(12, 2)),
        sa.Column("bounty_platform_fee_pct", sa.Numeric(5, 2), server_default="10"),
        sa.Column("bounty_expert_pct", sa.Numeric(5, 2), server_default="90"),
        sa.Column("bounty_status", sa.String(32), server_default="draft"),
        sa.Column("enterprise_id", sa.Integer()),
        sa.Column("expert_reviewer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("description", sa.Text()),
        sa.Column("tags", sa.JSON()),
        sa.Column("difficulty_rating", sa.Float()),
        sa.Column("visibility", sa.String(32), server_default="public"),
        sa.Column("max_participants", sa.Integer()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["challenge_id"], ["challenges.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("challenge_id"),
    )
    
    op.create_table(
        "cybercast_bounty_solutions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("challenge_tier_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("attachment_url", sa.String(512)),
        sa.Column("submitted_at", sa.DateTime()),
        sa.Column("expert_review_status", sa.String(32), server_default="pending"),
        sa.Column("expert_feedback", sa.Text()),
        sa.Column("expert_reviewed_at", sa.DateTime()),
        sa.Column("is_awarded", sa.Boolean(), default=False),
        sa.Column("award_amount", sa.Numeric(12, 2)),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["challenge_tier_id"], ["cybercast_challenge_tiers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    
    op.create_table(
        "cybercast_challenge_access_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("challenge_tier_id", sa.Integer(), sa.ForeignKey("cybercast_challenge_tiers.id", ondelete="CASCADE")),
        sa.Column("access_granted", sa.Boolean()),
        sa.Column("denial_reason", sa.String(256)),
        sa.Column("user_subscription_status", sa.String(32)),
        sa.Column("created_at", sa.DateTime()),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_access_logs_user", "user_id"),
        sa.Index("ix_access_logs_challenge", "challenge_tier_id"),
    )


def downgrade(op=None):
    op.drop_table("cybercast_challenge_access_logs")
    op.drop_table("cybercast_bounty_solutions")
    op.drop_table("cybercast_challenge_tiers")
