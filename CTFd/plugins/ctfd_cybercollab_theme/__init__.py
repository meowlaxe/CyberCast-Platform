"""
CTFd CyberCollab Theme Plugin
===============================
Purely visual reskin: dark cybersecurity theme + a signature node-network
animation on the homepage hero. No models, no routes, no dependency on any
other plugin - can be installed/removed independently of the feature
plugins (organizations, bounty, team-finder, learning-paths).

Install: copy this folder into CTFd/CTFd/plugins/ctfd_cybercollab_theme
"""

from CTFd.plugins import (
    register_plugin_assets_directory,
    register_plugin_script,
    register_plugin_stylesheet,
)


def load(app):
    register_plugin_assets_directory(
        app, base_path="/plugins/ctfd_cybercollab_theme/static/"
    )
    register_plugin_stylesheet("/plugins/ctfd_cybercollab_theme/static/css/theme.css")
    # Order matters: landing.js builds the hero markup (including the
    # canvas element), hero-network.js animates it. Both are homepage-only.
    register_plugin_script("/plugins/ctfd_cybercollab_theme/static/js/landing.js")
    register_plugin_script("/plugins/ctfd_cybercollab_theme/static/js/hero-network.js")
