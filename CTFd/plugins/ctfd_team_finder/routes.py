"""
ctfd_team_finder.routes
--------------------------
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from CTFd.models import db
from CTFd.utils.decorators import authed_only
from CTFd.utils.user import get_current_user

from .models import TeamFinderInterests, TeamFinderPosts

team_finder_bp = Blueprint(
    "team_finder",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/plugins/platform-plus",
)


@team_finder_bp.route("/team-finder")
def team_finder_list():
    posts = (
        TeamFinderPosts.query.filter_by(status="open")
        .order_by(TeamFinderPosts.created_at.desc())
        .all()
    )
    return render_template("platform_plus/team_finder_list.html", posts=posts)


@team_finder_bp.route("/team-finder/new", methods=["GET", "POST"])
@authed_only
def team_finder_new():
    if request.method == "GET":
        return render_template("platform_plus/team_finder_new.html")

    user = get_current_user()
    post = TeamFinderPosts(
        user_id=user.id,
        title=request.form.get("title", "").strip(),
        looking_for=request.form.get("looking_for", "").strip(),
        skills=request.form.get("skills", "").strip(),
        message=request.form.get("message", "").strip(),
        contact=request.form.get("contact", "").strip(),
    )
    db.session.add(post)
    db.session.commit()
    flash("Your team post is now live.", "success")
    return redirect(url_for("team_finder.team_finder_list"))


@team_finder_bp.route("/team-finder/<int:post_id>/interested", methods=["POST"])
@authed_only
def team_finder_interested(post_id):
    post = TeamFinderPosts.query.get_or_404(post_id)
    user = get_current_user()

    if post.user_id == user.id:
        flash("This is your own post.", "info")
        return redirect(url_for("team_finder.team_finder_list"))

    existing = TeamFinderInterests.query.filter_by(
        post_id=post.id, user_id=user.id
    ).first()
    if not existing:
        interest = TeamFinderInterests(
            post_id=post.id, user_id=user.id, note=request.form.get("note", "")
        )
        db.session.add(interest)
        db.session.commit()

    flash("Your interest has been sent to the post author.", "success")
    return redirect(url_for("team_finder.team_finder_list"))


@team_finder_bp.route("/team-finder/<int:post_id>/close", methods=["POST"])
@authed_only
def team_finder_close(post_id):
    post = TeamFinderPosts.query.get_or_404(post_id)
    user = get_current_user()
    if post.user_id != user.id:
        abort(403)
    post.status = "closed"
    db.session.commit()
    return redirect(url_for("team_finder.team_finder_list"))
