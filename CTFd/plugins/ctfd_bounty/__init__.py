"""
CTFd Bounty Plugin
===================
Enterprise bug bounty board. Fully self-contained.

Install: copy this folder into CTFd/CTFd/plugins/ctfd_bounty
"""

from CTFd.plugins import (
    register_admin_plugin_menu_bar,
    register_plugin_assets_directory,
    register_plugin_script,
)

from .models import BountyPrograms, BountySubmissions  # noqa: F401
from .routes import bounty_bp


def load(app):
    app.db.create_all()
    app.register_blueprint(bounty_bp)

    register_plugin_assets_directory(app, base_path="/plugins/ctfd_bounty/static/")
    register_plugin_script("/plugins/ctfd_bounty/static/js/nav.js")
    register_admin_plugin_menu_bar(
        title="Bounty Program", route="/plugins/platform-plus/admin/bounty"
    )
