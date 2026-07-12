"""
CTFd Organizations Plugin
==========================
University / company / community collaboration spaces.

Install: copy this folder into CTFd/CTFd/plugins/ctfd_organizations
This plugin is fully self-contained - it doesn't depend on any other
plugin in this family (bounty, team-finder, learning-paths, theme).
"""

from CTFd.plugins import register_plugin_assets_directory, register_plugin_script

from .models import OrganizationMembers, Organizations  # noqa: F401
from .routes import get_user_organization, organizations_bp


def load(app):
    app.db.create_all()
    app.register_blueprint(organizations_bp)

    # Exposes get_user_organization(user_id) to every Jinja template, so
    # theme pages (e.g. users/private.html) can show a user's
    # University/Company/Community badge without needing core route changes.
    app.jinja_env.globals["get_user_organization"] = get_user_organization

    register_plugin_assets_directory(
        app, base_path="/plugins/ctfd_organizations/static/"
    )
    register_plugin_script("/plugins/ctfd_organizations/static/js/nav.js")
