"""
ctfd_student_teams.routes
-------------------------
Phase 1 Student Team CRUD routes.
"""

import re
import secrets

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from CTFd.models import Users, db
from CTFd.utils.decorators import authed_only
from CTFd.utils.user import get_current_user, is_admin

from .models import StudentTeam

student_teams_bp = Blueprint(
    "student_teams",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/plugins/platform-plus",
)


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


def unique_slug(name: str, team_id=None) -> str:
    base = slugify(name) or "student-team"
    slug = base
    suffix = 2
    query = StudentTeam.query.filter_by(slug=slug)
    if team_id is not None:
        query = query.filter(StudentTeam.id != team_id)

    while query.first():
        slug = f"{base}-{suffix}"
        suffix += 1
        query = StudentTeam.query.filter_by(slug=slug)
        if team_id is not None:
            query = query.filter(StudentTeam.id != team_id)
    return slug


def can_manage_team(team, user=None) -> bool:
    user = user or get_current_user()
    if user is None:
        return False
    return is_admin() or team.owner_id == user.id


def can_view_team(team, user=None) -> bool:
    if team.status != "active":
        return can_manage_team(team, user)
    if team.visibility == "private":
        return can_manage_team(team, user)
    return True


def build_team_from_form(team, user):
    name = request.form.get("name", "").strip()
    if not name:
        return "Team name is required."

    existing_name = StudentTeam.query.filter_by(name=name)
    if team.id is not None:
        existing_name = existing_name.filter(StudentTeam.id != team.id)
    if existing_name.first():
        return "A Student Team with this name already exists."

    team.name = name
    team.slug = unique_slug(name, team.id)
    team.description = request.form.get("description", "").strip()
    team.avatar = request.form.get("avatar", "").strip()
    team.banner = request.form.get("banner", "").strip()
    team.visibility = request.form.get("visibility", "public")
    if team.visibility not in ("public", "private", "unlisted"):
        team.visibility = "public"
    team.status = request.form.get("status", team.status or "active")
    if team.status not in ("active", "archived"):
        team.status = "active"
    if team.owner_id is None:
        team.owner_id = user.id
    if not team.invite_code:
        team.invite_code = secrets.token_urlsafe(16)
    return None


@student_teams_bp.route("/student-teams", strict_slashes=False)
def team_list():
    teams = (
        StudentTeam.query.filter_by(status="active", visibility="public")
        .order_by(StudentTeam.created_at.desc())
        .all()
    )
    return render_template("platform_plus/student_teams_list.html", teams=teams)


@student_teams_bp.route(
    "/student-teams/new", methods=["GET", "POST"], strict_slashes=False
)
@authed_only
def team_new():
    if request.method == "GET":
        return render_template("platform_plus/student_team_form.html", team=None)

    user = get_current_user()
    team = StudentTeam()
    error = build_team_from_form(team, user)
    if error:
        flash(error, "error")
        return redirect(url_for("student_teams.team_new"))

    db.session.add(team)
    db.session.commit()
    flash("Student Team created.", "success")
    return redirect(url_for("student_teams.team_detail", slug=team.slug))


@student_teams_bp.route("/student-teams/<slug>", strict_slashes=False)
def team_detail(slug):
    team = StudentTeam.query.filter_by(slug=slug).first_or_404()
    user = get_current_user()
    if not can_view_team(team, user):
        abort(404)

    owner = Users.query.get(team.owner_id) if team.owner_id else None
    return render_template(
        "platform_plus/student_team_detail.html",
        can_manage=can_manage_team(team, user),
        owner=owner,
        team=team,
    )


@student_teams_bp.route(
    "/student-teams/<slug>/edit", methods=["GET", "POST"], strict_slashes=False
)
@authed_only
def team_edit(slug):
    team = StudentTeam.query.filter_by(slug=slug).first_or_404()
    user = get_current_user()
    if not can_manage_team(team, user):
        abort(403)

    if request.method == "GET":
        return render_template("platform_plus/student_team_form.html", team=team)

    old_slug = team.slug
    error = build_team_from_form(team, user)
    if error:
        flash(error, "error")
        return redirect(url_for("student_teams.team_edit", slug=old_slug))

    db.session.commit()
    flash("Student Team updated.", "success")
    return redirect(url_for("student_teams.team_detail", slug=team.slug))


@student_teams_bp.route(
    "/student-teams/<slug>/archive", methods=["POST"], strict_slashes=False
)
@authed_only
def team_archive(slug):
    team = StudentTeam.query.filter_by(slug=slug).first_or_404()
    user = get_current_user()
    if not can_manage_team(team, user):
        abort(403)

    team.status = "archived"
    db.session.commit()
    flash("Student Team archived.", "success")
    return redirect(url_for("student_teams.team_list"))
