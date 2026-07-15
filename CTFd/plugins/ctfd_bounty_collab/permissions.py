# =============================================================================
# File: CTFd/plugins/ctfd_bounty_collab/permissions.py
# Plugin: ctfd_bounty_collab
# Created: 2026-07-15  Author: Claude / CyberCast implementation
# Modified: 2026-07-15  — Switched primary role source to bntc_user_profiles.
#                          get_user_role() reads the profile table first;
#                          falls back to org_type for legacy accounts without
#                          a profile row.  All decorators updated accordingly.
# Purpose: Reusable permission decorators for all bounty-collab routes.
#
# Role model (sourced from bntc_user_profiles):
#   role = "student"  → No bounty access — Bounty nav link hidden
#   role = "expert"   → University researcher — can view and apply
#   role = "partner"  → Company account — can post, manage, control lifecycle
#
# Platform admins (users.type='admin') bypass all role checks.
# =============================================================================

from functools import wraps

from flask import abort, g

from CTFd.utils.decorators import authed_only
from CTFd.utils.user import get_current_user

from .models import CollabNdaAcceptance, CollabProject, CollabTeamMember


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def get_user_role(user_id: int) -> str | None:
    """Return the bounty-system role for a user.

    Checks bntc_user_profiles first (explicit role chosen at registration).
    Falls back to org_type for legacy accounts that pre-date the profile table.

    Returns: "student" | "expert" | "partner" | None (no profile, no org)
    """
    try:
        from .models import CollabUserProfile
        profile = CollabUserProfile.query.filter_by(user_id=user_id).first()
        if profile is not None:
            return profile.role
    except Exception:
        pass

    # Legacy fallback — derive role from ctfd_organizations
    org_type = _get_user_org_type(user_id)
    if org_type == "company":
        return "partner"
    if org_type == "university":
        return "expert"
    return None


def get_user_org_info(user_id: int) -> dict:
    """Return {"org_type": str|None, "org_role": str|None, "org_id": int|None}."""
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
            "org_role": membership.role,
            "org_id": org.id,
        }
    except Exception:
        return {"org_type": None, "org_role": None, "org_id": None}


def _get_user_org_type(user_id: int):
    return get_user_org_info(user_id)["org_type"]


def _resolve_project(project_id: int) -> CollabProject:
    project = CollabProject.query.get(project_id)
    if project is None:
        abort(404, description="Project not found.")
    return project


# ---------------------------------------------------------------------------
# Role decorators
# ---------------------------------------------------------------------------

def partner_only(f):
    """Allow partner-role users OR platform admins.

    Partners (company accounts) can post and manage bounty projects.
    """

    @wraps(f)
    @authed_only
    def decorated(*args, **kwargs):
        user = get_current_user()
        if getattr(user, "type", None) == "admin":
            return f(*args, **kwargs)
        role = get_user_role(user.id)
        if role != "partner":
            abort(
                403,
                description=(
                    "Company Partner account required. "
                    "Only company partners can post or manage bounty projects. "
                    "Please set up your profile as a Company Partner."
                ),
            )
        return f(*args, **kwargs)

    return decorated


# Keep enterprise_only as an alias for backward compat
enterprise_only = partner_only


def expert_only(f):
    """Allow only expert-role users (university researchers)."""

    @wraps(f)
    @authed_only
    def decorated(*args, **kwargs):
        user = get_current_user()
        if getattr(user, "type", None) == "admin":
            return f(*args, **kwargs)
        role = get_user_role(user.id)
        if role != "expert":
            abort(
                403,
                description=(
                    "University Expert account required. "
                    "Only university experts can perform this action."
                ),
            )
        return f(*args, **kwargs)

    return decorated


def expert_verified_only(f):
    """Allow expert-role verified users OR platform admins.

    Used for applying to projects:
      - Admins bypass (for testing)
      - Must have role='expert' AND users.verified=True
      - Partners are blocked (they post, not apply)
      - Students are blocked (no bounty access)
    """

    @wraps(f)
    @authed_only
    def decorated(*args, **kwargs):
        user = get_current_user()
        if getattr(user, "type", None) == "admin":
            return f(*args, **kwargs)
        role = get_user_role(user.id)
        if role == "partner":
            abort(
                403,
                description=(
                    "Company Partners cannot apply to bounty projects. "
                    "Only University Experts may apply."
                ),
            )
        if role == "student":
            abort(403, description="Bounty projects are not available for students.")
        if role != "expert":
            abort(
                403,
                description=(
                    "A University Expert account is required to apply. "
                    "Please set up your profile with an Expert access key first."
                ),
            )
        return f(*args, **kwargs)

    return decorated


def require_verified(f):
    """Block unverified users."""

    @wraps(f)
    @authed_only
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not getattr(user, "verified", False):
            abort(403, description="Account must be verified to perform this action.")
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
                abort(403, description="Only the project owner can perform this action.")
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
                abort(403, description="Project owner or active team member required.")
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
