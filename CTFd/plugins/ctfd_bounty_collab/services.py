# =============================================================================
# File: CTFd/plugins/ctfd_bounty_collab/services.py
# Plugin: ctfd_bounty_collab
# Created: 2026-07-15  Author: Claude / CyberCast implementation
# Purpose: State machine, escrow funding, and atomic payout logic.
#          Kept separate from routes.py for independent testability.
#          All mutations write to bntc_audit_log — no silent state changes.
#          Platform commission = 10%, researcher pool = 90% of escrow.
# =============================================================================

import datetime
from decimal import Decimal

from flask import abort

from CTFd.models import db

from .models import (
    CollabAuditLog,
    CollabEscrowLedger,
    CollabProject,
    CollabTeamMember,
    CollabWallet,
    CollabWalletTransaction,
)

# ---------------------------------------------------------------------------
# State machine definition
# ---------------------------------------------------------------------------

# Maps current_status -> set of statuses reachable from it
VALID_TRANSITIONS: dict = {
    "draft": {"published", "cancelled"},
    "published": {"recruiting", "draft", "cancelled"},   # draft = unpublish
    "recruiting": {"applications_closed", "cancelled"},
    "applications_closed": {"team_locked", "recruiting"},  # can re-open or lock
    "team_locked": {"in_progress"},
    "in_progress": {"submitted_for_review"},
    "submitted_for_review": {"approved", "revision_requested", "disputed"},
    "revision_requested": {"in_progress"},
    "approved": {"paid_out"},
    "paid_out": {"closed"},
    "disputed": {"approved", "cancelled"},   # admin resolves only
    "cancelled": set(),
    "closed": set(),
}

# Which role is allowed to drive each (from, to) transition
# Values: "owner" | "team" | "system" | "admin" | "owner_or_team"
TRANSITION_ROLES: dict = {
    ("draft", "published"): "owner",
    ("published", "draft"): "owner",          # unpublish
    ("published", "recruiting"): "owner",
    ("recruiting", "applications_closed"): "owner",  # partner closes recruiting
    ("applications_closed", "recruiting"): "owner",  # partner re-opens recruiting
    ("applications_closed", "team_locked"): "owner",
    ("team_locked", "in_progress"): "owner",
    ("in_progress", "submitted_for_review"): "team",
    ("submitted_for_review", "approved"): "owner",
    ("submitted_for_review", "revision_requested"): "owner",
    ("revision_requested", "in_progress"): "system",
    ("approved", "paid_out"): "system",       # set by release_payout()
    ("paid_out", "closed"): "owner",
    ("submitted_for_review", "disputed"): "owner_or_team",
    ("disputed", "approved"): "admin",
    ("disputed", "cancelled"): "admin",
    ("published", "cancelled"): "owner",
    ("recruiting", "cancelled"): "owner",
    ("applications_closed", "cancelled"): "owner",
    ("draft", "cancelled"): "owner",
}

# Pre-lock states where cancellation is allowed
CANCELLABLE_STATES = {"draft", "published", "recruiting", "applications_closed"}

# States that freeze budget, scope, and deliverables
EDIT_LOCKED_STATES = {
    "team_locked", "in_progress", "submitted_for_review",
    "revision_requested", "approved", "paid_out", "disputed", "closed",
}

PLATFORM_FEE_PCT = Decimal("10")


# ---------------------------------------------------------------------------
# Audit log helper
# ---------------------------------------------------------------------------

def _audit(project_id, actor_id, action, before=None, after=None):
    entry = CollabAuditLog(
        project_id=project_id,
        actor_id=actor_id,
        action=action,
        before_state=before or {},
        after_state=after or {},
    )
    db.session.add(entry)


# ---------------------------------------------------------------------------
# Wallet helper
# ---------------------------------------------------------------------------

def _get_or_create_wallet(user_id: int) -> CollabWallet:
    wallet = CollabWallet.query.filter_by(user_id=user_id).first()
    if wallet is None:
        wallet = CollabWallet(user_id=user_id, pending_balance=0, internal_balance=0)
        db.session.add(wallet)
        db.session.flush()
    return wallet


# ---------------------------------------------------------------------------
# Core: transition_project_status
# ---------------------------------------------------------------------------

def transition_project_status(
    project: CollabProject,
    new_status: str,
    actor,
    *,
    is_admin: bool = False,
    is_system: bool = False,
) -> CollabProject:
    """Validate and apply a status transition.
    Raises abort(409) for invalid transitions, abort(403) for role violations.
    Writes to audit_log.  Does NOT commit — callers commit.
    """
    old_status = project.status
    allowed = VALID_TRANSITIONS.get(old_status, set())

    if new_status not in allowed:
        abort(
            409,
            description=(
                f"Cannot transition project from '{old_status}' to '{new_status}'. "
                f"Allowed next states: {sorted(allowed) or 'none'}."
            ),
        )

    required_role = TRANSITION_ROLES.get((old_status, new_status), "owner")
    _check_transition_role(
        project, actor, required_role, is_admin=is_admin, is_system=is_system
    )

    project.status = new_status
    project.updated_at = datetime.datetime.utcnow()

    _audit(
        project_id=project.id,
        actor_id=actor.id if actor else None,
        action=f"status_changed:{old_status}->{new_status}",
        before={"status": old_status},
        after={"status": new_status},
    )
    return project


def _check_transition_role(project, actor, required_role, *, is_admin, is_system):
    if is_system:
        return

    if required_role == "admin":
        if not is_admin:
            abort(403, description="Admin access required for this transition.")
        return

    if required_role == "owner":
        if actor is None or project.owner_id != actor.id:
            abort(403, description="Only the project owner can make this transition.")
        return

    if required_role == "team":
        member = CollabTeamMember.query.filter_by(
            project_id=project.id,
            user_id=actor.id if actor else -1,
            status="active",
        ).first()
        if member is None:
            abort(403, description="Active team membership required for this transition.")
        return

    if required_role == "owner_or_team":
        is_owner = actor and project.owner_id == actor.id
        is_member = (
            CollabTeamMember.query.filter_by(
                project_id=project.id,
                user_id=actor.id if actor else -1,
                status="active",
            ).first()
            is not None
        )
        if not is_owner and not is_member:
            abort(403, description="Owner or active team member required.")
        return


# ---------------------------------------------------------------------------
# fund_escrow
# ---------------------------------------------------------------------------

def fund_escrow(project: CollabProject, amount_cents: int, actor) -> CollabEscrowLedger:
    """Create/update escrow for a project in 'recruiting' status.
    amount_cents: total budget in cents.
    Does NOT commit — callers commit.
    """
    if project.status not in ("recruiting", "applications_closed"):
        abort(
            409,
            description="Escrow can only be funded when project is in 'recruiting' or 'applications_closed' status.",
        )
    if amount_cents <= 0:
        abort(400, description="Escrow amount must be positive.")

    commission = int(amount_cents * int(PLATFORM_FEE_PCT) / 100)
    pool = amount_cents - commission

    ledger = CollabEscrowLedger.query.filter_by(project_id=project.id).first()
    if ledger is None:
        ledger = CollabEscrowLedger(project_id=project.id)
        db.session.add(ledger)

    before = {"ledger_status": ledger.status, "total_funded": ledger.total_funded}

    ledger.total_funded = amount_cents
    ledger.platform_commission_amount = commission
    ledger.researcher_pool_amount = pool
    ledger.status = "funded"
    ledger.funded_at = datetime.datetime.utcnow()

    db.session.add(
        CollabWalletTransaction(
            wallet_id=None,
            user_id=actor.id if actor else None,
            project_id=project.id,
            type="escrow_funded",
            amount=amount_cents,
            balance_after=0,
        )
    )

    _audit(
        project_id=project.id,
        actor_id=actor.id if actor else None,
        action="escrow_funded",
        before=before,
        after={
            "ledger_status": "funded",
            "total_funded": amount_cents,
            "commission": commission,
            "pool": pool,
        },
    )
    return ledger


# ---------------------------------------------------------------------------
# lock_team
# ---------------------------------------------------------------------------

def lock_team(project: CollabProject, actor) -> CollabProject:
    """Validate escrow funded + payout % sums to 100, then transition to team_locked.
    Does NOT commit — callers commit.
    """
    if project.status not in ("recruiting", "applications_closed"):
        abort(
            409,
            description="Project must be in 'recruiting' or 'applications_closed' status to lock team.",
        )

    members = CollabTeamMember.query.filter_by(
        project_id=project.id, status="active"
    ).all()
    if not members:
        abort(409, description="No active team members — accept at least one applicant first.")

    # Auto-close recruiting if still open
    if project.status == "recruiting":
        transition_project_status(project, "applications_closed", actor, is_system=True)

    # Auto-fund escrow from project budget if not already funded
    if project.budget_total > 0:
        ledger = CollabEscrowLedger.query.filter_by(project_id=project.id).first()
        if ledger is None or ledger.status != "funded":
            fund_escrow(project, project.budget_total, actor)

    # Auto-distribute equal payouts if all members still have 0%
    total_pct = sum(float(m.payout_percentage) for m in members)
    if abs(total_pct) < 0.01:
        n = len(members)
        base_pct = round(100.0 / n, 2)
        for i, m in enumerate(members):
            # Give remainder to last member so total is exactly 100
            m.payout_percentage = round(100.0 - base_pct * (n - 1), 2) if i == n - 1 else base_pct
    elif abs(total_pct - 100.0) > 0.01:
        abort(
            409,
            description=(
                f"Payout percentages must sum to 100 "
                f"(current: {total_pct:.2f}). Adjust member payouts before locking."
            ),
        )

    return transition_project_status(project, "team_locked", actor)


# ---------------------------------------------------------------------------
# release_payout  (ATOMIC — uses savepoint)
# ---------------------------------------------------------------------------

def release_payout(project: CollabProject, actor) -> None:
    """Atomically release researcher payouts and platform commission.
    Idempotency: raises abort(409) if already released.
    Uses db.session.begin_nested() savepoint — rolls back on partial failure.
    Does NOT commit — callers commit.

    Step order:
      1. Idempotency check
      2. Per-member payout → wallet credit + transaction row
      3. Platform commission transaction row
      4. ledger.status = "released"
      5. project.status = "paid_out"
      6. Audit log
    """
    ledger = CollabEscrowLedger.query.filter_by(project_id=project.id).first()

    if ledger is None:
        abort(409, description="No escrow ledger found for this project.")
    if ledger.status == "released":
        abort(
            409,
            description="Payout has already been released for this project (idempotency check).",
        )
    if ledger.status != "funded":
        abort(
            409,
            description=(
                f"Escrow must be in 'funded' state to release "
                f"(current: {ledger.status})."
            ),
        )

    sp = db.session.begin_nested()
    try:
        researcher_pool = ledger.researcher_pool_amount

        members = CollabTeamMember.query.filter_by(
            project_id=project.id, status="active"
        ).all()

        for member in members:
            pct = Decimal(str(member.payout_percentage))
            payout = int(researcher_pool * float(pct) / 100.0)

            wallet = _get_or_create_wallet(member.user_id)
            wallet.internal_balance += payout
            wallet.updated_at = datetime.datetime.utcnow()

            db.session.add(
                CollabWalletTransaction(
                    wallet_id=wallet.id,
                    user_id=member.user_id,
                    project_id=project.id,
                    type="payout_released",
                    amount=payout,
                    balance_after=wallet.internal_balance,
                )
            )

        # Platform commission row — wallet_id NULL signals system/platform
        db.session.add(
            CollabWalletTransaction(
                wallet_id=None,
                user_id=None,
                project_id=project.id,
                type="commission_deducted",
                amount=ledger.platform_commission_amount,
                balance_after=0,
            )
        )

        ledger.status = "released"
        ledger.released_at = datetime.datetime.utcnow()

        project.status = "paid_out"
        project.updated_at = datetime.datetime.utcnow()

        _audit(
            project_id=project.id,
            actor_id=actor.id if actor else None,
            action="payout_released",
            before={"ledger_status": "funded", "project_status": "approved"},
            after={
                "ledger_status": "released",
                "project_status": "paid_out",
                "total_paid_out": researcher_pool,
                "commission": ledger.platform_commission_amount,
            },
        )

        sp.commit()  # release savepoint (no DB commit yet)

    except Exception:
        sp.rollback()
        raise


# ---------------------------------------------------------------------------
# refund_escrow
# ---------------------------------------------------------------------------

def refund_escrow(project: CollabProject, actor):
    """Refund escrow — used on pre-lock cancellation or admin dispute resolution.
    Idempotent: no-op if already refunded or no ledger exists.
    Does NOT commit — callers commit.
    """
    ledger = CollabEscrowLedger.query.filter_by(project_id=project.id).first()
    if ledger is None:
        return None
    if ledger.status == "refunded":
        return ledger

    before_status = ledger.status
    ledger.status = "refunded"

    db.session.add(
        CollabWalletTransaction(
            wallet_id=None,
            user_id=project.owner_id,
            project_id=project.id,
            type="refund",
            amount=ledger.total_funded,
            balance_after=0,
        )
    )

    _audit(
        project_id=project.id,
        actor_id=actor.id if actor else None,
        action="escrow_refunded",
        before={"ledger_status": before_status},
        after={"ledger_status": "refunded"},
    )
    return ledger
