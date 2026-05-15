from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.app.models.binance_exit_protection import Base, BinanceExitProtection


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _row(**overrides):
    data = {
        "exit_key": "exit-key-1",
        "intent_id": "intent-1",
        "entry_execution_ref": "order-1",
        "symbol": "BTCUSDT",
        "market": "FUTURES",
        "direction": "LONG",
        "filled_qty": Decimal("0.01"),
        "avg_entry_price": Decimal("100"),
        "sl_client_algo_id": "sl-1",
        "tp_client_algo_id": "tp-1",
        "sl_status": "SUBMITTED",
        "tp_status": "SUBMITTED",
        "protection_status": "PROTECTED",
    }
    data.update(overrides)
    return BinanceExitProtection(**data)


def test_loads_only_protected_positions_with_submitted_sl():
    from apps.api.app.services.load_active_protected_positions import (
        load_active_protected_positions,
    )

    db = _db()
    db.add(_row(exit_key="protected-1", sl_client_algo_id="sl-1"))
    db.add(_row(exit_key="unknown-1", protection_status="UNKNOWN", sl_client_algo_id="sl-2"))
    db.add(_row(exit_key="pending-sl-1", sl_status="PENDING", sl_client_algo_id="sl-3"))
    db.commit()

    out = load_active_protected_positions(db)

    assert out == [
        {
            "exit_key": "protected-1",
            "symbol": "BTCUSDT",
            "market": "FUTURES",
            "direction": "LONG",
            "filled_qty": Decimal("0.01"),
            "avg_entry_price": Decimal("100"),
            "sl_client_algo_id": "sl-1",
            "tp_client_algo_id": "tp-1",
            "sl_status": "SUBMITTED",
            "tp_status": "SUBMITTED",
            "protection_status": "PROTECTED",
        }
    ]


def test_loader_returns_empty_when_no_authoritative_protected_positions():
    from apps.api.app.services.load_active_protected_positions import (
        load_active_protected_positions,
    )

    db = _db()
    db.add(_row(exit_key="unknown-1", protection_status="UNKNOWN"))
    db.add(_row(exit_key="failed-sl-1", sl_status="FAILED"))
    db.commit()

    assert load_active_protected_positions(db) == []
