# CTFd/plugins/ctfd_tiered_challenges_business/models.py
"""
CyberCast Tiered Challenges - Business Model Implementation
==========================================================

Implements the 3-tier challenge system:
1. Community Challenges (Free) - CTFd challenges
2. Premium Learning Path Challenges - Requires subscription
3. Enterprise Bounty Challenges - Real problems from enterprises (90/10 split)

References the money flow diagram:
- Enterprise deposits bounty → CyberCast creates invoice
- Students solve → Expert verifies → Bounty released
- 90% → Expert, 10% → CyberCast platform fee
"""

import datetime
from decimal import Decimal
from CTFd.models import db


class ChallengeTierType:
    """Challenge tier classification"""
    COMMUNITY = "community"  # Free, public, educational
    PREMIUM = "premium"      # Requires subscription
    BOUNTY = "bounty"        # Enterprise-backed, reward pool


class BountyStatus:
    """Bounty project lifecycle status"""
    DRAFT = "draft"                    # Enterprise creating proposal
    AWAITING_PAYMENT = "awaiting_payment"  # Invoice generated, awaiting payment
    FUNDED = "funded"                  # Enterprise paid full bounty
    ACTIVE = "active"                  # Published, students can solve
    IN_REVIEW = "in_review"            # Solutions submitted, expert reviewing
    AWARDED = "awarded"                # Winner selected, pending payout
    COMPLETED = "completed"            # Payout distributed
    CANCELLED = "cancelled"            # Enterprise or CyberCast cancelled


class ChallengeTier(db.Model):
    """Challenge tier metadata - links CTFd challenges to CyberCast business tier"""
    __tablename__ = "cybercast_challenge_tiers"
    id = db.Column(db.Integer, primary_key=True)
    
    # Core reference
    challenge_id = db.Column(
        db.Integer,
        db.ForeignKey("challenges.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    
    # Tier classification
    tier_type = db.Column(
        db.String(32),
        nullable=False,
        default=ChallengeTierType.COMMUNITY
    )
    
    # Premium/Bounty metadata
    require_premium = db.Column(db.Boolean, default=False)
    require_subscription_plan = db.Column(db.String(64))  # "premium", "enterprise"
    
    # Bounty-specific fields (links to ctfd_bounty)
    bounty_program_id = db.Column(db.Integer)  # Reference to BountyPrograms
    bounty_reward_pool = db.Column(db.Numeric(12, 2))  # Total prize USD
    bounty_platform_fee_pct = db.Column(db.Numeric(5, 2), default=Decimal("10"))  # 10%
    bounty_expert_pct = db.Column(db.Numeric(5, 2), default=Decimal("90"))  # 90%
    bounty_status = db.Column(
        db.String(32),
        default=BountyStatus.DRAFT
    )
    
    # Enterprise metadata
    enterprise_id = db.Column(db.Integer)  # Reference to enterprise user
    expert_reviewer_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL")
    )  # Expert validating solution
    
    # Metadata
    description = db.Column(db.Text)  # Why this challenge matters
    tags = db.Column(db.JSON)  # ["web", "cryptography", "2025-q1"]
    difficulty_rating = db.Column(db.Float)  # 1-5
    
    # Visibility & access control
    visibility = db.Column(db.String(32), default="public")  # public, unlisted, private
    max_participants = db.Column(db.Integer)  # Limit to N students
    
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow
    )
    
    challenge = db.relationship("Challenges", backref="tier_info", uselist=False)
    expert_reviewer = db.relationship("Users", foreign_keys=[expert_reviewer_id])
    
    def __repr__(self):
        return f"<ChallengeTier challenge_id={self.challenge_id} tier={self.tier_type}>"
    
    @property
    def is_active_bounty(self):
        """Bounty is accepting solutions"""
        return (
            self.tier_type == ChallengeTierType.BOUNTY
            and self.bounty_status == BountyStatus.ACTIVE
        )
    
    @property
    def expert_reward(self):
        """Calculate expert's share (90%)"""
        if not self.bounty_reward_pool:
            return Decimal("0")
        return self.bounty_reward_pool * (self.bounty_expert_pct / 100)
    
    @property
    def platform_fee(self):
        """Calculate CyberCast's platform fee (10%)"""
        if not self.bounty_reward_pool:
            return Decimal("0")
        return self.bounty_reward_pool * (self.bounty_platform_fee_pct / 100)


class BountySolution(db.Model):
    """Student solution submission to a bounty challenge"""
    __tablename__ = "cybercast_bounty_solutions"
    id = db.Column(db.Integer, primary_key=True)
    
    challenge_tier_id = db.Column(
        db.Integer,
        db.ForeignKey("cybercast_challenge_tiers.id", ondelete="CASCADE"),
        nullable=False
    )
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Solution content
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)
    attachment_url = db.Column(db.String(512))  # Link to solution (report, code, etc)
    
    # Verification workflow
    submitted_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    expert_review_status = db.Column(
        db.String(32),
        default="pending"  # pending, approved, rejected, needs_revision
    )
    expert_feedback = db.Column(db.Text)
    expert_reviewed_at = db.Column(db.DateTime)
    
    # Award status
    is_awarded = db.Column(db.Boolean, default=False)
    award_amount = db.Column(db.Numeric(12, 2))  # Expert's cut if awarded
    
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow
    )
    
    challenge_tier = db.relationship(
        "ChallengeTier",
        backref="solutions",
        foreign_keys=[challenge_tier_id]
    )
    student = db.relationship("Users", foreign_keys=[student_id])
    
    def __repr__(self):
        return f"<BountySolution tier_id={self.challenge_tier_id} student_id={self.student_id}>"


class TieredChallengeAccessLog(db.Model):
    """Audit log for challenge access decisions (for compliance)"""
    __tablename__ = "cybercast_challenge_access_logs"
    id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"))
    challenge_tier_id = db.Column(
        db.Integer,
        db.ForeignKey("cybercast_challenge_tiers.id", ondelete="CASCADE")
    )
    
    access_granted = db.Column(db.Boolean)  # True = allowed, False = denied
    denial_reason = db.Column(db.String(256))  # "requires_premium", "bounty_full", etc
    user_subscription_status = db.Column(db.String(32))  # "free", "premium", None
    
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)