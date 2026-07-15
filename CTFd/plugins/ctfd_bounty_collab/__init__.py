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
    CollabUserProfile,
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

    # ---------------------------------------------------------------------------
    # Role-setup gate: redirect any authenticated user without a role profile
    # to /setup-role before they can access any page.  Once a profile row exists
    # in bntc_user_profiles the gate is permanently open for that user.
    # ---------------------------------------------------------------------------
    _SETUP_BYPASS = (
        "/plugins/bounty-collab/setup-role",
        "/login",
        "/logout",
        "/register",
        "/oauth",
        "/api/",
        "/static/",
        "/themes/",
        "/plugins/ctfd_bounty_collab/static/",
        "/plugins/bounty-collab/me/",
    )

    @app.before_request
    def _enforce_role_setup():
        from flask import redirect, request
        from CTFd.utils import user as user_utils

        if not user_utils.authed():
            return

        path = request.path

        # Skip non-HTML requests (static, API, our own plugin endpoints)
        for prefix in _SETUP_BYPASS:
            if path.startswith(prefix):
                return

        # Admins never need role setup
        from CTFd.utils.user import get_current_user
        user = get_current_user()
        if user is None or getattr(user, "type", None) == "admin":
            return

        # If no profile row exists → force role selection
        from .models import CollabUserProfile
        if CollabUserProfile.query.filter_by(user_id=user.id).first() is None:
            return redirect("/plugins/bounty-collab/setup-role")
