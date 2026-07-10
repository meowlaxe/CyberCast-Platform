"""
CyberCast monetization layer.

This plugin adds billing/subscription primitives on top of the existing
CyberCast features. It does not own learning paths, bounty programs,
organizations, challenges, or authentication.
"""

from CTFd.plugins import (
    register_admin_plugin_menu_bar,
    register_plugin_assets_directory,
    register_plugin_script,
)
from CTFd.plugins.migrations import upgrade

from .routes import monetization_bp
from .services import is_premium_user


def load(app):
    upgrade(plugin_name="ctfd_monetization")
    app.register_blueprint(monetization_bp)
    app.jinja_env.globals.update(is_premium_user=is_premium_user)

    register_plugin_assets_directory(
        app, base_path="/plugins/ctfd_monetization/static/"
    )
    register_plugin_script("/plugins/ctfd_monetization/static/js/nav.js")
    register_admin_plugin_menu_bar(
        title="Monetization", route="/plugins/platform-plus/admin/monetization"
    )
