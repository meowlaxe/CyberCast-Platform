"""
CTFd Team Finder Plugin
=========================
"Looking for teammates" board. Fully self-contained.

Install: copy this folder into CTFd/CTFd/plugins/ctfd_team_finder
"""

from CTFd.plugins import register_plugin_assets_directory, register_plugin_script

from .models import TeamFinderInterests, TeamFinderPosts  # noqa: F401
from .routes import team_finder_bp


def load(app):
    app.db.create_all()
    app.register_blueprint(team_finder_bp)

    register_plugin_assets_directory(app, base_path="/plugins/ctfd_team_finder/static/")
    register_plugin_script("/plugins/ctfd_team_finder/static/js/nav.js")
