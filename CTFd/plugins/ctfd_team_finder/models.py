"""
ctfd_team_finder.models
--------------------------
Lightweight "looking for teammates" board.
"""

import datetime

from CTFd.models import db


class TeamFinderPosts(db.Model):
    __tablename__ = "tf_posts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"))
    title = db.Column(db.String(128), nullable=False)
    looking_for = db.Column(db.String(256))
    skills = db.Column(db.String(256))
    message = db.Column(db.Text)
    contact = db.Column(db.String(256))
    status = db.Column(db.String(16), default="open")  # open|closed
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    interests = db.relationship(
        "TeamFinderInterests", backref="post", cascade="all, delete-orphan"
    )


class TeamFinderInterests(db.Model):
    __tablename__ = "tf_interests"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("tf_posts.id", ondelete="CASCADE"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"))
    note = db.Column(db.String(512))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("post_id", "user_id", name="uq_post_user_interest"),
    )
