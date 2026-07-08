"""
ctfd_learning_paths.models
-----------------------------
Structured curriculum (multiple tracks) built on top of CTFd's own
Challenges table. Progress is NOT stored here - it's computed live by
joining against CTFd's own Solves table (see routes.py).
"""

import datetime

from CTFd.models import db


class LearningPaths(db.Model):
    __tablename__ = "lp_paths"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    slug = db.Column(db.String(128), nullable=False, unique=True)
    track = db.Column(db.String(64), default="general")
    description = db.Column(db.Text)
    difficulty = db.Column(db.String(16), default="beginner")
    published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    steps = db.relationship(
        "LearningPathSteps",
        backref="path",
        cascade="all, delete-orphan",
        order_by="LearningPathSteps.position",
    )

    def __repr__(self):
        return f"<LearningPath {self.title} ({self.track})>"


class LearningPathSteps(db.Model):
    __tablename__ = "lp_steps"

    id = db.Column(db.Integer, primary_key=True)
    path_id = db.Column(db.Integer, db.ForeignKey("lp_paths.id", ondelete="CASCADE"))
    challenge_id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE")
    )
    position = db.Column(db.Integer, nullable=False, default=0)
    note = db.Column(db.String(256))

    __table_args__ = (
        db.UniqueConstraint("path_id", "challenge_id", name="uq_path_challenge"),
    )
