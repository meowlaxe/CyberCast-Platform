# =============================================================================
# File: CTFd/plugins/ctfd_bounty_collab/models.py
# Plugin: ctfd_bounty_collab
# Created: 2026-07-15  Author: Claude / CyberCast implementation
# Modified: 2026-07-15  — Added CollabUserProfile for 3-role system
#           Roles: student | expert | partner
#           student  = no bounty access
#           expert   = university researcher, can view + apply
#           partner  = company, can post + manage + control lifecycle
# Purpose: All ORM models for the bounty-collab plugin. Table prefix: bntc_
# =============================================================================

import datetime

from CTFd.models import db


class CollabUserProfile(db.Model):
    """Role profile created when a user first enters the bounty system.
    Stores which actor type they are: student, expert, or partner.
    """

    __tablename__ = "bntc_user_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    # student | expert | partner
    role = db.Column(db.String(16), nullable=False)
    # Institution name — university for experts, company for partners
    institution = db.Column(db.String(256))
    # Expert credential fields (filled at signup, shown to partners when reviewing applications)
    bio = db.Column(db.Text)                        # brief self-description
    expertise_areas = db.Column(db.String(512))     # comma-separated tags
    profile_url = db.Column(db.String(512))         # LinkedIn / ResearchGate / personal site
    credential_id = db.Column(db.String(128))       # staff/student ID or employee number
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<CollabUserProfile user={self.user_id} role={self.role}>"


class CollabProject(db.Model):
    """Enterprise-posted research bounty project."""

    __tablename__ = "bntc_projects"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    category = db.Column(db.String(64))
    problem_statement = db.Column(db.Text, nullable=False)
    scope_of_work = db.Column(db.Text)
    deliverables = db.Column(db.Text)            # newline-delimited list
    required_expertise = db.Column(db.String(512))   # comma-tagged
    team_size_min = db.Column(db.Integer, default=1)
    team_size_max = db.Column(db.Integer, default=5)
    application_deadline = db.Column(db.DateTime)
    research_duration_days = db.Column(db.Integer)
    budget_total = db.Column(db.Integer, nullable=False, default=0)  # cents
    is_nda_required = db.Column(db.Boolean, default=False)
    nda_full_brief = db.Column(db.Text)          # hidden until NDA accepted
    status = db.Column(db.String(32), nullable=False, default="draft")
    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Optional link to ctfd_monetization invoice (nullable)
    invoice_id = db.Column(
        db.Integer,
        db.ForeignKey("mon_invoices.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    applications = db.relationship(
        "CollabApplication", backref="project", cascade="all, delete-orphan"
    )
    team_members = db.relationship(
        "CollabTeamMember", backref="project", cascade="all, delete-orphan"
    )
    deliverable_submissions = db.relationship(
        "CollabDeliverable", backref="project", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<CollabProject id={self.id} title={self.title!r} status={self.status}>"


class CollabApplication(db.Model):
    """Expert application to a CollabProject."""

    __tablename__ = "bntc_applications"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("bntc_projects.id", ondelete="CASCADE")
    )
    applicant_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    team_name = db.Column(db.String(128))
    cover_note = db.Column(db.Text)
    # pending | shortlisted | accepted | rejected | withdrawn
    status = db.Column(db.String(32), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return (
            f"<CollabApplication id={self.id} project={self.project_id} "
            f"status={self.status}>"
        )


class CollabTeamMember(db.Model):
    """Accepted researcher on a locked project team."""

    __tablename__ = "bntc_team_members"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("bntc_projects.id", ondelete="CASCADE")
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_team_lead = db.Column(db.Boolean, default=False)
    payout_percentage = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    # active | removed
    status = db.Column(db.String(16), nullable=False, default="active")
    joined_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return (
            f"<CollabTeamMember id={self.id} project={self.project_id} "
            f"user={self.user_id} pct={self.payout_percentage}>"
        )


class CollabNdaAcceptance(db.Model):
    """Records that a user accepted the NDA for a project."""

    __tablename__ = "bntc_nda_acceptances"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("bntc_projects.id", ondelete="CASCADE")
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE")
    )
    accepted_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("project_id", "user_id", name="uq_bntc_nda"),
    )

    def __repr__(self):
        return f"<CollabNdaAcceptance project={self.project_id} user={self.user_id}>"


class CollabDeliverable(db.Model):
    """Research deliverable submitted by a team member."""

    __tablename__ = "bntc_deliverables"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("bntc_projects.id", ondelete="CASCADE")
    )
    submitted_by = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    content = db.Column(db.Text)
    file_ref = db.Column(db.String(512))        # optional file path/URL
    version_number = db.Column(db.Integer, nullable=False, default=1)
    # submitted | revision_requested | approved
    status = db.Column(db.String(32), nullable=False, default="submitted")
    reviewer_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return (
            f"<CollabDeliverable id={self.id} project={self.project_id} "
            f"v={self.version_number}>"
        )


class CollabEscrowLedger(db.Model):
    """Single escrow record per project — enforced via unique constraint."""

    __tablename__ = "bntc_escrow_ledger"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("bntc_projects.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    total_funded = db.Column(db.Integer, nullable=False, default=0)           # cents
    platform_commission_amount = db.Column(db.Integer, nullable=False, default=0)
    researcher_pool_amount = db.Column(db.Integer, nullable=False, default=0)
    # unfunded | funded | released | refunded
    status = db.Column(db.String(16), nullable=False, default="unfunded")
    funded_at = db.Column(db.DateTime)
    released_at = db.Column(db.DateTime)

    def __repr__(self):
        return f"<CollabEscrowLedger project={self.project_id} status={self.status}>"


class CollabWallet(db.Model):
    """Per-user internal wallet for researcher payouts.
    Created here because ctfd_monetization has no wallet/balance model.
    """

    __tablename__ = "bntc_wallets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    pending_balance = db.Column(db.Integer, nullable=False, default=0)    # cents
    internal_balance = db.Column(db.Integer, nullable=False, default=0)   # cents
    updated_at = db.Column(
        db.DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    transactions = db.relationship(
        "CollabWalletTransaction", backref="wallet", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<CollabWallet user={self.user_id} balance={self.internal_balance}>"


class CollabWalletTransaction(db.Model):
    """Immutable ledger entry for every wallet movement."""

    __tablename__ = "bntc_wallet_transactions"

    id = db.Column(db.Integer, primary_key=True)
    # wallet_id NULL → platform commission entry (no personal wallet)
    wallet_id = db.Column(
        db.Integer,
        db.ForeignKey("bntc_wallets.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("bntc_projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    # escrow_funded | commission_deducted | payout_released | refund
    type = db.Column(db.String(32), nullable=False)
    amount = db.Column(db.Integer, nullable=False, default=0)    # cents
    balance_after = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return (
            f"<CollabWalletTransaction id={self.id} type={self.type} "
            f"amount={self.amount}>"
        )


class CollabAuditLog(db.Model):
    """Immutable audit trail — every status change and fund movement."""

    __tablename__ = "bntc_audit_log"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("bntc_projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action = db.Column(db.String(128), nullable=False)
    before_state = db.Column(db.JSON)
    after_state = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return (
            f"<CollabAuditLog id={self.id} action={self.action!r} "
            f"project={self.project_id}>"
        )
