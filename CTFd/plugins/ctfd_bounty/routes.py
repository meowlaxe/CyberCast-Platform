"""
ctfd_bounty.routes
--------------------
"""

import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from CTFd.models import db
from CTFd.utils.decorators import admins_only, authed_only
from CTFd.utils.user import get_current_user

from .models import BountyPrograms, BountySubmissions

bounty_bp = Blueprint(
    "bounty",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/plugins/platform-plus",
)


@bounty_bp.route("/bounty")
def bounty_list():
    programs = (
        BountyPrograms.query.filter_by(status="active")
        .order_by(BountyPrograms.created_at.desc())
        .all()
    )
    return render_template("platform_plus/bounty_list.html", programs=programs)


@bounty_bp.route("/bounty/<int:program_id>")
def bounty_detail(program_id):
    program = BountyPrograms.query.get_or_404(program_id)
    return render_template("platform_plus/bounty_detail.html", program=program)


@bounty_bp.route("/bounty/<int:program_id>/submit", methods=["GET", "POST"])
@authed_only
def bounty_submit(program_id):
    program = BountyPrograms.query.get_or_404(program_id)
    if program.status != "active":
        abort(403, description="This program is not currently accepting reports.")

    if request.method == "GET":
        return render_template("platform_plus/bounty_submit.html", program=program)

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    severity = request.form.get("severity", "medium")

    if not title or not description:
        flash("Report title and description are required.", "error")
        return redirect(url_for("bounty.bounty_submit", program_id=program_id))

    user = get_current_user()
    submission = BountySubmissions(
        program_id=program.id,
        user_id=user.id,
        title=title,
        description=description,
        severity=severity,
    )
    db.session.add(submission)
    db.session.commit()

    flash("Report submitted. Our team will review your submission.", "success")
    return redirect(url_for("bounty.bounty_my_submissions"))


@bounty_bp.route("/bounty/my-submissions")
@authed_only
def bounty_my_submissions():
    user = get_current_user()
    submissions = (
        BountySubmissions.query.filter_by(user_id=user.id)
        .order_by(BountySubmissions.submitted_at.desc())
        .all()
    )
    return render_template(
        "platform_plus/bounty_my_submissions.html", submissions=submissions
    )


@bounty_bp.route("/admin/bounty")
@admins_only
def admin_bounty_dashboard():
    programs = BountyPrograms.query.order_by(BountyPrograms.created_at.desc()).all()
    return render_template(
        "platform_plus/admin_bounty_dashboard.html", programs=programs
    )


@bounty_bp.route("/admin/bounty/new", methods=["GET", "POST"])
@admins_only
def admin_bounty_new():
    if request.method == "GET":
        return render_template("platform_plus/admin_bounty_new.html")

    user = get_current_user()
    program = BountyPrograms(
        title=request.form.get("title", "").strip(),
        company_name=request.form.get("company_name", "").strip(),
        description=request.form.get("description", "").strip(),
        scope=request.form.get("scope", "").strip(),
        reward_min=int(request.form.get("reward_min") or 0),
        reward_max=int(request.form.get("reward_max") or 0),
        status=request.form.get("status", "draft"),
        created_by=user.id,
    )
    db.session.add(program)
    db.session.commit()
    flash("Bounty program created.", "success")
    return redirect(url_for("bounty.admin_bounty_dashboard"))


@bounty_bp.route(
    "/admin/bounty/submissions/<int:submission_id>/update", methods=["POST"]
)
@admins_only
def admin_bounty_update_submission(submission_id):
    submission = BountySubmissions.query.get_or_404(submission_id)
    submission.status = request.form.get("status", submission.status)
    submission.reward_amount = int(
        request.form.get("reward_amount") or submission.reward_amount
    )
    submission.admin_notes = request.form.get("admin_notes", submission.admin_notes)
    submission.updated_at = datetime.datetime.utcnow()
    db.session.commit()
    flash("Submission updated.", "success")
    return redirect(url_for("bounty.admin_bounty_dashboard"))
