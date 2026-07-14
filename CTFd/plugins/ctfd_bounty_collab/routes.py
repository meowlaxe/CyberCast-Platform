# =============================================================================
# File: CTFd/plugins/ctfd_bounty_collab/routes.py
# Plugin: ctfd_bounty_collab
# Created: 2026-07-15  Author: Claude / CyberCast implementation
# Purpose: All HTTP endpoints for the bounty-collab plugin.
#          url_prefix: /plugins/bounty-collab
#          Blueprint name: bounty_collab
#          Every mutating endpoint writes to audit_log via services.py.
# =============================================================================

import datetime

from flask import Blueprint, abort, g, jsonify, render_template, request

from CTFd.models import db
from CTFd.utils.decorators import admins_only, authed_only
from CTFd.utils.user import get_current_user

from .models import (
    CollabApplication,
    CollabDeliverable,
    CollabEscrowLedger,
    CollabNdaAcceptance,
    CollabProject,
    CollabTeamMember,
    CollabWallet,
    CollabWalletTransaction,
)
from .permissions import (
    active_team_member_only,
    enterprise_only,
    expert_verified_only,
    full_brief_access,
    owner_or_active_team_member,
    project_owner_only,
    require_verified,
)
from .services import (
    CANCELLABLE_STATES,
    EDIT_LOCKED_STATES,
    _audit,
    fund_escrow,
    lock_team,
    refund_escrow,
    release_payout,
    transition_project_status,
)

bounty_collab_bp = Blueprint(
    "bounty_collab",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/plugins/bounty-collab",
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _json_project(p: CollabProject) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "category": p.category,
        "problem_statement": p.problem_statement,
        "scope_of_work": p.scope_of_work,
        "required_expertise": p.required_expertise,
        "team_size_min": p.team_size_min,
        "team_size_max": p.team_size_max,
        "application_deadline": (
            p.application_deadline.isoformat() if p.application_deadline else None
        ),
        "research_duration_days": p.research_duration_days,
        "budget_total": p.budget_total,
        "is_nda_required": p.is_nda_required,
        "status": p.status,
        "owner_id": p.owner_id,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# ===========================================================================
# HTML VIEWS
# ===========================================================================

@bounty_collab_bp.route("/", methods=["GET"])
@authed_only
def project_list_view():
    projects = (
        CollabProject.query
        .filter(CollabProject.status.in_(["published", "recruiting"]))
        .order_by(CollabProject.created_at.desc())
        .all()
    )
    return render_template("bounty_collab/project_list.html", projects=projects)


@bounty_collab_bp.route("/projects/<int:project_id>/view", methods=["GET"])
@authed_only
def project_detail_view(project_id):
    project = CollabProject.query.get_or_404(project_id)
    user = get_current_user()
    applied = CollabApplication.query.filter_by(
        project_id=project_id, applicant_id=user.id
    ).first()
    return render_template(
        "bounty_collab/project_detail.html", project=project, applied=applied
    )


@bounty_collab_bp.route("/projects/new", methods=["GET"])
@enterprise_only
def project_new_view():
    return render_template("bounty_collab/project_new.html")


@bounty_collab_bp.route("/projects/<int:project_id>/workspace", methods=["GET"])
@authed_only
def team_workspace_view(project_id):
    project = CollabProject.query.get_or_404(project_id)
    user = get_current_user()
    member = CollabTeamMember.query.filter_by(
        project_id=project_id, user_id=user.id, status="active"
    ).first()
    deliverables = (
        CollabDeliverable.query
        .filter_by(project_id=project_id)
        .order_by(CollabDeliverable.created_at.desc())
        .all()
    )
    return render_template(
        "bounty_collab/team_workspace.html",
        project=project,
        member=member,
        deliverables=deliverables,
    )


@bounty_collab_bp.route("/wallet/view", methods=["GET"])
@authed_only
def wallet_view():
    user = get_current_user()
    wallet = CollabWallet.query.filter_by(user_id=user.id).first()
    txns = (
        CollabWalletTransaction.query
        .filter_by(wallet_id=wallet.id)
        .order_by(CollabWalletTransaction.created_at.desc())
        .all()
        if wallet
        else []
    )
    return render_template("bounty_collab/wallet.html", wallet=wallet, transactions=txns)


# ===========================================================================
# ENTERPRISE: Project management API
# ===========================================================================

@bounty_collab_bp.route("/projects", methods=["POST"])
@enterprise_only
def create_project():
    """POST /projects — create a new draft project (enterprise only)."""
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    if not title:
        abort(400, description="'title' is required.")
    problem = (data.get("problem_statement") or "").strip()
    if not problem:
        abort(400, description="'problem_statement' is required.")
    budget = data.get("budget_total")
    if budget is None or int(budget) <= 0:
        abort(400, description="'budget_total' (cents, > 0) is required.")

    deadline = None
    if data.get("application_deadline"):
        try:
            deadline = datetime.datetime.fromisoformat(data["application_deadline"])
        except ValueError:
            abort(400, description="'application_deadline' must be ISO 8601 datetime.")

    project = CollabProject(
        title=title,
        category=data.get("category", ""),
        problem_statement=problem,
        scope_of_work=data.get("scope_of_work", ""),
        deliverables=data.get("deliverables", ""),
        required_expertise=data.get("required_expertise", ""),
        team_size_min=int(data.get("team_size_min") or 1),
        team_size_max=int(data.get("team_size_max") or 5),
        application_deadline=deadline,
        research_duration_days=data.get("research_duration_days"),
        budget_total=int(budget),
        is_nda_required=bool(data.get("is_nda_required", False)),
        nda_full_brief=data.get("nda_full_brief"),
        owner_id=user.id,
        status="draft",
    )
    db.session.add(project)
    db.session.flush()

    _audit(project.id, user.id, "project_created", {}, _json_project(project))
    db.session.commit()

    return jsonify(_json_project(project)), 201


@bounty_collab_bp.route("/projects/<int:project_id>", methods=["GET"])
@authed_only
def get_project(project_id):
    """GET /projects/<id> — public summary (no NDA brief field)."""
    project = CollabProject.query.get_or_404(project_id)
    return jsonify(_json_project(project))


@bounty_collab_bp.route("/projects/<int:project_id>", methods=["PATCH"])
@project_owner_only("project_id")
def edit_project(project_id):
    """PATCH /projects/<id> — edit (owner only, pre-lock states only)."""
    user = get_current_user()
    project = g.bntc_project

    if project.status in EDIT_LOCKED_STATES:
        abort(
            409,
            description=(
                "Project is locked. budget_total, scope_of_work, and deliverables "
                "cannot be edited after team_locked."
            ),
        )

    data = request.get_json(silent=True) or {}
    before = _json_project(project)

    editable = [
        "title", "category", "problem_statement", "scope_of_work",
        "deliverables", "required_expertise", "team_size_min", "team_size_max",
        "application_deadline", "research_duration_days", "budget_total",
        "is_nda_required", "nda_full_brief",
    ]
    for field in editable:
        if field in data:
            if field == "application_deadline" and data[field]:
                try:
                    setattr(
                        project, field,
                        datetime.datetime.fromisoformat(data[field])
                    )
                except ValueError:
                    abort(400, description=f"'{field}' must be ISO 8601 datetime.")
            else:
                setattr(project, field, data[field])

    project.updated_at = datetime.datetime.utcnow()
    _audit(project.id, user.id, "project_edited", before, _json_project(project))
    db.session.commit()

    return jsonify(_json_project(project))


@bounty_collab_bp.route("/projects/<int:project_id>/brief", methods=["GET"])
@full_brief_access("project_id")
def get_full_brief(project_id):
    """GET /projects/<id>/brief — NDA brief (owner OR NDA accepted OR accepted member)."""
    project = g.bntc_project
    data = _json_project(project)
    data["nda_full_brief"] = project.nda_full_brief
    return jsonify(data)


@bounty_collab_bp.route("/projects/<int:project_id>/publish", methods=["POST"])
@project_owner_only("project_id")
def publish_project(project_id):
    """POST /projects/<id>/publish — draft → published."""
    user = get_current_user()
    project = g.bntc_project
    transition_project_status(project, "published", user)
    db.session.commit()
    return jsonify({"status": project.status})


@bounty_collab_bp.route("/projects/<int:project_id>/recruit", methods=["POST"])
@project_owner_only("project_id")
def start_recruiting(project_id):
    """POST /projects/<id>/recruit — published → recruiting."""
    user = get_current_user()
    project = g.bntc_project
    transition_project_status(project, "recruiting", user)
    db.session.commit()
    return jsonify({"status": project.status})


@bounty_collab_bp.route("/projects/<int:project_id>/fund-escrow", methods=["POST"])
@project_owner_only("project_id")
def fund_project_escrow(project_id):
    """POST /projects/<id>/fund-escrow — fund escrow (recruiting status only)."""
    user = get_current_user()
    project = g.bntc_project
    data = request.get_json(silent=True) or {}

    amount = data.get("amount_cents")
    if amount is None:
        abort(400, description="'amount_cents' is required.")

    fund_escrow(project, int(amount), user)
    db.session.commit()
    return jsonify({"message": "Escrow funded.", "amount_cents": int(amount)})


@bounty_collab_bp.route("/projects/<int:project_id>/lock-team", methods=["POST"])
@project_owner_only("project_id")
def lock_project_team(project_id):
    """POST /projects/<id>/lock-team — recruiting → team_locked.
    Validates escrow funded + payout % sums to 100.
    """
    user = get_current_user()
    project = g.bntc_project
    lock_team(project, user)
    db.session.commit()
    return jsonify({"status": project.status})


@bounty_collab_bp.route("/projects/<int:project_id>/start", methods=["POST"])
@project_owner_only("project_id")
def start_project(project_id):
    """POST /projects/<id>/start — team_locked → in_progress."""
    user = get_current_user()
    project = g.bntc_project
    transition_project_status(project, "in_progress", user)
    db.session.commit()
    return jsonify({"status": project.status})


@bounty_collab_bp.route("/projects/<int:project_id>/review", methods=["PATCH"])
@project_owner_only("project_id")
def review_project(project_id):
    """PATCH /projects/<id>/review — approve or request revision.
    Body: {"decision": "approve" | "revision_requested", "note": "..."}
    Approving triggers atomic payout (release_payout).
    """
    user = get_current_user()
    project = g.bntc_project
    data = request.get_json(silent=True) or {}

    decision = (data.get("decision") or "").strip()
    note = (data.get("note") or "").strip()

    if decision == "approve":
        transition_project_status(project, "approved", user)
        release_payout(project, user)   # also sets project.status = "paid_out"
        db.session.commit()
        return jsonify({"status": project.status, "message": "Approved and payout released."})

    if decision == "revision_requested":
        transition_project_status(project, "revision_requested", user)
        latest = (
            CollabDeliverable.query
            .filter_by(project_id=project.id)
            .order_by(CollabDeliverable.created_at.desc())
            .first()
        )
        if latest:
            latest.reviewer_note = note
            latest.status = "revision_requested"
        db.session.commit()
        return jsonify({"status": project.status})

    abort(400, description="'decision' must be 'approve' or 'revision_requested'.")


@bounty_collab_bp.route("/projects/<int:project_id>/close", methods=["POST"])
@project_owner_only("project_id")
def close_project(project_id):
    """POST /projects/<id>/close — paid_out → closed."""
    user = get_current_user()
    project = g.bntc_project
    transition_project_status(project, "closed", user)
    db.session.commit()
    return jsonify({"status": project.status})


@bounty_collab_bp.route("/projects/<int:project_id>/cancel", methods=["POST"])
@project_owner_only("project_id")
def cancel_project(project_id):
    """POST /projects/<id>/cancel — pre-lock cancellation with escrow refund."""
    user = get_current_user()
    project = g.bntc_project

    if project.status not in CANCELLABLE_STATES:
        abort(
            409,
            description=(
                f"Cannot cancel project in '{project.status}' status. "
                "Projects at or after team_locked must go through the dispute process."
            ),
        )

    refund_escrow(project, user)
    transition_project_status(project, "cancelled", user)
    db.session.commit()
    return jsonify({"status": project.status})


@bounty_collab_bp.route("/projects/<int:project_id>/dispute", methods=["POST"])
@owner_or_active_team_member("project_id")
def dispute_project(project_id):
    """POST /projects/<id>/dispute — owner or active team member."""
    user = get_current_user()
    project = g.bntc_project
    transition_project_status(project, "disputed", user)
    db.session.commit()
    return jsonify({"status": project.status})


# ===========================================================================
# EXPERT: Browse & apply
# ===========================================================================

@bounty_collab_bp.route("/projects", methods=["GET"])
@authed_only
def list_projects():
    """GET /projects — published/recruiting projects for experts to browse."""
    projects = (
        CollabProject.query
        .filter(CollabProject.status.in_(["published", "recruiting"]))
        .order_by(CollabProject.created_at.desc())
        .all()
    )
    return jsonify([_json_project(p) for p in projects])


@bounty_collab_bp.route("/projects/<int:project_id>/apply", methods=["POST"])
@expert_verified_only
def apply_to_project(project_id):
    """POST /projects/<id>/apply — university-org verified expert applies (not the owner)."""
    user = get_current_user()
    project = CollabProject.query.get_or_404(project_id)

    if project.owner_id == user.id:
        abort(403, description="Project owner cannot apply to their own project.")
    if project.status not in ("published", "recruiting"):
        abort(409, description="Project is not currently accepting applications.")

    existing = (
        CollabApplication.query
        .filter_by(project_id=project_id, applicant_id=user.id)
        .filter(CollabApplication.status != "withdrawn")
        .first()
    )
    if existing:
        abort(409, description="You have already applied to this project.")

    data = request.get_json(silent=True) or {}
    app_obj = CollabApplication(
        project_id=project_id,
        applicant_id=user.id,
        team_name=data.get("team_name"),
        cover_note=data.get("cover_note", ""),
        status="pending",
    )
    db.session.add(app_obj)
    db.session.flush()

    _audit(
        project_id, user.id, "application_submitted",
        {}, {"application_id": app_obj.id, "applicant_id": user.id}
    )
    db.session.commit()

    return jsonify({"id": app_obj.id, "status": app_obj.status}), 201


@bounty_collab_bp.route("/projects/<int:project_id>/nda-accept", methods=["POST"])
@authed_only
def accept_nda(project_id):
    """POST /projects/<id>/nda-accept — record NDA acceptance to unlock brief."""
    user = get_current_user()
    project = CollabProject.query.get_or_404(project_id)

    if not project.is_nda_required:
        abort(400, description="This project does not require an NDA.")

    existing = CollabNdaAcceptance.query.filter_by(
        project_id=project_id, user_id=user.id
    ).first()
    if existing:
        return jsonify(
            {"message": "NDA already accepted.", "accepted_at": existing.accepted_at.isoformat()}
        )

    nda = CollabNdaAcceptance(project_id=project_id, user_id=user.id)
    db.session.add(nda)
    _audit(project_id, user.id, "nda_accepted", {}, {"user_id": user.id})
    db.session.commit()

    return jsonify(
        {"message": "NDA accepted.", "accepted_at": nda.accepted_at.isoformat()}
    ), 201


# ===========================================================================
# ENTERPRISE: Manage applications & team
# ===========================================================================

@bounty_collab_bp.route("/projects/<int:project_id>/applications", methods=["GET"])
@project_owner_only("project_id")
def list_applications(project_id):
    """GET /projects/<id>/applications — owner sees all applications."""
    apps = CollabApplication.query.filter_by(project_id=project_id).all()
    return jsonify([
        {
            "id": a.id,
            "applicant_id": a.applicant_id,
            "team_name": a.team_name,
            "cover_note": a.cover_note,
            "status": a.status,
            "created_at": a.created_at.isoformat(),
        }
        for a in apps
    ])


@bounty_collab_bp.route("/applications/<int:application_id>", methods=["PATCH"])
@authed_only
def update_application(application_id):
    """PATCH /applications/<id> — owner shortlists/accepts/rejects.
    Accepting creates a CollabTeamMember record automatically.
    """
    user = get_current_user()
    app_obj = CollabApplication.query.get_or_404(application_id)
    project = CollabProject.query.get_or_404(app_obj.project_id)

    if project.owner_id != user.id:
        abort(403, description="Only the project owner can update applications.")

    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").strip()
    valid = {"pending", "shortlisted", "accepted", "rejected", "withdrawn"}
    if new_status not in valid:
        abort(400, description=f"'status' must be one of: {sorted(valid)}")

    before_status = app_obj.status
    app_obj.status = new_status

    if new_status == "accepted":
        existing_member = CollabTeamMember.query.filter_by(
            project_id=project.id, user_id=app_obj.applicant_id
        ).first()
        if existing_member is None:
            db.session.add(
                CollabTeamMember(
                    project_id=project.id,
                    user_id=app_obj.applicant_id,
                    is_team_lead=False,
                    payout_percentage=0,
                    status="active",
                )
            )

    _audit(
        project.id, user.id, "application_updated",
        {"status": before_status},
        {"status": new_status, "application_id": application_id},
    )
    db.session.commit()

    return jsonify({"id": app_obj.id, "status": app_obj.status})


@bounty_collab_bp.route("/projects/<int:project_id>/team", methods=["GET"])
@authed_only
def list_team_members(project_id):
    """GET /projects/<id>/team — list active team members."""
    CollabProject.query.get_or_404(project_id)
    members = CollabTeamMember.query.filter_by(
        project_id=project_id, status="active"
    ).all()
    return jsonify([
        {
            "id": m.id,
            "user_id": m.user_id,
            "is_team_lead": m.is_team_lead,
            "payout_percentage": float(m.payout_percentage),
            "status": m.status,
            "joined_at": m.joined_at.isoformat() if m.joined_at else None,
        }
        for m in members
    ])


@bounty_collab_bp.route("/team-members/<int:member_id>", methods=["PATCH"])
@authed_only
def update_team_member(member_id):
    """PATCH /team-members/<id> — owner sets payout_percentage or removes member.
    Blocked after team_locked.
    """
    user = get_current_user()
    member = CollabTeamMember.query.get_or_404(member_id)
    project = CollabProject.query.get_or_404(member.project_id)

    if project.owner_id != user.id:
        abort(403, description="Only the project owner can update team members.")
    if project.status in EDIT_LOCKED_STATES:
        abort(409, description="Team cannot be modified after team_locked.")

    data = request.get_json(silent=True) or {}
    before = {
        "payout_percentage": float(member.payout_percentage),
        "status": member.status,
    }

    if "payout_percentage" in data:
        pct = float(data["payout_percentage"])
        if pct < 0 or pct > 100:
            abort(400, description="payout_percentage must be between 0 and 100.")
        member.payout_percentage = pct

    if data.get("status") == "removed":
        member.status = "removed"

    if data.get("is_team_lead") is not None:
        member.is_team_lead = bool(data["is_team_lead"])

    _audit(
        project.id, user.id, "team_member_updated",
        before,
        {
            "payout_percentage": float(member.payout_percentage),
            "status": member.status,
        },
    )
    db.session.commit()

    return jsonify({
        "id": member.id,
        "user_id": member.user_id,
        "payout_percentage": float(member.payout_percentage),
        "is_team_lead": member.is_team_lead,
        "status": member.status,
    })


# ===========================================================================
# EXPERT: Submit deliverables
# ===========================================================================

@bounty_collab_bp.route("/projects/<int:project_id>/deliverables", methods=["POST"])
@active_team_member_only("project_id")
def submit_deliverable(project_id):
    """POST /projects/<id>/deliverables — active team member submits work.
    Transitions project to submitted_for_review automatically.
    """
    user = get_current_user()
    project = g.bntc_project

    if project.status not in ("in_progress", "revision_requested"):
        abort(
            409,
            description=(
                "Deliverables can only be submitted when project is "
                "in_progress or revision_requested."
            ),
        )

    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content and not data.get("file_ref"):
        abort(400, description="'content' or 'file_ref' is required.")

    last = (
        CollabDeliverable.query
        .filter_by(project_id=project_id)
        .order_by(CollabDeliverable.version_number.desc())
        .first()
    )
    version = (last.version_number + 1) if last else 1

    deliverable = CollabDeliverable(
        project_id=project_id,
        submitted_by=user.id,
        content=content,
        file_ref=data.get("file_ref"),
        version_number=version,
        status="submitted",
    )
    db.session.add(deliverable)
    db.session.flush()

    # Move to submitted_for_review
    if project.status == "in_progress":
        transition_project_status(project, "submitted_for_review", user)
    elif project.status == "revision_requested":
        # revision_requested -> in_progress (system) -> submitted_for_review (team)
        transition_project_status(project, "in_progress", user, is_system=True)
        transition_project_status(project, "submitted_for_review", user)

    _audit(
        project_id, user.id, "deliverable_submitted",
        {}, {"deliverable_id": deliverable.id, "version": version}
    )
    db.session.commit()

    return jsonify({
        "id": deliverable.id,
        "version_number": version,
        "status": deliverable.status,
        "project_status": project.status,
    }), 201


@bounty_collab_bp.route("/projects/<int:project_id>/deliverables", methods=["GET"])
@owner_or_active_team_member("project_id")
def list_deliverables(project_id):
    """GET /projects/<id>/deliverables — owner or team members see all."""
    deliverables = (
        CollabDeliverable.query
        .filter_by(project_id=project_id)
        .order_by(CollabDeliverable.version_number.desc())
        .all()
    )
    return jsonify([
        {
            "id": d.id,
            "submitted_by": d.submitted_by,
            "version_number": d.version_number,
            "status": d.status,
            "reviewer_note": d.reviewer_note,
            "created_at": d.created_at.isoformat(),
        }
        for d in deliverables
    ])


# ===========================================================================
# ROLE INFO API — used by frontend to show/hide Post vs Apply buttons
# ===========================================================================

@bounty_collab_bp.route("/me/role", methods=["GET"])
@authed_only
def my_role():
    """GET /me/role — returns the current user's org type and role within it.

    Response shape:
      {
        "user_id": 1,
        "org_type": "company" | "university" | "community" | null,
        "org_role": "owner" | "admin" | "member" | null,
        "org_id": 3 | null,
        "can_post_project": true | false,
        "can_apply": true | false
      }

    Frontends should call this once on load to conditionally render:
      can_post_project → show "Post Project" button  (enterprise/company)
      can_apply        → show "Apply" button          (university + verified)
    """
    from .permissions import get_user_org_info

    user = get_current_user()
    info = get_user_org_info(user.id)
    org_type = info["org_type"]
    verified = bool(getattr(user, "verified", False))

    return jsonify({
        "user_id": user.id,
        "org_type": org_type,
        "org_role": info["org_role"],
        "org_id": info["org_id"],
        "can_post_project": org_type == "company",
        "can_apply": org_type == "university" and verified,
        "is_verified": verified,
    })


# ===========================================================================
# WALLET API
# ===========================================================================

@bounty_collab_bp.route("/wallet", methods=["GET"])
@authed_only
def my_wallet():
    """GET /wallet — own wallet only."""
    user = get_current_user()
    wallet = CollabWallet.query.filter_by(user_id=user.id).first()
    if wallet is None:
        return jsonify({"user_id": user.id, "pending_balance": 0, "internal_balance": 0})
    return jsonify({
        "user_id": user.id,
        "pending_balance": wallet.pending_balance,
        "internal_balance": wallet.internal_balance,
        "updated_at": wallet.updated_at.isoformat() if wallet.updated_at else None,
    })


@bounty_collab_bp.route("/wallet/transactions", methods=["GET"])
@authed_only
def my_wallet_transactions():
    """GET /wallet/transactions — own transactions only."""
    user = get_current_user()
    wallet = CollabWallet.query.filter_by(user_id=user.id).first()
    if wallet is None:
        return jsonify([])
    txns = (
        CollabWalletTransaction.query
        .filter_by(wallet_id=wallet.id)
        .order_by(CollabWalletTransaction.created_at.desc())
        .all()
    )
    return jsonify([
        {
            "id": t.id,
            "type": t.type,
            "amount": t.amount,
            "balance_after": t.balance_after,
            "project_id": t.project_id,
            "created_at": t.created_at.isoformat(),
        }
        for t in txns
    ])


# ===========================================================================
# ADMIN
# ===========================================================================

@bounty_collab_bp.route("/admin/bounty-collab", methods=["GET"])
@admins_only
def admin_dashboard():
    """Admin dashboard — all projects overview."""
    projects = (
        CollabProject.query
        .order_by(CollabProject.created_at.desc())
        .all()
    )
    return render_template(
        "bounty_collab/admin_dashboard.html", projects=projects, dispute_view=False
    )


@bounty_collab_bp.route("/admin/bounty-collab/escrow-ledger", methods=["GET"])
@admins_only
def admin_escrow_ledger():
    """GET /admin/escrow-ledger — all escrow records."""
    ledgers = CollabEscrowLedger.query.all()
    return jsonify([
        {
            "id": l.id,
            "project_id": l.project_id,
            "total_funded": l.total_funded,
            "platform_commission_amount": l.platform_commission_amount,
            "researcher_pool_amount": l.researcher_pool_amount,
            "status": l.status,
            "funded_at": l.funded_at.isoformat() if l.funded_at else None,
            "released_at": l.released_at.isoformat() if l.released_at else None,
        }
        for l in ledgers
    ])


@bounty_collab_bp.route("/admin/bounty-collab/disputes", methods=["GET"])
@admins_only
def admin_disputes():
    """GET /admin/disputes — disputed projects queue."""
    projects = CollabProject.query.filter_by(status="disputed").all()
    return render_template(
        "bounty_collab/admin_dashboard.html", projects=projects, dispute_view=True
    )


@bounty_collab_bp.route(
    "/admin/bounty-collab/disputes/<int:project_id>/resolve",
    methods=["POST"],
)
@admins_only
def admin_resolve_dispute(project_id):
    """POST — admin resolves a dispute: approve (pay out) or refund."""
    admin = get_current_user()
    project = CollabProject.query.get_or_404(project_id)
    data = request.get_json(silent=True) or {}
    resolution = data.get("resolution")

    if resolution == "approve":
        transition_project_status(project, "approved", admin, is_admin=True)
        release_payout(project, admin)
        db.session.commit()
        return jsonify({"status": project.status, "message": "Approved and payout released."})

    if resolution == "refund":
        transition_project_status(project, "cancelled", admin, is_admin=True)
        refund_escrow(project, admin)
        db.session.commit()
        return jsonify({"status": project.status, "message": "Cancelled and refunded."})

    abort(400, description="'resolution' must be 'approve' or 'refund'.")


@bounty_collab_bp.route("/admin/bounty-collab/audit-log", methods=["GET"])
@admins_only
def admin_audit_log():
    """GET /admin/audit-log — paginated audit trail."""
    from .models import CollabAuditLog

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    entries = (
        CollabAuditLog.query
        .order_by(CollabAuditLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return jsonify([
        {
            "id": e.id,
            "project_id": e.project_id,
            "actor_id": e.actor_id,
            "action": e.action,
            "before_state": e.before_state,
            "after_state": e.after_state,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ])
