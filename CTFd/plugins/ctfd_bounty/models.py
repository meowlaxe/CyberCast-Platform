"""
ctfd_bounty.models
--------------------
Enterprise bug bounty board.
"""

import datetime

from CTFd.models import db


class BountyPrograms(db.Model):
    __tablename__ = "bnt_programs"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    company_name = db.Column(db.String(128), nullable=False)
    company_logo_url = db.Column(db.String(256))
    scope = db.Column(db.Text)
    description = db.Column(db.Text)
    reward_min = db.Column(db.Integer, default=0)
    reward_max = db.Column(db.Integer, default=0)
    currency = db.Column(db.String(8), default="USD")
    status = db.Column(db.String(16), default="draft")  # draft|active|paused|closed
    review_status = db.Column(db.String(32), default="draft")
    payment_status = db.Column(db.String(32), default="invoice_required")
    invoice_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    submissions = db.relationship(
        "BountySubmissions", backref="program", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<BountyProgram {self.title} - {self.company_name}>"


class BountySubmissions(db.Model):
    __tablename__ = "bnt_submissions"

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(
        db.Integer, db.ForeignKey("bnt_programs.id", ondelete="CASCADE")
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(16), default="medium")  # low|medium|high|critical
    status = db.Column(
        db.String(16), default="pending"
    )  # pending|triaging|accepted|duplicate|rejected|paid
    reward_amount = db.Column(db.Integer, default=0)
    admin_notes = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    def __repr__(self):
        return f"<BountySubmission {self.title} [{self.status}]>"
