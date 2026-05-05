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
