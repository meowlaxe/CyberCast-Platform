# =============================================================================
# File: CTFd/plugins/ctfd_bounty_collab/routes.py
# Plugin: ctfd_bounty_collab
# Created: 2026-07-15  Author: Claude / CyberCast implementation
# Purpose: All HTTP endpoints for the bounty-collab plugin.
#          url_prefix: /plugins/bounty-collab
#          Blueprint name: bounty_collab
#          Every mutating endpoint writes to audit_log via services.py.
# =============================================================================

import csv
import datetime
import io
import os

from flask import Blueprint, Response, abort, g, jsonify, redirect, render_template, request, url_for

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
    CollabUserProfile,
    CollabWallet,
    CollabWalletTransaction,
)
from .permissions import (
    active_team_member_only,
    enterprise_only,
    expert_verified_only,
    full_brief_access,
    get_user_role,
    owner_or_active_team_member,
    partner_only,
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


# All abort() calls within this blueprint return JSON so fetch() can parse them.
@bounty_collab_bp.errorhandler(400)
@bounty_collab_bp.errorhandler(403)
@bounty_collab_bp.errorhandler(404)
@bounty_collab_bp.errorhandler(409)
def _json_error(e):
    from werkzeug.exceptions import HTTPException
    code = e.code if isinstance(e, HTTPException) else 500
    return jsonify({"error": getattr(e, "description", str(e))}), code


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _cents_to_usd(cents: int) -> float:
    """Convert internal cents storage to display dollars."""
    return round((cents or 0) / 100, 2)


def _usd_to_cents(dollars) -> int:
    """Convert dollar input from forms to internal cents storage."""
    return int(float(dollars or 0) * 100)


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
        "budget_usd": _cents_to_usd(p.budget_total),
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
    user = get_current_user()
    is_admin = getattr(user, "type", None) == "admin"
    role = get_user_role(user.id) if not is_admin else "partner"

    # No profile yet — send to role setup
    if role is None and not is_admin:
        return redirect(url_for("bounty_collab.setup_role_view"))

    # Students have no bounty access
    if role == "student" and not is_admin:
        return render_template("bounty_collab/no_access.html")

    # Partners see their own projects too (all statuses) plus public ones
    if role == "partner" or is_admin:
        projects = (
            CollabProject.query
            .filter(CollabProject.owner_id == user.id)
            .order_by(CollabProject.created_at.desc())
            .all()
        )
    else:
        projects = (
            CollabProject.query
            .filter(CollabProject.status.in_(["published", "recruiting", "applications_closed"]))
            .order_by(CollabProject.created_at.desc())
            .all()
        )
    return render_template(
        "bounty_collab/project_list.html",
        projects=projects,
        cents_to_usd=_cents_to_usd,
        user_role=role,
    )


@bounty_collab_bp.route("/projects/<int:project_id>/view", methods=["GET"])
@authed_only
def project_detail_view(project_id):
    project = CollabProject.query.get_or_404(project_id)
    user = get_current_user()
    applied = CollabApplication.query.filter_by(
        project_id=project_id, applicant_id=user.id
    ).first()
    is_owner = project.owner_id == user.id
    team_members = CollabTeamMember.query.filter_by(
        project_id=project_id, status="active"
    ).all() if is_owner else []

    applications = []
    applicant_details = {}   # app.id → {name, email, institution}
    if is_owner:
        from CTFd.models import Users
        applications = CollabApplication.query.filter_by(project_id=project_id).all()
        applicant_ids = [a.applicant_id for a in applications if a.applicant_id]
        if applicant_ids:
            user_rows = {u.id: u for u in Users.query.filter(Users.id.in_(applicant_ids)).all()}
            profile_rows = {
                p.user_id: p
                for p in CollabUserProfile.query.filter(
                    CollabUserProfile.user_id.in_(applicant_ids)
                ).all()
            }
            for a in applications:
                uid = a.applicant_id
                u_obj = user_rows.get(uid)
                p_obj = profile_rows.get(uid)
                applicant_details[a.id] = {
                    "name": u_obj.name if u_obj else f"User #{uid}",
                    "email": u_obj.email if u_obj else "",
                    "institution": p_obj.institution if p_obj else "",
                    "credential_id": p_obj.credential_id if p_obj else "",
                    "expertise_areas": p_obj.expertise_areas if p_obj else "",
                    "bio": p_obj.bio if p_obj else "",
                    "profile_url": p_obj.profile_url if p_obj else "",
                }

    is_team_member = CollabTeamMember.query.filter_by(
        project_id=project_id, user_id=user.id, status="active"
    ).first()
    is_admin = getattr(user, "type", None) == "admin"
    user_role = get_user_role(user.id) if not is_admin else "partner"
    return render_template(
        "bounty_collab/project_detail.html",
        project=project,
        applied=applied,
        is_owner=is_owner,
        is_team_member=is_team_member,
        team_members=team_members,
        applications=applications,
        applicant_details=applicant_details,
        budget_usd=_cents_to_usd(project.budget_total),
        user_role=user_role,
    )


@bounty_collab_bp.route("/my-applications", methods=["GET"])
@authed_only
def my_applications_view():
    user = get_current_user()
    apps = (
        CollabApplication.query
        .filter_by(applicant_id=user.id)
        .order_by(CollabApplication.created_at.desc())
        .all()
    )
    project_map = {
        p.id: p for p in CollabProject.query.filter(
            CollabProject.id.in_([a.project_id for a in apps])
        ).all()
    } if apps else {}
    return render_template(
        "bounty_collab/my_applications.html",
        applications=apps,
        project_map=project_map,
        cents_to_usd=_cents_to_usd,
    )


@bounty_collab_bp.route("/setup-role", methods=["GET", "POST"])
@authed_only
def setup_role_view():
    """GET/POST /setup-role — one-time role selection (student/expert/partner).
    Saved to bntc_user_profiles.  Admin accounts skip this (no profile needed).
    """
    user = get_current_user()
    existing = CollabUserProfile.query.filter_by(user_id=user.id).first()

    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        role = (data.get("role") or "").strip().lower()
        institution = (data.get("institution") or "").strip()
        submitted_key = (data.get("access_key") or "").strip()
        bio = (data.get("bio") or "").strip()
        expertise_areas = (data.get("expertise_areas") or "").strip()
        profile_url = (data.get("profile_url") or "").strip()
        credential_id = (data.get("credential_id") or "").strip()

        valid_roles = {"student", "expert", "partner"}
        if role not in valid_roles:
            err = "Please select a valid role."
            if request.is_json:
                return jsonify({"error": err}), 400
            return render_template("bounty_collab/role_select.html", error=err, existing=existing)

        # Experts: open enrollment — credentials (institution, staff ID, expertise) are their
        # qualification. Vetting happens when partners review applications.
        # Partners: require admin-issued key from BNTC_PARTNER_KEY env var.
        partner_key = os.environ.get("BNTC_PARTNER_KEY", "").strip()

        if role == "partner" and partner_key and submitted_key != partner_key:
            err = "Invalid Partner access key. Please obtain the key from the platform administrator."
            if request.is_json:
                return jsonify({"error": err}), 403
            return render_template("bounty_collab/role_select.html", error=err, existing=existing)

        if existing:
            existing.role = role
            existing.institution = institution
            existing.bio = bio
            existing.expertise_areas = expertise_areas
            existing.profile_url = profile_url
            existing.credential_id = credential_id
        else:
            existing = CollabUserProfile(
                user_id=user.id,
                role=role,
                institution=institution,
                bio=bio,
                expertise_areas=expertise_areas,
                profile_url=profile_url,
                credential_id=credential_id,
            )
            db.session.add(existing)

        db.session.commit()

        if request.is_json:
            return jsonify({"role": role, "message": "Profile saved."})

        if role == "student":
            return redirect("/")
        return redirect(url_for("bounty_collab.project_list_view"))

    return render_template(
        "bounty_collab/role_select.html",
        existing=existing,
        error=None,
    )


@bounty_collab_bp.route("/projects/new", methods=["GET"])
@partner_only
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
    budget = data.get("budget_usd") or data.get("budget_total")
    if budget is None or float(budget) <= 0:
        abort(400, description="'budget_usd' (dollars, > 0) is required.")
    budget_cents = _usd_to_cents(budget)

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
        budget_total=budget_cents,
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


@bounty_collab_bp.route("/projects/<int:project_id>/unpublish", methods=["POST"])
@project_owner_only("project_id")
def unpublish_project(project_id):
    """POST /projects/<id>/unpublish — published → draft (partner pulls listing back)."""
    user = get_current_user()
    project = g.bntc_project
    transition_project_status(project, "draft", user)
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


@bounty_collab_bp.route("/projects/<int:project_id>/close-recruiting", methods=["POST"])
@project_owner_only("project_id")
def close_recruiting(project_id):
    """POST /projects/<id>/close-recruiting — recruiting → applications_closed.
    Partner stops accepting new applications while reviewing existing ones.
    """
    user = get_current_user()
    project = g.bntc_project
    transition_project_status(project, "applications_closed", user)
    db.session.commit()
    return jsonify({"status": project.status})


@bounty_collab_bp.route("/projects/<int:project_id>/reopen-recruiting", methods=["POST"])
@project_owner_only("project_id")
def reopen_recruiting(project_id):
    """POST /projects/<id>/reopen-recruiting — applications_closed → recruiting.
    Partner re-opens applications if needed.
    """
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
@authed_only
def apply_to_project(project_id):
    """POST /projects/<id>/apply — individual expert applies.
    Always returns JSON so the fetch() handler can parse errors cleanly.
    Admins can apply to any project for testing (except their own).
    Regular users need a university org + verified account.
    """
    user = get_current_user()
    project = CollabProject.query.get_or_404(project_id)

    # Owner cannot apply to their own project
    if project.owner_id == user.id:
        return jsonify({"error": "You cannot apply to your own project."}), 403

    # Role check — admins bypass, others need expert role + verified
    is_admin = getattr(user, "type", None) == "admin"
    if not is_admin:
        role = get_user_role(user.id)
        if role is None:
            return jsonify({"error": "Please set up your profile first."}), 403
        if role == "student":
            return jsonify({"error": "Bounty projects are not available for students."}), 403
        if role == "partner":
            return jsonify({"error": "Company Partners cannot apply to projects."}), 403
        if role != "expert":
            return jsonify({"error": "A University Expert account is required to apply."}), 403

    if project.status not in ("published", "recruiting", "applications_closed"):
        return jsonify({
            "error": f"This project is not accepting applications (status: {project.status})."
        }), 409

    existing = (
        CollabApplication.query
        .filter_by(project_id=project_id, applicant_id=user.id)
        .filter(CollabApplication.status != "withdrawn")
        .first()
    )
    if existing:
        return jsonify({
            "error": "You have already applied to this project.",
            "application_id": existing.id,
            "status": existing.status,
        }), 409

    data = request.get_json(silent=True) or {}
    cover_note = (data.get("cover_note") or "").strip()
    if not cover_note:
        return jsonify({"error": "A cover note is required to apply."}), 400

    app_obj = CollabApplication(
        project_id=project_id,
        applicant_id=user.id,
        team_name=None,          # removed — individual applications only
        cover_note=cover_note,
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


@bounty_collab_bp.route("/projects/<int:project_id>/applications/export", methods=["GET"])
@project_owner_only("project_id")
def export_applications_csv(project_id):
    """GET /projects/<id>/applications/export — download all applications as CSV.
    Includes applicant name, email, institution, cover note, status, applied date.
    Owner only.
    """
    from CTFd.models import Users
    project = g.bntc_project
    apps = CollabApplication.query.filter_by(project_id=project_id).all()

    applicant_ids = [a.applicant_id for a in apps if a.applicant_id]
    user_map = {}
    profile_map = {}
    if applicant_ids:
        user_map = {u.id: u for u in Users.query.filter(Users.id.in_(applicant_ids)).all()}
        profile_map = {
            p.user_id: p
            for p in CollabUserProfile.query.filter(
                CollabUserProfile.user_id.in_(applicant_ids)
            ).all()
        }

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Application ID", "Name", "Email", "Institution", "Staff/Student ID",
        "Expertise Areas", "Bio", "Profile URL", "Cover Note", "Status", "Applied At"
    ])
    for a in apps:
        u = user_map.get(a.applicant_id)
        p = profile_map.get(a.applicant_id)
        writer.writerow([
            a.id,
            u.name if u else f"User #{a.applicant_id}",
            u.email if u else "",
            p.institution if p else "",
            p.credential_id if p else "",
            p.expertise_areas if p else "",
            (p.bio or "").replace("\n", " ") if p else "",
            p.profile_url if p else "",
            (a.cover_note or "").replace("\n", " "),
            a.status,
            a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "",
        ])

    filename = f"applications_project{project_id}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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

@bounty_collab_bp.route("/me/profile", methods=["GET"])
@authed_only
def my_profile():
    """GET /me/profile — current user's bounty profile (role + credentials).
    Used by the Settings > Bounty Role tab.
    """
    user = get_current_user()
    is_admin = getattr(user, "type", None) == "admin"
    role = "admin" if is_admin else get_user_role(user.id)

    profile = CollabUserProfile.query.filter_by(user_id=user.id).first()

    return jsonify({
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": role,
        "is_admin": is_admin,
        "needs_setup": role is None and not is_admin,
        "institution": profile.institution if profile else None,
        "bio": profile.bio if profile else None,
        "expertise_areas": profile.expertise_areas if profile else None,
        "profile_url": profile.profile_url if profile else None,
        "credential_id": profile.credential_id if profile else None,
        "can_post_project": role in ("partner", "admin"),
        "can_apply": role == "expert",
    })


@bounty_collab_bp.route("/me/role", methods=["GET"])
@authed_only
def my_role():
    """GET /me/role — returns the current user's bounty-system role.

    Response shape:
      {
        "user_id": 1,
        "role": "student" | "expert" | "partner" | null,
        "is_admin": false,
        "can_post_project": true | false,
        "can_apply": true | false,
        "needs_setup": true | false
      }
    """
    from .permissions import get_user_org_info

    user = get_current_user()
    is_admin = getattr(user, "type", None) == "admin"
    role = "partner" if is_admin else get_user_role(user.id)
    verified = bool(getattr(user, "verified", False))

    # org info for legacy context
    info = get_user_org_info(user.id)

    return jsonify({
        "user_id": user.id,
        "role": role,
        "is_admin": is_admin,
        "org_type": info["org_type"],
        "org_role": info["org_role"],
        "org_id": info["org_id"],
        "can_post_project": role == "partner" or is_admin,
        "can_apply": role == "expert" and verified,
        "is_verified": verified,
        "needs_setup": role is None and not is_admin,
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


@bounty_collab_bp.route("/wallet/withdraw", methods=["POST"])
@authed_only
def request_withdrawal():
    """POST /wallet/withdraw — expert requests an external payout.

    Deducts amount from internal_balance immediately and logs a
    withdrawal_requested transaction.  An admin processes the actual
    bank/PayPal transfer externally.

    Body: { amount_cents: int, method: str, details: str }
    """
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    amount_cents = int(data.get("amount_cents") or 0)
    method = (data.get("method") or "").strip()
    details = (data.get("details") or "").strip()

    if amount_cents <= 0:
        abort(400, description="amount_cents must be a positive integer.")
    if not details:
        abort(400, description="payment details are required.")

    wallet = CollabWallet.query.filter_by(user_id=user.id).first()
    if wallet is None or wallet.internal_balance < amount_cents:
        abort(409, description="Insufficient balance for this withdrawal.")

    wallet.internal_balance -= amount_cents
    wallet.updated_at = datetime.datetime.utcnow()

    note = f"{method}: {details}"
    db.session.add(
        CollabWalletTransaction(
            wallet_id=wallet.id,
            user_id=user.id,
            project_id=None,
            type="withdrawal_requested",
            amount=amount_cents,
            balance_after=wallet.internal_balance,
        )
    )

    _audit(
        project_id=None,
        actor_id=user.id,
        action="withdrawal_requested",
        before={"balance": wallet.internal_balance + amount_cents},
        after={
            "balance": wallet.internal_balance,
            "amount": amount_cents,
            "method": method,
            "details": details,
        },
    )
    db.session.commit()

    return jsonify({
        "message": "Withdrawal request submitted.",
        "amount_cents": amount_cents,
        "balance_after": wallet.internal_balance,
    }), 201


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
