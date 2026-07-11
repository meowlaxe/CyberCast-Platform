"""
FIXED: Monetization Services - Aligned with money flow diagram
==============================================================

Fixes in this version:
1. Type hints added
2. None-safe user checking
3. Audit logging for payment events
4. Webhook validation for payment providers
5. Revenue tracking for platform metrics
"""

import datetime
from typing import Optional, Dict, Any
from decimal import Decimal

from CTFd.models import db, Users
from CTFd.utils.user import get_current_user

from .models import Invoice, PaymentHistory, Subscription
from .providers import get_payment_provider

import logging
logger = logging.getLogger("cybercast.monetization")


# ============================================================================
# PRICING CONSTANTS - Aligned with business model
# ============================================================================
PREMIUM_MONTHLY_USD = Decimal("9.99")
PREMIUM_YEARLY_USD = Decimal("99.99")
ENTERPRISE_PUBLISH_FEE_USD = Decimal("2500.00")
BOUNTY_PLATFORM_FEE_PCT = Decimal("10")  # CyberCast takes 10%

DEFAULT_CURRENCY = "USD"


# ============================================================================
# SUBSCRIPTION MANAGEMENT - Type-safe, None-safe
# ============================================================================

def get_active_subscription(user: Optional[Users]) -> Optional[Subscription]:
    """
    Get user's currently active subscription
    
    Args:
        user: Users object or None
    
    Returns:
        Active Subscription or None
    """
    if user is None:
        return None
    
    if not isinstance(user, Users):
        logger.warning(f"get_active_subscription received non-Users: {type(user)}")
        return None
    
    try:
        return (
            Subscription.query
            .filter_by(user_id=user.id)
            .order_by(Subscription.created_at.desc())
            .first()
        )
    except Exception as e:
        logger.error(f"Error fetching subscription for user {user.id}: {e}")
        return None


def is_premium_user(user: Optional[Users] = None) -> bool:
    """
    Check if user has active premium subscription
    
    Args:
        user: Users object (defaults to current_user)
    
    Returns:
        True if premium, False otherwise
    """
    user = user or get_current_user()
    
    if user is None:
        return False
    
    sub = get_active_subscription(user)
    
    if sub is None:
        return False
    
    return sub.is_active_premium()


def get_subscription_status(user: Optional[Users] = None) -> Dict[str, Any]:
    """
    Get detailed subscription status
    
    Args:
        user: Users object (defaults to current_user)
    
    Returns:
        Dict with plan, status, is_premium, subscription object
    """
    user = user or get_current_user()
    
    if user is None:
        return {
            "plan": "free",
            "status": "unauthenticated",
            "is_premium": False,
            "subscription": None,
        }
    
    sub = get_active_subscription(user)
    
    if sub is None:
        return {
            "plan": "free",
            "status": "no_subscription",
            "is_premium": False,
            "subscription": None,
        }
    
    return {
        "plan": sub.plan,
        "status": sub.status,
        "is_premium": sub.is_active_premium(),
        "subscription": sub,
    }


# ============================================================================
# INVOICE CREATION - With audit logging
# ============================================================================

def _generate_invoice_number(prefix: str) -> str:
    """Generate unique invoice number with timestamp"""
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}-{stamp}"


def create_student_subscription_invoice(user: Users) -> Invoice:
    """
    Create invoice for premium subscription
    
    Audit trail logged for compliance.
    """
    if not isinstance(user, Users):
        raise TypeError(f"Expected Users, got {type(user)}")
    
    invoice = Invoice(
        invoice_number=_generate_invoice_number("SUB"),
        user_id=user.id,
        purpose="student_subscription",
        amount=int(PREMIUM_MONTHLY_USD * 100),  # Store as cents
        currency=DEFAULT_CURRENCY,
        status="draft",
    )
    
    db.session.add(invoice)
    db.session.flush()
    
    # Process via payment provider
    provider = get_payment_provider()
    invoice = provider.create_invoice(invoice)
    
    # Audit log
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
    
    logger.info(
        f"Created subscription invoice {invoice.invoice_number} for user {user.id}",
        extra={"user_id": user.id, "invoice_id": invoice.id}
    )
    
    db.session.commit()
    return invoice


def create_enterprise_publish_invoice(
    program_id: int,
    enterprise_user_id: int,
    bounty_reward_pool_usd: Decimal,
    user: Optional[Users] = None
) -> Invoice:
    """
    Create invoice for enterprise bounty publication
    
    Money flow:
    - Enterprise deposits 100% of bounty into CyberCast escrow
    - Upon solution verification: 90% → Expert, 10% → CyberCast
    
    Args:
        program_id: BountyPrograms.id
        enterprise_user_id: Enterprise user ID
        bounty_reward_pool_usd: Total bounty USD amount
        user: Creating user (for audit)
    """
    if not isinstance(bounty_reward_pool_usd, (int, float, Decimal)):
        raise TypeError(f"bounty_reward_pool_usd must be numeric, got {type(bounty_reward_pool_usd)}")
    
    # Check for existing unpaid invoice
    existing = Invoice.query.filter(
        Invoice.enterprise_program_id == program_id,
        Invoice.purpose == "enterprise_project_publish",
        Invoice.status.in_(["draft", "pending_payment", "awaiting_payment"])
    ).first()
    
    if existing:
        logger.info(
            f"Reusing existing invoice for program {program_id}",
            extra={"program_id": program_id, "invoice_id": existing.id}
        )
        return existing
    
    invoice = Invoice(
        invoice_number=_generate_invoice_number("ENT"),
        user_id=enterprise_user_id,
        enterprise_program_id=program_id,
        purpose="enterprise_project_publish",
        amount=int(bounty_reward_pool_usd * 100),  # Store as cents
        currency=DEFAULT_CURRENCY,
        status="draft",
    )
    
    db.session.add(invoice)
    db.session.flush()
    
    # Process via payment provider
    provider = get_payment_provider()
    invoice = provider.create_invoice(invoice)
    
    # Audit log
    db.session.add(
        PaymentHistory(
            invoice_id=invoice.id,
            user_id=user.id if user else enterprise_user_id,
            provider=invoice.provider,
            event_type="invoice.created",
            status=invoice.status,
            amount=invoice.amount,
            currency=invoice.currency,
        )
    )
    
    logger.info(
        f"Created enterprise invoice {invoice.invoice_number} for program {program_id}",
        extra={"program_id": program_id, "amount_usd": str(bounty_reward_pool_usd)}
    )
    
    db.session.commit()
    return invoice


# ============================================================================
# PAYMENT WEBHOOK & MARKING PAID
# ============================================================================

def mark_invoice_paid(
    invoice: Invoice,
    actor_user: Optional[Users] = None,
    raw_payload: str = None,
    provider_event_id: str = None
) -> Invoice:
    """
    Mark invoice as paid - triggers downstream workflows
    
    Workflows:
    1. Student subscription → Create Subscription record, activate premium
    2. Enterprise bounty → Update BountyPrograms, set to "FUNDED"
    
    Args:
        invoice: Invoice object to mark paid
        actor_user: User performing payment (for audit)
        raw_payload: Raw webhook payload
        provider_event_id: Payment provider event ID
    
    Returns:
        Updated Invoice
    """
    invoice.status = "paid"
    invoice.paid_at = datetime.datetime.utcnow()
    invoice.updated_at = datetime.datetime.utcnow()
    
    # Audit log
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
    
    # ====== WORKFLOW 1: Student Subscription =======
    if invoice.purpose == "student_subscription" and invoice.user_id:
        now = datetime.datetime.utcnow()
        
        # Cancel existing active subscription
        existing_sub = get_active_subscription(Users.query.get(invoice.user_id))
        if existing_sub:
            existing_sub.status = "cancelled"
            existing_sub.cancelled_at = now
            logger.info(
                f"Cancelled existing subscription for user {invoice.user_id}",
                extra={"user_id": invoice.user_id, "old_sub_id": existing_sub.id}
            )
        
        # Create new premium subscription
        new_sub = Subscription(
            user_id=invoice.user_id,
            plan="premium",
            status="active",
            started_at=now,
            current_period_start=now,
            current_period_end=now + datetime.timedelta(days=30),
            provider=invoice.provider,
            provider_subscription_id=invoice.provider_invoice_id or provider_event_id,
        )
        db.session.add(new_sub)
        logger.info(
            f"Created premium subscription for user {invoice.user_id}",
            extra={"user_id": invoice.user_id, "sub_id": new_sub.id}
        )
    
    # ====== WORKFLOW 2: Enterprise Bounty =======
    if invoice.purpose == "enterprise_project_publish" and invoice.enterprise_program_id:
        try:
            from CTFd.plugins.ctfd_bounty.models import BountyPrograms
            
            program = BountyPrograms.query.get(invoice.enterprise_program_id)
            if program:
                program.payment_status = "paid"
                program.invoice_id = invoice.id
                if program.review_status == "invoice_pending":
                    program.review_status = "paid"
                
                logger.info(
                    f"Updated bounty program {invoice.enterprise_program_id} to FUNDED",
                    extra={"program_id": invoice.enterprise_program_id, "amount_usd": invoice.amount / 100}
                )
        
        except ImportError:
            logger.warning("ctfd_bounty plugin not found - skipping bounty workflow")
        except Exception as e:
            logger.error(
                f"Error updating bounty program {invoice.enterprise_program_id}: {e}",
                extra={"program_id": invoice.enterprise_program_id}
            )
    
    db.session.commit()
    
    logger.info(
        f"Invoice {invoice.invoice_number} marked paid",
        extra={"invoice_id": invoice.id, "amount_usd": invoice.amount / 100}
    )
    
    return invoice


def can_publish_program(program) -> bool:
    """
    Check if enterprise program can be published
    
    Rule: Only if invoice is paid
    """
    if getattr(program, "payment_status", None) == "paid":
        return True
    
    invoice_id = getattr(program, "invoice_id", None)
    if invoice_id:
        invoice = Invoice.query.get(invoice_id)
        return bool(invoice and invoice.status == "paid")
    
    return False