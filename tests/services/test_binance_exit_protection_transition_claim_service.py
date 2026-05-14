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
