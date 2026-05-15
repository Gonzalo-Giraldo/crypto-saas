import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.app.db.session import Base


def _build_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_first_owner_claims_transition():
    from apps.api.app.services.binance_exit_protection_transition_claim_service import (
        claim_exit_protection_transition,
    )

    db = _build_db()

    result = claim_exit_protection_transition(
        db,
        exit_key="exit-key-1",
        required_action="START_AUTHORITATIVE_REPLACEMENT",
        owner_id="worker-1",
    )

    assert result == {
        "status": "claimed",
        "exit_key": "exit-key-1",
        "required_action": "START_AUTHORITATIVE_REPLACEMENT",
        "owner_id": "worker-1",
    }


def test_second_owner_is_rejected_while_claim_active():
    from apps.api.app.services.binance_exit_protection_transition_claim_service import (
        claim_exit_protection_transition,
    )

    db = _build_db()

    claim_exit_protection_transition(
        db,
        exit_key="exit-key-1",
        required_action="START_AUTHORITATIVE_REPLACEMENT",
        owner_id="worker-1",
    )

    with pytest.raises(ValueError, match="transition_claim_already_owned"):
        claim_exit_protection_transition(
            db,
            exit_key="exit-key-1",
            required_action="START_AUTHORITATIVE_REPLACEMENT",
            owner_id="worker-2",
        )


def test_same_owner_claim_is_idempotent():
    from apps.api.app.services.binance_exit_protection_transition_claim_service import (
        claim_exit_protection_transition,
    )

    db = _build_db()

    claim_exit_protection_transition(
        db,
        exit_key="exit-key-1",
        required_action="START_AUTHORITATIVE_REPLACEMENT",
        owner_id="worker-1",
    )

    result = claim_exit_protection_transition(
        db,
        exit_key="exit-key-1",
        required_action="START_AUTHORITATIVE_REPLACEMENT",
        owner_id="worker-1",
    )

    assert result == {
        "status": "already_owned",
        "exit_key": "exit-key-1",
        "required_action": "START_AUTHORITATIVE_REPLACEMENT",
        "owner_id": "worker-1",
    }


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("exit_key", "", "exit_key_required"),
        ("required_action", "", "required_action_required"),
        ("owner_id", "", "owner_id_required"),
    ],
)
def test_claim_missing_required_fields_fail_closed(field, value, error):
    from apps.api.app.services.binance_exit_protection_transition_claim_service import (
        claim_exit_protection_transition,
    )

    db = _build_db()
    kwargs = {
        "exit_key": "exit-key-1",
        "required_action": "START_AUTHORITATIVE_REPLACEMENT",
        "owner_id": "worker-1",
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match=error):
        claim_exit_protection_transition(db, **kwargs)


def test_unsupported_required_action_fails_closed():
    from apps.api.app.services.binance_exit_protection_transition_claim_service import (
        claim_exit_protection_transition,
    )

    db = _build_db()

    with pytest.raises(ValueError, match="unsupported_required_action"):
        claim_exit_protection_transition(
            db,
            exit_key="exit-key-1",
            required_action="UNSAFE_UNKNOWN_ACTION",
            owner_id="worker-1",
        )


def test_evaluate_transition_claim_staleness_marks_old_active_claim_stale():
    from datetime import datetime, timedelta

    from apps.api.app.services.binance_exit_protection_transition_claim_service import (
        evaluate_transition_claim_staleness,
    )

    result = evaluate_transition_claim_staleness(
        claim_status="ACTIVE",
        updated_at=datetime.utcnow() - timedelta(minutes=31),
        now=datetime.utcnow(),
        stale_after_seconds=1800,
    )

    assert result == {
        "status": "STALE",
        "reason": "active_claim_stale",
    }


def test_evaluate_transition_claim_staleness_keeps_fresh_active_claim_active():
    from datetime import datetime, timedelta

    from apps.api.app.services.binance_exit_protection_transition_claim_service import (
        evaluate_transition_claim_staleness,
    )

    now = datetime.utcnow()

    result = evaluate_transition_claim_staleness(
        claim_status="ACTIVE",
        updated_at=now - timedelta(minutes=5),
        now=now,
        stale_after_seconds=1800,
    )

    assert result == {
        "status": "ACTIVE",
        "reason": "active_claim_fresh",
    }


def test_evaluate_transition_claim_staleness_marks_non_active_claim_not_active():
    from datetime import datetime

    from apps.api.app.services.binance_exit_protection_transition_claim_service import (
        evaluate_transition_claim_staleness,
    )

    result = evaluate_transition_claim_staleness(
        claim_status="FINALIZED",
        updated_at=datetime.utcnow(),
        now=datetime.utcnow(),
        stale_after_seconds=1800,
    )

    assert result == {
        "status": "NOT_ACTIVE",
        "reason": "claim_not_active",
    }


def test_complete_transition_claim_finalizes_active_claim_for_owner():
    from apps.api.app.models.binance_exit_protection_transition_claim import (
        BinanceExitProtectionTransitionClaim,
    )
    from apps.api.app.services.binance_exit_protection_transition_claim_service import (
        claim_exit_protection_transition,
        complete_exit_protection_transition_claim,
    )

    db = _build_db()

    claim_exit_protection_transition(
        db,
        exit_key="exit-key-finalize-1",
        required_action="START_AUTHORITATIVE_REPLACEMENT",
        owner_id="worker-1",
    )

    result = complete_exit_protection_transition_claim(
        db,
        exit_key="exit-key-finalize-1",
        required_action="START_AUTHORITATIVE_REPLACEMENT",
        owner_id="worker-1",
        final_status="FINALIZED",
    )

    assert result == {
        "status": "FINALIZED",
        "exit_key": "exit-key-finalize-1",
        "required_action": "START_AUTHORITATIVE_REPLACEMENT",
        "owner_id": "worker-1",
    }

    row = db.query(BinanceExitProtectionTransitionClaim).filter_by(
        exit_key="exit-key-finalize-1"
    ).one()
    assert row.claim_status == "FINALIZED"


def test_complete_transition_claim_rejects_wrong_owner():
    from apps.api.app.services.binance_exit_protection_transition_claim_service import (
        claim_exit_protection_transition,
        complete_exit_protection_transition_claim,
    )

    db = _build_db()

    claim_exit_protection_transition(
        db,
        exit_key="exit-key-finalize-2",
        required_action="START_AUTHORITATIVE_REPLACEMENT",
        owner_id="worker-1",
    )

    with pytest.raises(ValueError, match="transition_claim_not_owned"):
        complete_exit_protection_transition_claim(
            db,
            exit_key="exit-key-finalize-2",
            required_action="START_AUTHORITATIVE_REPLACEMENT",
            owner_id="worker-2",
            final_status="FINALIZED",
        )


def test_complete_transition_claim_rejects_invalid_final_status():
    from apps.api.app.services.binance_exit_protection_transition_claim_service import (
        claim_exit_protection_transition,
        complete_exit_protection_transition_claim,
    )

    db = _build_db()

    claim_exit_protection_transition(
        db,
        exit_key="exit-key-finalize-3",
        required_action="START_AUTHORITATIVE_REPLACEMENT",
        owner_id="worker-1",
    )

    with pytest.raises(ValueError, match="invalid_final_claim_status"):
        complete_exit_protection_transition_claim(
            db,
            exit_key="exit-key-finalize-3",
            required_action="START_AUTHORITATIVE_REPLACEMENT",
            owner_id="worker-1",
            final_status="ACTIVE",
        )


def test_can_recover_stale_claim_for_same_owner():
    from apps.api.app.services.binance_exit_protection_transition_claim_service import (
        can_recover_stale_transition_claim,
    )

    result = can_recover_stale_transition_claim(
        staleness_status="STALE",
        claim_owner_id="worker-1",
        requester_owner_id="worker-1",
    )

    assert result == {
        "allowed": True,
        "reason": "stale_claim_recoverable",
    }


def test_rejects_recovery_for_different_owner():
    from apps.api.app.services.binance_exit_protection_transition_claim_service import (
        can_recover_stale_transition_claim,
    )

    result = can_recover_stale_transition_claim(
        staleness_status="STALE",
        claim_owner_id="worker-1",
        requester_owner_id="worker-2",
    )

    assert result == {
        "allowed": False,
        "reason": "stale_claim_owned_by_different_owner",
    }


def test_rejects_recovery_for_non_stale_claim():
    from apps.api.app.services.binance_exit_protection_transition_claim_service import (
        can_recover_stale_transition_claim,
    )

    result = can_recover_stale_transition_claim(
        staleness_status="ACTIVE",
        claim_owner_id="worker-1",
        requester_owner_id="worker-1",
    )

    assert result == {
        "allowed": False,
        "reason": "claim_not_stale",
    }
