from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest

from apps.api.app.models.binance_exit_protection import Base, BinanceExitProtection
from apps.api.app.services.binance_exit_protection_service import create_exit_protection


def _build_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _valid_data():
    return dict(
        exit_key="test_key",
        intent_id="intent_1",
        entry_execution_ref="order_123",
        symbol="BTCUSDT",
        market="FUTURES",
        direction="LONG",
        filled_qty=1,
        avg_entry_price=100,
        sl_client_algo_id="sl_1",
        tp_client_algo_id="tp_1",
    )


def test_exit_protection_idempotent_insert():
    db = _build_db()
    data = _valid_data()

    r1 = create_exit_protection(db, **data)
    r2 = create_exit_protection(db, **data)

    assert r1["status"] == "created"
    assert r2["status"] == "duplicate"
    assert db.query(BinanceExitProtection).count() == 1


def test_invalid_market():
    db = _build_db()
    data = _valid_data()
    data["market"] = "SPOT"

    with pytest.raises(ValueError):
        create_exit_protection(db, **data)


def test_invalid_direction():
    db = _build_db()
    data = _valid_data()
    data["direction"] = "BUY"

    with pytest.raises(ValueError):
        create_exit_protection(db, **data)


def test_invalid_qty():
    db = _build_db()
    data = _valid_data()
    data["filled_qty"] = 0

    with pytest.raises(ValueError):
        create_exit_protection(db, **data)


def test_missing_sl_id():
    db = _build_db()
    data = _valid_data()
    data["sl_client_algo_id"] = ""

    with pytest.raises(ValueError):
        create_exit_protection(db, **data)

def test_update_exit_protection_reconciliation_persists_projection():
    from apps.api.app.services.binance_exit_protection_service import (
        update_exit_protection_reconciliation,
    )

    db = _build_db()
    data = _valid_data()
    create_exit_protection(db, **data)

    result = update_exit_protection_reconciliation(
        db,
        exit_key=data["exit_key"],
        sl_status="SUBMITTED",
        tp_status="SUBMITTED",
        protection_status="PROTECTED",
        last_error=None,
        increment_attempt_count=False,
    )

    obj = db.query(BinanceExitProtection).filter_by(exit_key=data["exit_key"]).one()

    assert result == {"status": "updated", "exit_key": data["exit_key"]}
    assert obj.sl_status == "SUBMITTED"
    assert obj.tp_status == "SUBMITTED"
    assert obj.protection_status == "PROTECTED"
    assert obj.last_error is None
    assert obj.attempt_count == 0


def test_update_exit_protection_reconciliation_missing_exit_key_fails_closed():
    from apps.api.app.services.binance_exit_protection_service import (
        update_exit_protection_reconciliation,
    )

    db = _build_db()

    with pytest.raises(ValueError, match="exit_protection_not_found"):
        update_exit_protection_reconciliation(
            db,
            exit_key="missing",
            sl_status="SUBMITTED",
            tp_status="SUBMITTED",
            protection_status="PROTECTED",
        )


def test_update_exit_protection_reconciliation_invalid_status_fails_closed():
    from apps.api.app.services.binance_exit_protection_service import (
        update_exit_protection_reconciliation,
    )

    db = _build_db()
    data = _valid_data()
    create_exit_protection(db, **data)

    with pytest.raises(ValueError, match="invalid_protection_status"):
        update_exit_protection_reconciliation(
            db,
            exit_key=data["exit_key"],
            sl_status="SUBMITTED",
            tp_status="SUBMITTED",
            protection_status="BAD_STATUS",
        )


def test_update_exit_protection_reconciliation_increments_attempt_count_once():
    from apps.api.app.services.binance_exit_protection_service import (
        update_exit_protection_reconciliation,
    )

    db = _build_db()
    data = _valid_data()
    create_exit_protection(db, **data)

    update_exit_protection_reconciliation(
        db,
        exit_key=data["exit_key"],
        sl_status="UNKNOWN",
        tp_status="SUBMITTED",
        protection_status="UNKNOWN",
        last_error="tp_status_fetch_timeout",
        increment_attempt_count=True,
    )

    obj = db.query(BinanceExitProtection).filter_by(exit_key=data["exit_key"]).one()

    assert obj.sl_status == "UNKNOWN"
    assert obj.tp_status == "SUBMITTED"
    assert obj.protection_status == "UNKNOWN"
    assert obj.last_error == "tp_status_fetch_timeout"
    assert obj.attempt_count == 1
