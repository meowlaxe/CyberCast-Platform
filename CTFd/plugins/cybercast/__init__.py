"""CyberCast rooms and profile API for CTFd users mode."""

from CTFd.plugins.migrations import upgrade

from .models import (  # noqa: F401
    CyberCastChallengeProfile,
    CyberCastRoomMember,
    CyberCastRoomSubmission,
    CyberCastUserProfile,
    CyberCastWorkingRoom,
)
from .routes import cybercast_bp


def load(app):
    """Apply CyberCast tables, then make the API available to CTFd."""
    upgrade(plugin_name="cybercast")
    app.register_blueprint(cybercast_bp)
