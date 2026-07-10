from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from CTFd.models import db
from CTFd.utils.decorators import admins_only, authed_only
from CTFd.utils.user import get_current_user

from .models import Invoice, PaymentHistory, Subscription
from .services import (
    create_student_subscription_invoice,
    get_subscription_status,
    mark_invoice_paid,
)

monetization_bp = Blueprint(
    "monetization",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/plugins/platform-plus",
)


@monetization_bp.route("/pricing")
def pricing():
    return render_template(
        "monetization/pricing.html",
        subscription_status=get_subscription_status(),
    )


@monetization_bp.route("/subscription")
@authed_only
def subscription():
    user = get_current_user()
    invoices = (
        Invoice.query.filter_by(user_id=user.id)
        .order_by(Invoice.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "monetization/subscription.html",
        subscription_status=get_subscription_status(user),
        invoices=invoices,
    )


@monetization_bp.route("/subscription/upgrade", methods=["POST"])
@authed_only
def subscription_upgrade():
    user = get_current_user()
    invoice = create_student_subscription_invoice(user)
    flash("Premium invoice generated. Complete payment to activate Premium.", "info")
    return redirect(url_for("monetization.invoice_payment", invoice_id=invoice.id))


@monetization_bp.route("/billing")
@authed_only
def billing_history():
    user = get_current_user()
    invoices = (
        Invoice.query.filter_by(user_id=user.id)
        .order_by(Invoice.created_at.desc())
        .all()
    )
    return render_template("monetization/billing_history.html", invoices=invoices)


@monetization_bp.route("/payments/invoices/<int:invoice_id>")
@authed_only
def invoice_detail(invoice_id):
    user = get_current_user()
    invoice = Invoice.query.get_or_404(invoice_id)
    if invoice.user_id not in (None, user.id):
        abort(403)
    return render_template("monetization/invoice_detail.html", invoice=invoice)


@monetization_bp.route("/payments/invoices/<int:invoice_id>/pay")
@authed_only
def invoice_payment(invoice_id):
    user = get_current_user()
    invoice = Invoice.query.get_or_404(invoice_id)
    if invoice.user_id not in (None, user.id):
        abort(403)
    return render_template("monetization/payment.html", invoice=invoice)


@monetization_bp.route("/payments/invoices/<int:invoice_id>/status")
@authed_only
def payment_status(invoice_id):
    user = get_current_user()
    invoice = Invoice.query.get_or_404(invoice_id)
    if invoice.user_id not in (None, user.id):
        abort(403)
    return render_template("monetization/payment_status.html", invoice=invoice)


@monetization_bp.route("/admin/monetization")
@admins_only
def admin_dashboard():
    total_invoices = Invoice.query.count()
    paid_invoices = Invoice.query.filter_by(status="paid").count()
    pending_invoices = Invoice.query.filter_by(status="pending_payment").count()
    premium_users = Subscription.query.filter_by(plan="premium", status="active").count()
    recent_invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(10).all()
    return render_template(
        "monetization/admin_dashboard.html",
        total_invoices=total_invoices,
        paid_invoices=paid_invoices,
        pending_invoices=pending_invoices,
        premium_users=premium_users,
        recent_invoices=recent_invoices,
    )


@monetization_bp.route("/admin/monetization/subscriptions")
@admins_only
def admin_subscriptions():
    subscriptions = Subscription.query.order_by(Subscription.created_at.desc()).all()
    return render_template(
        "monetization/admin_subscriptions.html", subscriptions=subscriptions
    )


@monetization_bp.route("/admin/monetization/invoices")
@admins_only
def admin_invoices():
    invoices = Invoice.query.order_by(Invoice.created_at.desc()).all()
    return render_template("monetization/admin_invoices.html", invoices=invoices)


@monetization_bp.route("/admin/monetization/invoices/<int:invoice_id>/mark-paid", methods=["POST"])
@admins_only
def admin_invoice_mark_paid(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    mark_invoice_paid(invoice, actor_user=get_current_user(), raw_payload="manual admin mark-paid")
    flash("Invoice marked as paid.", "success")
    return redirect(request.referrer or url_for("monetization.admin_invoices"))


@monetization_bp.route("/admin/monetization/payments")
@admins_only
def admin_payments():
    payments = PaymentHistory.query.order_by(PaymentHistory.created_at.desc()).all()
    return render_template("monetization/admin_payments.html", payments=payments)
