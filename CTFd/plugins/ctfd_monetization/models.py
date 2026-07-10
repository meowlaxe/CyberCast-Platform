import datetime

from CTFd.models import db


class Subscription(db.Model):
    __tablename__ = "mon_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"))
    plan = db.Column(db.String(32), nullable=False, default="free")
    status = db.Column(db.String(32), nullable=False, default="active")
    started_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    current_period_start = db.Column(db.DateTime)
    current_period_end = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    provider = db.Column(db.String(64), nullable=False, default="manual")
    provider_subscription_id = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    def is_active_premium(self):
        if self.plan != "premium":
            return False
        if self.status not in ("active", "trialing"):
            return False
        if self.current_period_end and self.current_period_end < datetime.datetime.utcnow():
            return False
        return True


class Invoice(db.Model):
    __tablename__ = "mon_invoices"

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(64), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    enterprise_program_id = db.Column(
        db.Integer, db.ForeignKey("bnt_programs.id", ondelete="SET NULL")
    )
    purpose = db.Column(db.String(64), nullable=False)
    amount = db.Column(db.Integer, nullable=False, default=0)
    currency = db.Column(db.String(8), nullable=False, default="IDR")
    status = db.Column(db.String(32), nullable=False, default="draft")
    provider = db.Column(db.String(64), nullable=False, default="manual")
    provider_invoice_id = db.Column(db.String(128))
    payment_url = db.Column(db.String(512))
    metadata_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
    paid_at = db.Column(db.DateTime)

    histories = db.relationship(
        "PaymentHistory", backref="invoice", cascade="all, delete-orphan"
    )

    @property
    def is_paid(self):
        return self.status == "paid"


class PaymentHistory(db.Model):
    __tablename__ = "mon_payment_history"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(
        db.Integer, db.ForeignKey("mon_invoices.id", ondelete="CASCADE")
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    provider = db.Column(db.String(64), nullable=False, default="manual")
    event_type = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(32), nullable=False)
    amount = db.Column(db.Integer, nullable=False, default=0)
    currency = db.Column(db.String(8), nullable=False, default="IDR")
    raw_payload = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
