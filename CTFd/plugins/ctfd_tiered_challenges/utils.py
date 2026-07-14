# CTFd/plugins/ctfd_tiered_challenges_business/utils.py
"""
Tiered Challenges Business Logic & Access Control
==================================================

Implements:
1. Premium subscription checks (integrates with ctfd_monetization)
2. Bounty access rules
3. Revenue calculations
4. Access logging for compliance
"""

from CTFd.models import db
from .models import ChallengeTier, ChallengeTierType, TieredChallengeAccessLog
from decimal import Decimal
import datetime


def check_challenge_access(user_id, tier, challenge):
    """
    Comprehensive access control logic
    
    Args:
        user_id: User ID (None if not authenticated)
        tier: ChallengeTier instance or None
        challenge: Challenges instance
    
    Returns:
        (has_access: bool, reason: str, redirect_url: str|None)
    """
    
    # No tier info = public community challenge
    if not tier:
        return True, "community", None
    
    # Community tier - always accessible
    if tier.tier_type == ChallengeTierType.COMMUNITY:
        return True, "community_free", None
    
    # Must be authenticated for premium/bounty
    if not user_id:
        return False, "requires_login", "/auth/login"
    
    # Premium tier - check subscription
    if tier.tier_type == ChallengeTierType.PREMIUM:
        try:
            from CTFd.plugins.ctfd_monetization.services import is_premium_user
            # Get user object
            from CTFd.models import Users
            user = Users.query.get(user_id)
            
            if not is_premium_user(user):
                return False, "requires_premium_subscription", "/plugins/platform-plus/pricing"
            
            return True, "premium_access", None
            
        except ImportError:
            # Monetization plugin not available
            return False, "monetization_unavailable", None
    
    # Bounty tier - check if active and not full
    if tier.tier_type == ChallengeTierType.BOUNTY:
        if not tier.is_active_bounty:
            return False, "bounty_not_active", None
        
        if tier.max_participants:
            solution_count = db.session.query(
                db.func.count(db.distinct("cybercast_bounty_solutions.student_id"))
            ).filter_by(challenge_tier_id=tier.id).scalar() or 0
            
            if solution_count >= tier.max_participants:
                return False, "bounty_full", None
        
        return True, "bounty_access", None
    
    return False, "unknown_tier", None


def log_access_attempt(user_id, challenge_tier_id, access_granted, denial_reason=None):
    """
    Log all access attempts for audit trail & compliance
    """
    log_entry = TieredChallengeAccessLog(
        user_id=user_id,
        challenge_tier_id=challenge_tier_id,
        access_granted=access_granted,
        denial_reason=denial_reason,
    )
    
    db.session.add(log_entry)
    db.session.commit()


def calculate_tier_earnings(challenge_tier):
    """
    Calculate earnings for a completed bounty
    
    Returns:
    {
        "total_pool": 100.00 USD,
        "expert_reward": 90.00 USD (90%),
        "platform_fee": 10.00 USD (10%),
    }
    """
    if not challenge_tier.bounty_reward_pool:
        return {
            "total_pool": Decimal("0"),
            "expert_reward": Decimal("0"),
            "platform_fee": Decimal("0"),
        }
    
    return {
        "total_pool": challenge_tier.bounty_reward_pool,
        "expert_reward": challenge_tier.expert_reward,
        "platform_fee": challenge_tier.platform_fee,
    }


def get_pending_reviews(expert_user_id):
    """
    Get all pending solutions awaiting expert review
    """
    from .models import BountySolution
    
    pending = BountySolution.query.join(
        ChallengeTier, BountySolution.challenge_tier_id == ChallengeTier.id
    ).filter(
        ChallengeTier.expert_reviewer_id == expert_user_id,
        BountySolution.expert_review_status == "pending"
    ).all()
    
    return pending


def get_user_earnings_summary(user_id):
    """
    Get expert's total earnings from bounty reviews
    """
    from .models import BountySolution
    
    awarded_solutions = BountySolution.query.join(
        ChallengeTier, BountySolution.challenge_tier_id == ChallengeTier.id
    ).filter(
        ChallengeTier.expert_reviewer_id == user_id,
        BountySolution.is_awarded == True,
    ).all()
    
    total_earned = sum(
        s.award_amount or Decimal("0")
        for s in awarded_solutions
    )
    
    return {
        "total_awarded_solutions": len(awarded_solutions),
        "total_earned_usd": str(total_earned),
        "pending_payout": "TODO: integrate with monetization",
    }