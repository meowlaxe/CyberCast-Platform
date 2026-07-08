"""
CTFd Learning Paths Plugin
============================
Structured curriculum + live progress tracking (computed from CTFd's own
Solves table - no separate "progress" data is stored). Fully self-contained;
only dependency is CTFd core's own Challenges/Solves tables, not any other
plugin in this family.

Install: copy this folder into CTFd/CTFd/plugins/ctfd_learning_paths
"""

from CTFd.plugins import (
    register_admin_plugin_menu_bar,
    register_plugin_assets_directory,
    register_plugin_script,
)

from .models import LearningPaths, LearningPathSteps  # noqa: F401
from .routes import learning_paths_bp


def load(app):
    app.db.create_all()
    app.register_blueprint(learning_paths_bp)

    register_plugin_assets_directory(
        app, base_path="/plugins/ctfd_learning_paths/static/"
    )
    register_plugin_script("/plugins/ctfd_learning_paths/static/js/nav.js")
    register_admin_plugin_menu_bar(
        title="Learning Paths", route="/plugins/platform-plus/admin/learning-paths"
    )
