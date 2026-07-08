"""
ctfd_learning_paths.routes
-----------------------------
"""

import re

from flask import Blueprint, flash, redirect, render_template, request, url_for

from CTFd.models import Challenges, Solves, db
from CTFd.utils.decorators import admins_only, authed_only
from CTFd.utils.user import get_current_user

from .models import LearningPaths, LearningPathSteps

learning_paths_bp = Blueprint(
    "learning_paths",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/plugins/platform-plus",
)


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


def _solved_challenge_ids(user):
    if user is None:
        return set()
    from CTFd.utils import get_config

    query = Solves.query
    if get_config("user_mode") == "teams" and user.team_id:
        query = query.filter(Solves.team_id == user.team_id)
    else:
        query = query.filter(Solves.user_id == user.id)
    return {row.challenge_id for row in query.all()}


@learning_paths_bp.route("/learning-paths")
def learning_paths_list():
    paths = (
        LearningPaths.query.filter_by(published=True)
        .order_by(LearningPaths.track.asc(), LearningPaths.title.asc())
        .all()
    )

    user = get_current_user()
    solved_ids = _solved_challenge_ids(user)

    progress_by_path = {}
    for path in paths:
        total = len(path.steps)
        done = sum(1 for s in path.steps if s.challenge_id in solved_ids)
        progress_by_path[path.id] = {
            "done": done,
            "total": total,
            "pct": round((done / total) * 100) if total else 0,
        }

    return render_template(
        "platform_plus/learning_paths_list.html",
        paths=paths,
        progress_by_path=progress_by_path,
    )


@learning_paths_bp.route("/learning-paths/<slug>")
def learning_path_detail(slug):
    path = LearningPaths.query.filter_by(slug=slug).first_or_404()
    user = get_current_user()
    solved_ids = _solved_challenge_ids(user)

    steps = []
    for step in path.steps:
        challenge = Challenges.query.get(step.challenge_id)
        steps.append(
            {
                "step": step,
                "challenge": challenge,
                "solved": step.challenge_id in solved_ids,
            }
        )

    total = len(steps)
    done = sum(1 for s in steps if s["solved"])
    pct = round((done / total) * 100) if total else 0

    return render_template(
        "platform_plus/learning_path_detail.html",
        path=path,
        steps=steps,
        done=done,
        total=total,
        pct=pct,
    )


@learning_paths_bp.route("/progress")
@authed_only
def progress_dashboard():
    user = get_current_user()
    solved_ids = _solved_challenge_ids(user)

    paths = (
        LearningPaths.query.filter_by(published=True)
        .order_by(LearningPaths.track.asc())
        .all()
    )

    rows = []
    total_steps_all = 0
    total_done_all = 0
    for path in paths:
        total = len(path.steps)
        done = sum(1 for s in path.steps if s.challenge_id in solved_ids)
        total_steps_all += total
        total_done_all += done
        rows.append(
            {
                "path": path,
                "done": done,
                "total": total,
                "pct": round((done / total) * 100) if total else 0,
            }
        )

    overall_pct = (
        round((total_done_all / total_steps_all) * 100) if total_steps_all else 0
    )

    return render_template(
        "platform_plus/progress_dashboard.html",
        rows=rows,
        overall_pct=overall_pct,
        total_done_all=total_done_all,
        total_steps_all=total_steps_all,
    )


# --- Admin ------------------------------------------------------------------


@learning_paths_bp.route("/admin/learning-paths")
@admins_only
def admin_learning_paths():
    paths = LearningPaths.query.order_by(LearningPaths.created_at.desc()).all()
    return render_template("platform_plus/admin_learning_paths.html", paths=paths)


@learning_paths_bp.route("/admin/learning-paths/new", methods=["GET", "POST"])
@admins_only
def admin_learning_path_new():
    if request.method == "GET":
        return render_template("platform_plus/admin_learning_path_new.html")

    user = get_current_user()
    title = request.form.get("title", "").strip()
    slug = slugify(title)

    path = LearningPaths(
        title=title,
        slug=slug,
        track=request.form.get("track", "general"),
        description=request.form.get("description", "").strip(),
        difficulty=request.form.get("difficulty", "beginner"),
        published=bool(request.form.get("published")),
        created_by=user.id,
    )
    db.session.add(path)
    db.session.commit()
    flash("Learning path created. Now add its steps.", "success")
    return redirect(url_for("learning_paths.admin_learning_path_edit", path_id=path.id))


@learning_paths_bp.route("/admin/learning-paths/<int:path_id>/edit")
@admins_only
def admin_learning_path_edit(path_id):
    path = LearningPaths.query.get_or_404(path_id)
    all_challenges = Challenges.query.order_by(
        Challenges.category, Challenges.name
    ).all()
    used_ids = {s.challenge_id for s in path.steps}
    available = [c for c in all_challenges if c.id not in used_ids]
    return render_template(
        "platform_plus/admin_learning_path_edit.html",
        path=path,
        available=available,
    )


@learning_paths_bp.route(
    "/admin/learning-paths/<int:path_id>/add-step", methods=["POST"]
)
@admins_only
def admin_learning_path_add_step(path_id):
    path = LearningPaths.query.get_or_404(path_id)
    challenge_id = int(request.form.get("challenge_id"))
    next_position = len(path.steps)

    step = LearningPathSteps(
        path_id=path.id,
        challenge_id=challenge_id,
        position=next_position,
        note=request.form.get("note", "").strip(),
    )
    db.session.add(step)
    db.session.commit()
    flash("Step added.", "success")
    return redirect(url_for("learning_paths.admin_learning_path_edit", path_id=path.id))


@learning_paths_bp.route(
    "/admin/learning-paths/steps/<int:step_id>/remove", methods=["POST"]
)
@admins_only
def admin_learning_path_remove_step(step_id):
    step = LearningPathSteps.query.get_or_404(step_id)
    path_id = step.path_id
    db.session.delete(step)
    db.session.commit()
    return redirect(url_for("learning_paths.admin_learning_path_edit", path_id=path_id))
