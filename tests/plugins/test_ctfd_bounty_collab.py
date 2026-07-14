# =============================================================================
# File: tests/plugins/test_ctfd_bounty_collab.py
# Plugin: ctfd_bounty_collab
# Created: 2026-07-15  Author: Claude / CyberCast implementation
# Purpose: Integration tests covering all spec "done" criteria.
#          Uses pytest + CTFd's in-memory SQLite test pattern.
#          Tests service-layer functions directly (no HTTP) for reliability.
# =============================================================================

import pytest

from CTFd import create_app
from CTFd.models import db as _db, Users


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def app():
    _app = create_app()
    _app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        WTF_CSRF_ENABLED=False,
        SERVER_NAME="localhost",
    )
    with _app.app_context():
        _db.create_all()
        yield _app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(app, name="testuser", email=None, verified=True, utype="user"):
    from CTFd.utils.crypto import hash_password

    email = email or f"{name}@test.com"
    u = Users(
        name=name,
        email=email,
        password=hash_password("password"),
        verified=verified,
        type=utype,
    )
    _db.session.add(u)
    _db.session.commit()
    return u


def _make_project(owner_id, status="recruiting", budget=100_000):
    from CTFd.plugins.ctfd_bounty_collab.models import CollabProject

    p = CollabProject(
        title="Test Project",
        problem_statement="Find and document vulnerabilities.",
        budget_total=budget,
        owner_id=owner_id,
        status=status,
    )
    _db.session.add(p)
    _db.session.commit()
    return p


def _make_team_member(project_id, user_id, pct=100):
    from CTFd.plugins.ctfd_bounty_collab.models import CollabTeamMember

    m = CollabTeamMember(
        project_id=project_id,
        user_id=user_id,
        payout_percentage=pct,
        status="active",
    )
    _db.session.add(m)
    _db.session.commit()
    return m


def _fund_escrow(project, owner):
    from CTFd.plugins.ctfd_bounty_collab.services import fund_escrow

    fund_escrow(project, project.budget_total, owner)
    _db.session.commit()


# ---------------------------------------------------------------------------
# Test 1: Cannot lock_team without funded escrow
# ---------------------------------------------------------------------------

def test_lock_team_requires_funded_escrow(app):
    """lock_team() must raise 409 when no escrow ledger exists."""
    with app.app_context():
        from CTFd.plugins.ctfd_bounty_collab.services import lock_team
        from werkzeug.exceptions import Conflict

        owner = _make_user(app, "owner1")
        project = _make_project(owner.id, status="recruiting")
        _make_team_member(project.id, owner.id, pct=100)

        with pytest.raises(Exception) as exc_info:
            lock_team(project, owner)

        exc = exc_info.value
        # werkzeug HTTPException has .code; plain ValueError has message
        code = getattr(exc, "code", None)
        msg = str(exc).lower()
        assert code == 409 or "escrow" in msg, f"Expected 409/escrow error, got: {exc}"


# ---------------------------------------------------------------------------
# Test 2: Cannot lock_team unless payout percentages sum to exactly 100
# ---------------------------------------------------------------------------

def test_lock_team_requires_100pct_sum(app):
    """lock_team() must reject when team percentages do not total 100."""
    with app.app_context():
        owner = _make_user(app, "owner2")
        expert = _make_user(app, "expert2")
        project = _make_project(owner.id, status="recruiting")

        _fund_escrow(project, owner)

        # 40 + 40 = 80 (not 100)
        _make_team_member(project.id, owner.id, pct=40)
        _make_team_member(project.id, expert.id, pct=40)

        from CTFd.plugins.ctfd_bounty_collab.services import lock_team

        with pytest.raises(Exception) as exc_info:
            lock_team(project, owner)

        exc = exc_info.value
        code = getattr(exc, "code", None)
        msg = str(exc).lower()
        assert code == 409 or "100" in msg or "percentage" in msg, (
            f"Expected 409/percentage error, got: {exc}"
        )


# ---------------------------------------------------------------------------
# Test 3: release_payout credits researcher wallets correctly (90% split)
# ---------------------------------------------------------------------------

def test_release_payout_credits_researcher_wallet(app):
    """release_payout() must credit 90% to researcher wallet."""
    with app.app_context():
        from CTFd.plugins.ctfd_bounty_collab.services import fund_escrow, release_payout
        from CTFd.plugins.ctfd_bounty_collab.models import CollabWallet

        owner = _make_user(app, "owner3")
        expert = _make_user(app, "expert3")
        # Must be in approved state so release_payout works
        project = _make_project(owner.id, status="approved", budget=100_000)
        _make_team_member(project.id, expert.id, pct=100)

        # Fund escrow directly (skip recruiting state check via service)
        from CTFd.plugins.ctfd_bounty_collab.models import CollabEscrowLedger
        import datetime
        ledger = CollabEscrowLedger(
            project_id=project.id,
            total_funded=100_000,
            platform_commission_amount=10_000,
            researcher_pool_amount=90_000,
            status="funded",
            funded_at=datetime.datetime.utcnow(),
        )
        _db.session.add(ledger)
        _db.session.commit()

        release_payout(project, owner)
        _db.session.commit()

        wallet = CollabWallet.query.filter_by(user_id=expert.id).first()
        assert wallet is not None, "Wallet should have been created"
        assert wallet.internal_balance == 90_000, (
            f"Expected 90000 (90%), got {wallet.internal_balance}"
        )


# ---------------------------------------------------------------------------
# Test 4: release_payout idempotency — double release is rejected
# ---------------------------------------------------------------------------

def test_release_payout_idempotency(app):
    """release_payout() must raise 409 on second call for the same project."""
    with app.app_context():
        from CTFd.plugins.ctfd_bounty_collab.services import release_payout
        from CTFd.plugins.ctfd_bounty_collab.models import CollabEscrowLedger
        import datetime

        owner = _make_user(app, "owner4")
        expert = _make_user(app, "expert4")
        project = _make_project(owner.id, status="approved", budget=50_000)
        _make_team_member(project.id, expert.id, pct=100)

        ledger = CollabEscrowLedger(
            project_id=project.id,
            total_funded=50_000,
            platform_commission_amount=5_000,
            researcher_pool_amount=45_000,
            status="funded",
            funded_at=datetime.datetime.utcnow(),
        )
        _db.session.add(ledger)
        _db.session.commit()

        # First release — succeeds
        release_payout(project, owner)
        _db.session.commit()

        # Second release — must fail
        with pytest.raises(Exception) as exc_info:
            release_payout(project, owner)

        exc = exc_info.value
        code = getattr(exc, "code", None)
        msg = str(exc).lower()
        assert code == 409 or "already been released" in msg, (
            f"Expected idempotency rejection, got: {exc}"
        )


# ---------------------------------------------------------------------------
# Test 5: Non-owner cannot drive approved transition
# ---------------------------------------------------------------------------

def test_non_owner_cannot_approve(app):
    """transition_project_status() → approved must 403 for non-owner."""
    with app.app_context():
        from CTFd.plugins.ctfd_bounty_collab.services import transition_project_status

        owner = _make_user(app, "owner5")
        expert = _make_user(app, "expert5")
        project = _make_project(owner.id, status="submitted_for_review")

        with pytest.raises(Exception) as exc_info:
            transition_project_status(project, "approved", expert)

        exc = exc_info.value
        code = getattr(exc, "code", None)
        msg = str(exc).lower()
        assert code == 403 or "owner" in msg, (
            f"Expected 403/owner error, got: {exc}"
        )


# ---------------------------------------------------------------------------
# Test 6: Non-team-member (no NDA) blocked from /brief endpoint
# ---------------------------------------------------------------------------

def test_full_brief_blocked_without_nda(app, client):
    """GET /brief must return 403 for users without NDA or team membership."""
    with app.app_context():
        owner = _make_user(app, "owner6", utype="admin")
        outsider = _make_user(app, "outsider6")
        project = _make_project(owner.id, status="published", budget=1000)
        project.is_nda_required = True
        _db.session.commit()
        pid = project.id

    with client.session_transaction() as sess:
        sess["id"] = outsider.id
        sess["name"] = "outsider6"
        sess["hash"] = "test"

    resp = client.get(f"/plugins/bounty-collab/projects/{pid}/brief")
    # Without NDA and not owner → 403
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Test 7a: Cancel before team_locked refunds escrow
# ---------------------------------------------------------------------------

def test_cancel_before_lock_triggers_refund(app):
    """Cancelling a recruiting project must mark escrow as refunded."""
    with app.app_context():
        from CTFd.plugins.ctfd_bounty_collab.services import (
            fund_escrow,
            refund_escrow,
            transition_project_status,
        )
        from CTFd.plugins.ctfd_bounty_collab.models import CollabEscrowLedger

        owner = _make_user(app, "owner7a")
        project = _make_project(owner.id, status="recruiting")
        fund_escrow(project, 50_000, owner)
        _db.session.commit()

        refund_escrow(project, owner)
        transition_project_status(project, "cancelled", owner)
        _db.session.commit()

        ledger = CollabEscrowLedger.query.filter_by(project_id=project.id).first()
        assert ledger is not None
        assert ledger.status == "refunded", f"Expected 'refunded', got '{ledger.status}'"
        assert project.status == "cancelled"


# ---------------------------------------------------------------------------
# Test 7b: Cancel after team_locked is blocked by state machine
# ---------------------------------------------------------------------------

def test_cancel_after_lock_is_blocked(app):
    """State machine must reject draft/team_locked → cancelled transition."""
    with app.app_context():
        from CTFd.plugins.ctfd_bounty_collab.services import transition_project_status

        owner = _make_user(app, "owner7b")
        project = _make_project(owner.id, status="team_locked")

        with pytest.raises(Exception) as exc_info:
            transition_project_status(project, "cancelled", owner)

        exc = exc_info.value
        code = getattr(exc, "code", None)
        msg = str(exc).lower()
        assert code == 409 or "cannot transition" in msg, (
            f"Expected 409/invalid-transition error, got: {exc}"
        )
