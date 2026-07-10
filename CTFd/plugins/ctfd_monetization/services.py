import datetime

from CTFd.models import db
from CTFd.utils.user import get_current_user

from .models import Invoice, PaymentHistory, Subscription
from .providers import get_payment_provider


PREMIUM_MONTHLY_AMOUNT = 99000
ENTERPRISE_PUBLISH_AMOUNT = 2500000
DEFAULT_CURRENCY = "IDR"


def _invoice_number(prefix):
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}-{stamp}"


def get_active_subscription(user):
    if user is None:
        return None
    return (
        Subscription.query.filter_by(user_id=user.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )


def is_premium_user(user=None):
    user = user or get_current_user()
    sub = get_active_subscription(user)
    return bool(sub and sub.is_active_premium())


def get_subscription_status(user=None):
    user = user or get_current_user()
    sub = get_active_subscription(user)
    if sub is None:
        return {
            "plan": "free",
            "status": "active",
            "subscription": None,
            "is_premium": False,
        }
    return {
        "plan": sub.plan,
        "status": sub.status,
        "subscription": sub,
        "is_premium": sub.is_active_premium(),
    }


def create_student_subscription_invoice(user):
    invoice = Invoice(
        invoice_number=_invoice_number("SUB"),
        user_id=user.id,
        purpose="student_subscription",
        amount=PREMIUM_MONTHLY_AMOUNT,
        currency=DEFAULT_CURRENCY,
        status="draft",
    )
    db.session.add(invoice)
    db.session.flush()
    get_payment_provider().create_invoice(invoice)
    invoice.payment_url = f"/plugins/platform-plus/payments/invoices/{invoice.id}/pay"
    db.session.add(
        PaymentHistory(
            invoice_id=invoice.id,
            user_id=user.id,
            provider=invoice.provider,
            event_type="invoice.created",
            status=invoice.status,
            amount=invoice.amount,
            currency=invoice.currency,
        )
    )
    db.session.commit()
    return invoice


def create_enterprise_publish_invoice(program, user=None):
    existing = Invoice.query.filter_by(
        enterprise_program_id=program.id,
        purpose="enterprise_project_publish",
    ).order_by(Invoice.created_at.desc()).first()
    if existing and existing.status not in ("cancelled", "expired", "failed"):
        return existing

    invoice = Invoice(
        invoice_number=_invoice_number("ENT"),
        user_id=user.id if user else None,
        enterprise_program_id=program.id,
        purpose="enterprise_project_publish",
        amount=ENTERPRISE_PUBLISH_AMOUNT,
        currency=DEFAULT_CURRENCY,
        status="draft",
    )
    db.session.add(invoice)
    db.session.flush()
    get_payment_provider().create_invoice(invoice)
    invoice.payment_url = f"/plugins/platform-plus/payments/invoices/{invoice.id}/pay"
    db.session.add(
        PaymentHistory(
            invoice_id=invoice.id,
            user_id=invoice.user_id,
            provider=invoice.provider,
            event_type="invoice.created",
            status=invoice.status,
            amount=invoice.amount,
            currency=invoice.currency,
        )
    )
    db.session.commit()
    return invoice


def mark_invoice_paid(invoice, actor_user=None, raw_payload=None):
    invoice.status = "paid"
    invoice.paid_at = datetime.datetime.utcnow()
    invoice.updated_at = datetime.datetime.utcnow()
    db.session.add(
        PaymentHistory(
            invoice_id=invoice.id,
            user_id=actor_user.id if actor_user else invoice.user_id,
            provider=invoice.provider,
            event_type="invoice.paid",
            status=invoice.status,
            amount=invoice.amount,
            currency=invoice.currency,
            raw_payload=raw_payload,
        )
    )

    if invoice.purpose == "student_subscription" and invoice.user_id:
        now = datetime.datetime.utcnow()
        current = get_active_subscription(type("UserRef", (), {"id": invoice.user_id})())
        if current:
            current.status = "cancelled"
            current.cancelled_at = now
        db.session.add(
            Subscription(
                user_id=invoice.user_id,
                plan="premium",
                status="active",
                started_at=now,
                current_period_start=now,
                current_period_end=now + datetime.timedelta(days=30),
                provider=invoice.provider,
                provider_subscription_id=invoice.provider_invoice_id,
            )
        )

    if invoice.purpose == "enterprise_project_publish" and invoice.enterprise_program_id:
        try:
            from CTFd.plugins.ctfd_bounty.models import BountyPrograms

            program = BountyPrograms.query.get(invoice.enterprise_program_id)
            if program:
                program.payment_status = "paid"
                program.invoice_id = invoice.id
                if program.review_status == "invoice_pending":
                    program.review_status = "paid"
        except Exception:
            # Keep payment state authoritative even if the optional bounty plugin is unavailable.
            pass

    db.session.commit()
    return invoice


def can_publish_program(program):
    if getattr(program, "payment_status", None) == "paid":
        return True
    invoice_id = getattr(program, "invoice_id", None)
    if invoice_id:
        invoice = Invoice.query.get(invoice_id)
        return bool(invoice and invoice.status == "paid")
    return False
