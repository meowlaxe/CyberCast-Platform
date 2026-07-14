# CTFd/plugins/ctfd_tiered_challenges_business/routes.py
"""
Tiered Challenges Routes - Implements access control & business logic
=======================================================================

Integrates with:
- ctfd_monetization: Premium subscription checks
- ctfd_bounty: Enterprise problem posting
- ctfd_student_teams: Participation tracking
"""

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for, current_app
from flask_login import login_required, current_user
from CTFd.models import db, Challenges, Users
from CTFd.utils.decorators import admins_only
from datetime import datetime
from decimal import Decimal

from .models import (
    ChallengeTier,
    ChallengeTierType,
    BountyStatus,
    BountySolution,
    TieredChallengeAccessLog,
)
from .utils import (
    check_challenge_access,
    log_access_attempt,
    calculate_tier_earnings,
)

tiered_challenges_bp = Blueprint(
    "tiered_challenges_business",
    __name__,
    url_prefix="/challenges/tiered",
)


# ============================================================================
# PUBLIC ENDPOINTS - Challenge Discovery
# ============================================================================

@tiered_challenges_bp.route("/community", methods=["GET"])
def community_challenges():
    """
    List all free, community challenges
    - No authentication required
    - No subscription check
    """
    challenges = db.session.query(Challenges).join(
        ChallengeTier, Challenges.id == ChallengeTier.challenge_id
    ).filter(
        ChallengeTier.tier_type == ChallengeTierType.COMMUNITY,
        Challenges.state == "visible"
    ).order_by(ChallengeTier.created_at.desc()).all()
    
    data = [
        {
            "id": c.id,
            "name": c.name,
            "category": c.category,
            "value": c.value,
            "description": c.description,
            "tier": "community",
        }
        for c in challenges
    ]
    
    return render_template(
        "tiered_challenges/community.html",
        challenges=challenges,
        challenge_count=len(challenges)
    )


@tiered_challenges_bp.route("/premium", methods=["GET"])
@login_required
def premium_challenges():
    """
    List premium learning path challenges
    - Requires authentication + active premium subscription
    - Part of learning paths
    """
    # Check subscription via monetization plugin
    try:
        from CTFd.plugins.ctfd_monetization.services import is_premium_user
        if not is_premium_user(current_user):
            return redirect(url_for("monetization.pricing"))
    except ImportError:
        current_app.logger.warning("ctfd_monetization plugin not found")
        return redirect(url_for("views.index"))
    
    challenges = db.session.query(Challenges).join(
        ChallengeTier, Challenges.id == ChallengeTier.challenge_id
    ).filter(
        ChallengeTier.tier_type == ChallengeTierType.PREMIUM,
        ChallengeTier.require_premium == True,
        Challenges.state == "visible"
    ).order_by(ChallengeTier.created_at.desc()).all()
    
    return render_template(
        "tiered_challenges/premium.html",
        challenges=challenges,
        challenge_count=len(challenges)
    )


@tiered_challenges_bp.route("/bounty", methods=["GET"])
@login_required
def bounty_challenges():
    """
    List active enterprise bounty challenges
    - Students can view ACTIVE bounties
    - Experts can review solutions
    - Show reward amounts
    """
    # Get all active bounties
    bounties = db.session.query(ChallengeTier).filter(
        ChallengeTier.tier_type == ChallengeTierType.BOUNTY,
        ChallengeTier.bounty_status == BountyStatus.ACTIVE,
    ).all()
    
    bounty_data = []
    for tier in bounties:
        challenge = tier.challenge
        solution_count = BountySolution.query.filter_by(
            challenge_tier_id=tier.id,
            expert_review_status="pending"
        ).count()
        
        bounty_data.append({
            "id": tier.id,
            "challenge_id": challenge.id,
            "name": challenge.name,
            "description": tier.description,
            "reward_pool": str(tier.bounty_reward_pool),
            "expert_reward": str(tier.expert_reward),
            "platform_fee": str(tier.platform_fee),
            "pending_solutions": solution_count,
            "tags": tier.tags,
            "difficulty": tier.difficulty_rating,
        })
    
    return render_template(
        "tiered_challenges/bounty.html",
        bounties=bounty_data,
        bounty_count=len(bounty_data)
    )


# ============================================================================
# ACCESS CONTROL ENDPOINT
# ============================================================================

@tiered_challenges_bp.route("/<int:challenge_id>/check-access", methods=["GET"])
def check_access(challenge_id):
    """
    API: Check if user can access a challenge
    
    Returns:
    - access (bool): True if user can view/solve
    - reason (str): Why access was granted or denied
    - tier_type (str): community|premium|bounty
    - redirect_url (str): Where to go if access denied (e.g., /subscription/plans)
    """
    challenge = Challenges.query.get_or_404(challenge_id)
    tier = ChallengeTier.query.filter_by(challenge_id=challenge_id).first()
    
    user_id = current_user.id if current_user.is_authenticated else None
    has_access, reason, redirect_url = check_challenge_access(user_id, tier, challenge)
    
    # Log access attempt
    if user_id:
        log_access_attempt(
            user_id=user_id,
            challenge_tier_id=tier.id if tier else None,
            access_granted=has_access,
            denial_reason=reason if not has_access else None
        )
    
    response = {
        "access": has_access,
        "reason": reason,
        "tier_type": tier.tier_type if tier else "community",
    }
    if not has_access and redirect_url:
        response["redirect_url"] = redirect_url
    
    return jsonify(response)


# ============================================================================
# BOUNTY SOLUTION SUBMISSION (Students)
# ============================================================================

@tiered_challenges_bp.route("/<int:challenge_id>/submit-solution", methods=["POST"])
@login_required
def submit_bounty_solution(challenge_id):
    """
    Student submits solution to bounty challenge
    
    Flow:
    1. Student fills form with solution details
    2. Expert gets notified
    3. Expert reviews and approves/rejects
    4. If approved → bounty released (90% to expert, 10% to platform)
    """
    challenge = Challenges.query.get_or_404(challenge_id)
    tier = ChallengeTier.query.filter_by(challenge_id=challenge_id).first_or_404()
    
    if tier.tier_type != ChallengeTierType.BOUNTY:
        return jsonify({"error": "Not a bounty challenge"}), 400
    
    if not tier.is_active_bounty:
        return jsonify({"error": "Bounty is no longer accepting solutions"}), 400
    
    # Parse form
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    attachment_url = request.form.get("attachment_url", "").strip()
    
    if not title or not description:
        return jsonify({"error": "Title and description required"}), 400
    
    # Create solution record
    solution = BountySolution(
        challenge_tier_id=tier.id,
        student_id=current_user.id,
        title=title,
        description=description,
        attachment_url=attachment_url,
    )
    
    db.session.add(solution)
    db.session.commit()
    
    # Notify expert
    # TODO: Send email to tier.expert_reviewer_id
    
    return jsonify({
        "success": True,
        "solution_id": solution.id,
        "message": "Solution submitted. Expert will review shortly."
    })


# ============================================================================
# EXPERT REVIEW WORKFLOW
# ============================================================================

@tiered_challenges_bp.route("/solution/<int:solution_id>/review", methods=["POST"])
@login_required
def review_solution(solution_id):
    """
    Expert reviews student solution to bounty challenge
    
    Approves/Rejects, then payment flow is triggered
    """
    solution = BountySolution.query.get_or_404(solution_id)
    tier = solution.challenge_tier
    
    # Verify user is the assigned expert
    if tier.expert_reviewer_id != current_user.id:
        abort(403)
    
    review_status = request.form.get("status")  # "approved" or "rejected"
    feedback = request.form.get("feedback", "").strip()
    
    if review_status not in ("approved", "rejected"):
        return jsonify({"error": "Invalid status"}), 400
    
    solution.expert_review_status = review_status
    solution.expert_feedback = feedback
    solution.expert_reviewed_at = datetime.utcnow()
    
    if review_status == "approved":
        solution.is_awarded = True
        solution.award_amount = tier.expert_reward
        tier.bounty_status = BountyStatus.AWARDED
        
        # TODO: Trigger payout via monetization plugin
        # - Create Invoice for expert (90%)
        # - Create Invoice for platform (10%)
    
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": f"Solution {review_status}",
    })


# ============================================================================
# ADMIN MANAGEMENT
# ============================================================================

@tiered_challenges_bp.route("/admin/manage", methods=["GET", "POST"])
@admins_only
def admin_manage_tiers():
    """Admin panel: Assign tier classification to challenges"""
    if request.method == "POST":
        challenge_id = request.form.get("challenge_id", type=int)
        tier_type = request.form.get("tier_type")
        require_premium = request.form.get("require_premium") == "on"
        
        tier = ChallengeTier.query.filter_by(challenge_id=challenge_id).first()
        if not tier:
            tier = ChallengeTier(challenge_id=challenge_id)
        
        tier.tier_type = tier_type
        tier.require_premium = require_premium
        
        db.session.add(tier)
        db.session.commit()
        
        return jsonify({"success": True, "message": "Tier updated"})
    
    all_challenges = Challenges.query.all()
    tiers = ChallengeTier.query.all()
    
    return render_template(
        "admin/tiered_challenges_manage.html",
        challenges=all_challenges,
        tiers=tiers,
        tier_types=[
            ChallengeTierType.COMMUNITY,
            ChallengeTierType.PREMIUM,
            ChallengeTierType.BOUNTY,
        ]
    )