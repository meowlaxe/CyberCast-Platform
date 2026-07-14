# =============================================================================
# File: CTFd/plugins/ctfd_bounty_collab/__init__.py
# Plugin: ctfd_bounty_collab
# Created: 2026-07-15  Author: Claude / CyberCast implementation
# Purpose: Plugin entry point — registers blueprint, assets directory, nav
#          script, and admin menu bar item following the ctfd_bounty pattern.
#          Called automatically by CTFd's plugin loader via load(app).
# =============================================================================

from CTFd.plugins import (
    register_admin_plugin_menu_bar,
    register_plugin_assets_directory,
    register_plugin_script,
)
from CTFd.plugins.migrations import upgrade

# noqa: F401 — imported so SQLAlchemy registers all bntc_ tables before
# app.db.create_all() is called.
from .models import (  # noqa: F401
    CollabApplication,
    CollabAuditLog,
    CollabDeliverable,
    CollabEscrowLedger,
    CollabNdaAcceptance,
    CollabProject,
    CollabTeamMember,
    CollabWallet,
    CollabWalletTransaction,
)
from .routes import bounty_collab_bp


def load(app):
    app.db.create_all()
    upgrade(plugin_name="ctfd_bounty_collab")
    app.register_blueprint(bounty_collab_bp)

    register_plugin_assets_directory(
        app, base_path="/plugins/ctfd_bounty_collab/static/"
    )
    register_plugin_script("/plugins/ctfd_bounty_collab/static/js/nav.js")
    register_admin_plugin_menu_bar(
        title="Bounty Collab",
        route="/plugins/bounty-collab/admin/bounty-collab",
    )
