"""Database models for the CyberCast CTFd extension."""

import datetime

from CTFd.models import db


class CyberCastUserProfile(db.Model):
    __tablename__ = "cybercast_user_profiles"

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role = db.Column(db.String(16), nullable=False, default="student")
    rating_points = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint(
            "role IN ('student', 'expert', 'admin')",
            name="ck_cybercast_user_profile_role",
        ),
        db.CheckConstraint(
            "rating_points >= 0", name="ck_cybercast_user_profile_rating"
        ),
    )


class CyberCastChallengeProfile(db.Model):
    __tablename__ = "cybercast_challenge_profiles"

    challenge_id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    difficulty_tier = db.Column(db.String(32), nullable=False)
    owner_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint(
            "difficulty_tier IN ('sandbox_practice', 'enterprise_arena')",
            name="ck_cybercast_challenge_profile_tier",
        ),
    )


class CyberCastWorkingRoom(db.Model):
    __tablename__ = "cybercast_working_rooms"

    id = db.Column(db.Integer, primary_key=True)
    room_token = db.Column(db.String(100), nullable=False, unique=True)
    expert_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    challenge_id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False
    )
    status = db.Column(db.String(16), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.datetime.utcnow)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    members = db.relationship(
        "CyberCastRoomMember",
        backref="room",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('active', 'completed')", name="ck_cybercast_room_status"
        ),
        db.Index("ix_cybercast_rooms_challenge", "challenge_id"),
    )


class CyberCastRoomMember(db.Model):
    __tablename__ = "cybercast_room_members"

    room_id = db.Column(
        db.Integer,
        db.ForeignKey("cybercast_working_rooms.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    joined_at = db.Column(db.DateTime(timezone=True), default=datetime.datetime.utcnow)

    __table_args__ = (db.Index("ix_cybercast_room_members_user", "user_id"),)


class CyberCastRoomSubmission(db.Model):
    __tablename__ = "cybercast_room_submissions"

    submission_id = db.Column(
        db.Integer,
        db.ForeignKey("submissions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    room_id = db.Column(
        db.Integer,
        db.ForeignKey("cybercast_working_rooms.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (db.Index("ix_cybercast_room_submissions_room", "room_id"),)
