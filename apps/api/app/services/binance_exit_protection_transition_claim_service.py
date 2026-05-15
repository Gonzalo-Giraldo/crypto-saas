from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.app.models.binance_exit_protection_transition_claim import (
    BinanceExitProtectionTransitionClaim,
)

ALLOWED_TRANSITION_ACTIONS = {
    "START_AUTHORITATIVE_REPLACEMENT",
}


def claim_exit_protection_transition(
    db: Session,
    *,
    exit_key: str,
    required_action: str,
    owner_id: str,
):
    exit_key_value = str(exit_key or "").strip()
    required_action_value = str(required_action or "").strip()
    owner_id_value = str(owner_id or "").strip()

    if not exit_key_value:
        raise ValueError("exit_key_required")

    if not required_action_value:
        raise ValueError("required_action_required")

    if not owner_id_value:
        raise ValueError("owner_id_required")

    if required_action_value not in ALLOWED_TRANSITION_ACTIONS:
        raise ValueError("unsupported_required_action")

    # DB partial unique index is the authoritative concurrency boundary.
    existing = (
        db.query(BinanceExitProtectionTransitionClaim)
        .filter(
            BinanceExitProtectionTransitionClaim.exit_key == exit_key_value,
            BinanceExitProtectionTransitionClaim.required_action == required_action_value,
            BinanceExitProtectionTransitionClaim.claim_status == "ACTIVE",
        )
        .one_or_none()
    )

    if existing is not None:
        if existing.owner_id == owner_id_value:
            return {
                "status": "already_owned",
                "exit_key": exit_key_value,
                "required_action": required_action_value,
                "owner_id": owner_id_value,
            }
        raise ValueError("transition_claim_already_owned")

    claim = BinanceExitProtectionTransitionClaim(
        exit_key=exit_key_value,
        required_action=required_action_value,
        owner_id=owner_id_value,
        claim_status="ACTIVE",
    )
    db.add(claim)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(BinanceExitProtectionTransitionClaim)
            .filter(
                BinanceExitProtectionTransitionClaim.exit_key == exit_key_value,
                BinanceExitProtectionTransitionClaim.required_action == required_action_value,
                BinanceExitProtectionTransitionClaim.claim_status == "ACTIVE",
            )
            .one_or_none()
        )
        if existing is not None and existing.owner_id == owner_id_value:
            return {
                "status": "already_owned",
                "exit_key": exit_key_value,
                "required_action": required_action_value,
                "owner_id": owner_id_value,
            }
        raise ValueError("transition_claim_already_owned")
    except Exception:
        db.rollback()
        raise

    return {
        "status": "claimed",
        "exit_key": exit_key_value,
        "required_action": required_action_value,
        "owner_id": owner_id_value,
    }


def evaluate_transition_claim_staleness(
    *,
    claim_status,
    updated_at,
    now,
    stale_after_seconds: int,
):
    status = str(claim_status or "").upper().strip()

    if status != "ACTIVE":
        return {
            "status": "NOT_ACTIVE",
            "reason": "claim_not_active",
        }

    try:
        age_seconds = (now - updated_at).total_seconds()
    except Exception:
        return {
            "status": "UNKNOWN",
            "reason": "claim_age_unknown",
        }

    if age_seconds > stale_after_seconds:
        return {
            "status": "STALE",
            "reason": "active_claim_stale",
        }

    return {
        "status": "ACTIVE",
        "reason": "active_claim_fresh",
    }


_FINAL_CLAIM_STATUSES = {"RELEASED", "FINALIZED", "ABANDONED"}


def complete_exit_protection_transition_claim(
    db: Session,
    *,
    exit_key: str,
    required_action: str,
    owner_id: str,
    final_status: str,
):
    exit_key_value = str(exit_key or "").strip()
    required_action_value = str(required_action or "").strip()
    owner_id_value = str(owner_id or "").strip()
    final_status_value = str(final_status or "").upper().strip()

    if not exit_key_value:
        raise ValueError("exit_key_required")

    if not required_action_value:
        raise ValueError("required_action_required")

    if not owner_id_value:
        raise ValueError("owner_id_required")

    if final_status_value not in _FINAL_CLAIM_STATUSES:
        raise ValueError("invalid_final_claim_status")

    claim = (
        db.query(BinanceExitProtectionTransitionClaim)
        .filter(
            BinanceExitProtectionTransitionClaim.exit_key == exit_key_value,
            BinanceExitProtectionTransitionClaim.required_action == required_action_value,
            BinanceExitProtectionTransitionClaim.claim_status == "ACTIVE",
        )
        .one_or_none()
    )

    if claim is None:
        raise ValueError("active_transition_claim_not_found")

    if claim.owner_id != owner_id_value:
        raise ValueError("transition_claim_not_owned")

    claim.claim_status = final_status_value

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "status": final_status_value,
        "exit_key": exit_key_value,
        "required_action": required_action_value,
        "owner_id": owner_id_value,
    }
