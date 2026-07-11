"""
CTFd Student Teams Plugin
=========================
Permanent CyberCast learning communities built on top of CTFd users mode.
Student Teams are not CTFd built-in Teams and do not change challenge, solve,
flag, or scoreboard behavior.
"""

from flask import redirect, request, url_for

from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.migrations import upgrade

from .models import (  # noqa: F401
    StudentTeam,
    StudentTeamInvite,
    StudentTeamJoinRequest,
    StudentTeamMember,
    StudentTeamScoreCache,
    StudentTeamScoreEvent,
)
from .routes import student_teams_bp


def load(app):
    upgrade(plugin_name="ctfd_student_teams")
    app.register_blueprint(student_teams_bp)
    register_plugin_assets_directory(
        app, base_path="/plugins/ctfd_student_teams/static/"
    )

    @app.before_request
    def redirect_ctfd_team_routes_to_student_teams():
        path = request.path.rstrip("/")
        if path in ("/team", "/teams", "/teams/new", "/teams/join"):
            return redirect(url_for("student_teams.team_list"))
        return None
