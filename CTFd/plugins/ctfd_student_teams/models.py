"""
ctfd_student_teams.models
-------------------------
CyberCast Student Teams domain models.
"""

import datetime

from CTFd.models import db


class StudentTeam(db.Model):
    __tablename__ = "st_teams"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    name = db.Column(db.String(128), nullable=False, unique=True)
    slug = db.Column(db.String(128), nullable=False, unique=True)
    description = db.Column(db.Text)
    avatar = db.Column(db.String(256))
    banner = db.Column(db.String(256))
    visibility = db.Column(db.String(32), nullable=False, default="public")
    invite_code = db.Column(db.String(64), unique=True)
    status = db.Column(db.String(32), nullable=False, default="active")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    members = db.relationship(
        "StudentTeamMember", backref="team", cascade="all, delete-orphan"
    )
    invites = db.relationship(
        "StudentTeamInvite", backref="team", cascade="all, delete-orphan"
    )
    join_requests = db.relationship(
        "StudentTeamJoinRequest", backref="team", cascade="all, delete-orphan"
    )
    score_events = db.relationship(
        "StudentTeamScoreEvent", backref="team", cascade="all, delete-orphan"
    )
    score_cache = db.relationship(
        "StudentTeamScoreCache",
        backref="team",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def __repr__(self):
        return f"<StudentTeam {self.name}>"


class StudentTeamMember(db.Model):
    __tablename__ = "st_team_members"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("st_teams.id", ondelete="CASCADE"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"))
    role = db.Column(db.String(32), nullable=False, default="member")
    joined_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    left_at = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint("team_id", "user_id", name="uq_st_team_user"),
    )


class StudentTeamInvite(db.Model):
    __tablename__ = "st_team_invites"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("st_teams.id", ondelete="CASCADE"))
    invited_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE")
    )
    invited_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    status = db.Column(db.String(32), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint(
            "team_id", "invited_user_id", "status", name="uq_st_active_invite"
        ),
    )


class StudentTeamJoinRequest(db.Model):
    __tablename__ = "st_team_join_requests"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("st_teams.id", ondelete="CASCADE"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"))
    message = db.Column(db.String(512))
    status = db.Column(db.String(32), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        db.UniqueConstraint(
            "team_id", "user_id", "status", name="uq_st_active_join_request"
        ),
    )


class StudentTeamScoreEvent(db.Model):
    __tablename__ = "st_team_score_events"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("st_teams.id", ondelete="CASCADE"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"))
    solve_id = db.Column(db.Integer, db.ForeignKey("solves.id", ondelete="CASCADE"))
    challenge_id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE")
    )
    category = db.Column(db.String(64))
    points = db.Column(db.Integer, nullable=False, default=0)
    solve_date = db.Column(db.DateTime, nullable=False)
    member_joined_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("solve_id", name="uq_st_score_event_solve"),
        db.Index("ix_st_score_team_date", "team_id", "solve_date"),
        db.Index("ix_st_score_user_date", "user_id", "solve_date"),
    )


class StudentTeamScoreCache(db.Model):
    __tablename__ = "st_team_score_cache"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(
        db.Integer, db.ForeignKey("st_teams.id", ondelete="CASCADE"), unique=True
    )
    total_score = db.Column(db.Integer, nullable=False, default=0)
    solve_count = db.Column(db.Integer, nullable=False, default=0)
    last_score_event_id = db.Column(
        db.Integer, db.ForeignKey("st_team_score_events.id", ondelete="SET NULL")
    )
    updated_at = db.Column(
        db.DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )
