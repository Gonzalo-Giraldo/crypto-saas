from sqlalchemy import CheckConstraint, Column, DateTime, Index, Integer, String, func

from apps.api.app.db.session import Base


class BinanceExitProtectionTransitionClaim(Base):
    __tablename__ = "binance_exit_protection_transition_claims"

    id = Column(Integer, primary_key=True, nullable=False)
    exit_key = Column(String, nullable=False)
    required_action = Column(String, nullable=False)
    owner_id = Column(String, nullable=False)
    claim_status = Column(String, nullable=False, default="ACTIVE")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index(
            "uq_binance_exit_protection_transition_claim_active",
            "exit_key",
            "required_action",
            unique=True,
            sqlite_where=(claim_status == "ACTIVE"),
            postgresql_where=(claim_status == "ACTIVE"),
        ),
        CheckConstraint(
            "claim_status IN ('ACTIVE', 'RELEASED', 'FINALIZED', 'ABANDONED')",
            name="ck_binance_exit_protection_transition_claim_status",
        ),
    )
