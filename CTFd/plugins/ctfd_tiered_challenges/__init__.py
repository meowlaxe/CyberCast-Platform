"""CyberCast tiered-challenge access and bounty workflows."""

from CTFd.plugins.migrations import upgrade

from .models import BountySolution, ChallengeTier, TieredChallengeAccessLog  # noqa: F401
from .routes import tiered_challenges_bp


def load(app):
    """Register the plugin's database schema and HTTP routes with CTFd."""
    upgrade(plugin_name="ctfd_tiered_challenges")
    app.register_blueprint(tiered_challenges_bp)
