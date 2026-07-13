"""Authenticated API routes for CyberCast rooms and leaderboard data."""

import secrets

from flask import Blueprint, abort, jsonify, request
from sqlalchemy import case, func

from CTFd.models import Challenges, Submissions, Users, db
from CTFd.models import Solves
from CTFd.utils.decorators import admins_only, authed_only
from CTFd.utils.user import get_current_user, is_admin

from .models import (
    CyberCastRoomMember,
    CyberCastRoomSubmission,
    CyberCastUserProfile,
    CyberCastWorkingRoom,
)

cybercast_bp = Blueprint("cybercast", __name__, url_prefix="/api/v1/cybercast")

VALID_ROLES = {"student", "expert", "admin"}


def request_json():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400, description="A JSON object is required.")
    return payload


def get_or_create_profile(user_id):
    profile = CyberCastUserProfile.query.get(user_id)
    if profile is None:
        profile = CyberCastUserProfile(user_id=user_id, role="student")
        db.session.add(profile)
        db.session.flush()
    return profile


def can_manage_rooms(user):
    profile = get_or_create_profile(user.id)
    return is_admin() or profile.role in {"expert", "admin"}


def room_for_token(room_token):
    return CyberCastWorkingRoom.query.filter_by(room_token=room_token).first_or_404()


def is_room_member(room_id, user_id):
    return (
        CyberCastRoomMember.query.filter_by(room_id=room_id, user_id=user_id).first()
        is not None
    )


def can_access_room(room, user):
    return is_admin() or room.expert_user_id == user.id or is_room_member(room.id, user.id)


def room_payload(room):
    challenge = Challenges.query.get(room.challenge_id)
    expert = Users.query.get(room.expert_user_id)
    return {
        "id": room.id,
        "room_token": room.room_token,
        "status": room.status,
        "created_at": room.created_at.isoformat() if room.created_at else None,
        "completed_at": room.completed_at.isoformat() if room.completed_at else None,
        "challenge": {
            "id": challenge.id,
            "name": challenge.name,
            "description": challenge.description,
            "value": challenge.value,
        },
        "expert": {"id": expert.id, "name": expert.name},
    }


@cybercast_bp.route("/rooms", methods=["POST"])
@authed_only
def create_room():
    user = get_current_user()
    if not can_manage_rooms(user):
        abort(403, description="Only experts and CTFd admins can create rooms.")

    payload = request_json()
    challenge_id = payload.get("challenge_id")
    if not isinstance(challenge_id, int):
        abort(400, description="challenge_id must be an integer.")
    if Challenges.query.get(challenge_id) is None:
        abort(404, description="Challenge not found.")

    room_token = payload.get("room_token") or secrets.token_urlsafe(18)
    if not isinstance(room_token, str) or not room_token.strip() or len(room_token) > 100:
        abort(400, description="room_token must be a non-empty string up to 100 characters.")
    if CyberCastWorkingRoom.query.filter_by(room_token=room_token).first():
        abort(409, description="room_token is already in use.")

    room = CyberCastWorkingRoom(
        room_token=room_token,
        expert_user_id=user.id,
        challenge_id=challenge_id,
    )
    db.session.add(room)
    db.session.commit()
    return jsonify(room_payload(room)), 201


@cybercast_bp.route("/rooms/<string:room_token>", methods=["GET"])
@authed_only
def get_room(room_token):
    room = room_for_token(room_token)
    user = get_current_user()
    if not can_access_room(room, user):
        abort(403)
    payload = room_payload(room)
    payload["member_count"] = CyberCastRoomMember.query.filter_by(room_id=room.id).count()
    return jsonify(payload)


@cybercast_bp.route("/rooms/<string:room_token>/join", methods=["POST"])
@authed_only
def join_room(room_token):
    room = room_for_token(room_token)
    user = get_current_user()
    profile = get_or_create_profile(user.id)
    if profile.role != "student" and not is_admin():
        abort(403, description="Only students can join a working room.")
    if room.status != "active":
        abort(409, description="This room is not active.")

    membership = CyberCastRoomMember.query.filter_by(room_id=room.id, user_id=user.id).first()
    if membership is None:
        membership = CyberCastRoomMember(room_id=room.id, user_id=user.id)
        db.session.add(membership)
        db.session.commit()
    return jsonify({"room_token": room.room_token, "joined": True}), 200


@cybercast_bp.route("/rooms/<string:room_token>/submissions", methods=["POST"])
@authed_only
def attach_submission(room_token):
    room = room_for_token(room_token)
    user = get_current_user()
    if not is_room_member(room.id, user.id):
        abort(403, description="Join the room before attaching a submission.")

    payload = request_json()
    submission_id = payload.get("submission_id")
    if not isinstance(submission_id, int):
        abort(400, description="submission_id must be an integer.")

    submission = Submissions.query.filter_by(
        id=submission_id, user_id=user.id, challenge_id=room.challenge_id
    ).first()
    if submission is None:
        abort(404, description="No matching submission was found.")

    linked_submission = CyberCastRoomSubmission.query.get(submission_id)
    if linked_submission and linked_submission.room_id != room.id:
        abort(409, description="This submission is already linked to another room.")
    if linked_submission is None:
        db.session.add(CyberCastRoomSubmission(submission_id=submission_id, room_id=room.id))
        db.session.commit()

    return jsonify({"submission_id": submission_id, "room_token": room.room_token}), 201


@cybercast_bp.route("/rooms/<string:room_token>/progress", methods=["GET"])
@authed_only
def room_progress(room_token):
    room = room_for_token(room_token)
    user = get_current_user()
    if not can_access_room(room, user):
        abort(403)

    correct_count = func.coalesce(
        func.sum(case((Submissions.type == "correct", 1), else_=0)), 0
    ).label("correct_solves")
    incorrect_count = func.coalesce(
        func.sum(case((Submissions.type == "incorrect", 1), else_=0)), 0
    ).label("incorrect_attempts")
    rows = (
        db.session.query(
            Users.id.label("user_id"),
            Users.name.label("username"),
            correct_count,
            incorrect_count,
        )
        .join(CyberCastRoomMember, CyberCastRoomMember.user_id == Users.id)
        .outerjoin(
            CyberCastRoomSubmission,
            CyberCastRoomSubmission.room_id == CyberCastRoomMember.room_id,
        )
        .outerjoin(
            Submissions,
            (Submissions.id == CyberCastRoomSubmission.submission_id)
            & (Submissions.user_id == Users.id),
        )
        .filter(CyberCastRoomMember.room_id == room.id)
        .group_by(Users.id, Users.name)
        .order_by(correct_count.desc(), incorrect_count.asc(), Users.name.asc())
        .all()
    )
    return jsonify(
        {
            "room_token": room.room_token,
            "progress": [
                {
                    "user_id": row.user_id,
                    "username": row.username,
                    "correct_solves": int(row.correct_solves),
                    "incorrect_attempts": int(row.incorrect_attempts),
                }
                for row in rows
            ],
        }
    )


@cybercast_bp.route("/leaderboard", methods=["GET"])
@authed_only
def leaderboard():
    score = func.coalesce(func.sum(Challenges.value), 0).label("score")
    solved_count = func.count(Solves.id).label("solved_count")
    rows = (
        db.session.query(
            Users.id.label("user_id"), Users.name.label("username"), score, solved_count
        )
        .join(CyberCastUserProfile, CyberCastUserProfile.user_id == Users.id)
        .outerjoin(Solves, Solves.user_id == Users.id)
        .outerjoin(Challenges, Challenges.id == Solves.challenge_id)
        .filter(CyberCastUserProfile.role == "student")
        .group_by(Users.id, Users.name)
        .order_by(score.desc(), solved_count.desc(), Users.name.asc())
        .all()
    )
    return jsonify(
        {
            "leaderboard": [
                {
                    "rank": position,
                    "user_id": row.user_id,
                    "username": row.username,
                    "score": int(row.score),
                    "solved_count": int(row.solved_count),
                }
                for position, row in enumerate(rows, start=1)
            ]
        }
    )


@cybercast_bp.route("/users/<int:user_id>/role", methods=["PATCH"])
@admins_only
def update_user_role(user_id):
    if Users.query.get(user_id) is None:
        abort(404, description="User not found.")
    payload = request_json()
    role = payload.get("role")
    if role not in VALID_ROLES:
        abort(400, description="role must be student, expert, or admin.")

    profile = get_or_create_profile(user_id)
    profile.role = role
    db.session.commit()
    return jsonify({"user_id": user_id, "role": role})
