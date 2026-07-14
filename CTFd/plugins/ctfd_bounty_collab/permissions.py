# =============================================================================
# File: CTFd/plugins/ctfd_bounty_collab/permissions.py
# Plugin: ctfd_bounty_collab
# Created: 2026-07-15  Author: Claude / CyberCast implementation
# Modified: 2026-07-15  — Added get_user_org_info() returning (org_type, role)
#                          so callers can inspect both the org type AND the
#                          user's role within that org (owner/admin/member).
#                          Fixed apply_to_project: expert_verified_only now
#                          blocks company-org users from applying.
# Purpose: Reusable permission decorators for all bounty-collab routes.
#
# Role model (sourced from ctfd_organizations):
#   org_organizations.org_type   "company"    → Enterprise Partner
#                                "university" → University Expert
#                                "community"  → Community member
#   org_organization_members.role "owner" | "admin" | "member"
#
# Posting a project  → @enterprise_only  (any company-org member)
# Applying           → @expert_verified_only  (university-org + verified)
# Submitting work    → @active_team_member_only  (locked-in researcher)
# Admin controls     → CTFd @admins_only  (platform admin users.type='admin')
# =============================================================================

from functools import wraps

from flask import abort, g

from CTFd.utils.decorators import authed_only
from CTFd.utils.user import get_current_user

from .models import CollabNdaAcceptance, CollabProject, CollabTeamMember


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def get_user_org_info(user_id: int) -> dict:
    """Return {"org_type": str|None, "org_role": str|None, "org_id": int|None}.

    org_type  — 'company' | 'university' | 'community' | None (no org)
    org_role  — 'owner' | 'admin' | 'member' | None
    org_id    — integer PK of the org, or None

    Lazy-imports ctfd_organizations to avoid circular imports.
    If a user belongs to multiple orgs the first membership row is used
    (users are expected to belong to one primary org on this platform).
    """
    try:
        from CTFd.plugins.ctfd_organizations.models import (
            OrganizationMembers,
            Organizations,
        )

        membership = OrganizationMembers.query.filter_by(user_id=user_id).first()
        if membership is None:
            return {"org_type": None, "org_role": None, "org_id": None}
        org = Organizations.query.get(membership.organization_id)
        if org is None:
            return {"org_type": None, "org_role": None, "org_id": None}
        return {
            "org_type": org.org_type,
            "org_role": membership.role,   # owner | admin | member
            "org_id": org.id,
        }
    except Exception:
        return {"org_type": None, "org_role": None, "org_id": None}


def _get_user_org_type(user_id: int):
    """Thin helper — returns org_type string or None."""
    return get_user_org_info(user_id)["org_type"]


def _resolve_project(project_id: int) -> CollabProject:
    project = CollabProject.query.get(project_id)
    if project is None:
        abort(404, description="Project not found.")
    return project


# ---------------------------------------------------------------------------
# Role decorators
# ---------------------------------------------------------------------------

def enterprise_only(f):
    """Allow only users whose org is org_type='company' (any role within the org).

    To restrict to org owner/admin only, swap the check:
        info["org_role"] not in ("owner", "admin")
    """

    @wraps(f)
    @authed_only
    def decorated(*args, **kwargs):
        user = get_current_user()
        info = get_user_org_info(user.id)
        if info["org_type"] != "company":
            abort(
                403,
                description=(
                    "Enterprise (company organisation) account required. "
                    "Your account is not linked to a company organisation."
                ),
            )
        return f(*args, **kwargs)

    return decorated


def expert_only(f):
    """Allow only users whose org is org_type='university' (any role)."""

    @wraps(f)
    @authed_only
    def decorated(*args, **kwargs):
        user = get_current_user()
        if _get_user_org_type(user.id) != "university":
            abort(
                403,
                description=(
                    "University/Expert account required. "
                    "Your account is not linked to a university organisation."
                ),
            )
        return f(*args, **kwargs)

    return decorated


def expert_verified_only(f):
    """Allow only university-org users who are also verified.

    This is the correct gate for 'apply to project':
      - must belong to a university org  (not a company — companies cannot apply)
      - must be verified by the platform
    """

    @wraps(f)
    @authed_only
    def decorated(*args, **kwargs):
        user = get_current_user()
        org_type = _get_user_org_type(user.id)

        if org_type == "company":
            abort(
                403,
                description=(
                    "Enterprise accounts cannot apply to bounty projects. "
                    "Only university/expert accounts may apply."
                ),
            )
        if org_type != "university":
            abort(
                403,
                description=(
                    "A verified university/expert account is required to apply. "
                    "Join a university organisation first."
                ),
            )
        if not getattr(user, "verified", False):
            abort(
                403,
                description=(
                    "Your account must be verified before you can apply "
                    "to a bounty project."
                ),
            )
        return f(*args, **kwargs)

    return decorated


def require_verified(f):
    """Block unverified users (CTFd Users.verified boolean).
    Does NOT check org type — use expert_verified_only for apply endpoints.
    """

    @wraps(f)
    @authed_only
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not getattr(user, "verified", False):
            abort(
                403,
                description="Account must be verified to perform this action.",
            )
        return f(*args, **kwargs)

    return decorated


# ---------------------------------------------------------------------------
# Project-scoped decorator factories
# ---------------------------------------------------------------------------

def project_owner_only(project_id_kwarg: str = "project_id"):
    """Decorator factory — rejects anyone who is not the project owner."""

    def decorator(f):
        @wraps(f)
        @authed_only
        def decorated(*args, **kwargs):
            pid = kwargs.get(project_id_kwarg)
            project = _resolve_project(pid)
            user = get_current_user()
            if project.owner_id != user.id:
                abort(
                    403,
                    description="Only the project owner can perform this action.",
                )
            g.bntc_project = project
            return f(*args, **kwargs)

        return decorated

    return decorator


def active_team_member_only(project_id_kwarg: str = "project_id"):
    """Decorator factory — rejects anyone not an active team member."""

    def decorator(f):
        @wraps(f)
        @authed_only
        def decorated(*args, **kwargs):
            pid = kwargs.get(project_id_kwarg)
            project = _resolve_project(pid)
            user = get_current_user()
            member = CollabTeamMember.query.filter_by(
                project_id=pid, user_id=user.id, status="active"
            ).first()
            if member is None:
                abort(403, description="Active team membership required.")
            g.bntc_project = project
            g.bntc_team_member = member
            return f(*args, **kwargs)

        return decorated

    return decorator


def owner_or_active_team_member(project_id_kwarg: str = "project_id"):
    """Decorator factory — allows owner OR active team member."""

    def decorator(f):
        @wraps(f)
        @authed_only
        def decorated(*args, **kwargs):
            pid = kwargs.get(project_id_kwarg)
            project = _resolve_project(pid)
            user = get_current_user()
            is_owner = project.owner_id == user.id
            is_member = (
                CollabTeamMember.query.filter_by(
                    project_id=pid, user_id=user.id, status="active"
                ).first()
                is not None
            )
            if not is_owner and not is_member:
                abort(
                    403,
                    description="Project owner or active team member required.",
                )
            g.bntc_project = project
            return f(*args, **kwargs)

        return decorated

    return decorator


def full_brief_access(project_id_kwarg: str = "project_id"):
    """Decorator factory — owner OR accepted team member OR NDA accepted."""

    def decorator(f):
        @wraps(f)
        @authed_only
        def decorated(*args, **kwargs):
            pid = kwargs.get(project_id_kwarg)
            project = _resolve_project(pid)
            user = get_current_user()

            if project.owner_id == user.id:
                g.bntc_project = project
                return f(*args, **kwargs)

            is_accepted_member = CollabTeamMember.query.filter_by(
                project_id=pid, user_id=user.id, status="active"
            ).first()
            if is_accepted_member:
                g.bntc_project = project
                return f(*args, **kwargs)

            has_nda = CollabNdaAcceptance.query.filter_by(
                project_id=pid, user_id=user.id
            ).first()
            if has_nda:
                g.bntc_project = project
                return f(*args, **kwargs)

            abort(
                403,
                description=(
                    "Full brief access requires: project owner, accepted team "
                    "membership, or NDA acceptance."
                ),
            )

        return decorated

    return decorator
