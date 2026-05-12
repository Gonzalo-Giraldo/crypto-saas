from __future__ import annotations

from types import SimpleNamespace

import apps.api.app.services.intent_persistence as module

from apps.api.app.services.intent_draft import BinanceIntentDraft
from apps.api.app.services.intent_persistence import persist_binance_intent_from_draft

def _user():
    return SimpleNamespace(
        id="user-1",
    )

def _draft():
    return BinanceIntentDraft(
        symbol="BTCUSDT",
        side="BUY",
        expected_qty=1.0,
        entry_price=100.0,
        stop_loss=99.0,
        take_profit=102.0,
        risk_pct=1.0,
        risk_abs=1.0,
        risk_usdt=1.0,
        reward_risk_ratio=2.0,
        entry_price_reference=100.0,
        auto_pick_trace={
            "final_score": 0.9,
            "decision_reason": "test",
            "evidence": {"entry_price_reference": 100.0},
        },
    )

def test_persist_binance_intent_from_draft_calls_adapter(monkeypatch):
    captured = {}

    def fake_create_binance_intent(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(module, "create_binance_intent", fake_create_binance_intent)

    result = persist_binance_intent_from_draft(
        draft=_draft(),
        db="fake-db",
        user_id="user-1",
        current_user=_user(),
        account_id="acc-1",
    )

    assert result["ok"] is True

    assert captured["symbol"] == "BTCUSDT"
    assert captured["side"] == "BUY"
    assert captured["expected_qty"] == 1.0
    assert captured["entry_price"] == 100.0
    assert captured["stop_loss"] == 99.0
    assert captured["take_profit"] == 102.0

    assert captured["auto_pick_trace"]["final_score"] == 0.9


def test_invalid_input():
    import pytest

    with pytest.raises(ValueError, match="draft_required"):
        persist_binance_intent_from_draft(
            draft=None,
            db="db",
            user_id="u",
            current_user=_user(),
            account_id="a",
        )

def test_persist_binance_intent_from_draft_does_not_execute_by_default(monkeypatch):
    called = {"execute": False}

    def fake_create_binance_intent(**kwargs):
        return {"intent_id": "intent-1", "ok": True}

    def fake_execute(**kwargs):
        called["execute"] = True
        return {"sent": True}

    monkeypatch.setattr(module, "create_binance_intent", fake_create_binance_intent)
    monkeypatch.setattr(module, "execute_binance_real_order_for_user", fake_execute)

    result = persist_binance_intent_from_draft(
        draft=_draft(),
        db="fake-db",
        user_id="user-1",
        current_user=_user(),
        account_id="acc-1",
    )

    assert result["ok"] is True
    assert called["execute"] is False


def test_persist_binance_intent_from_draft_requires_authorization_for_real_execution(monkeypatch):
    def fake_create_binance_intent(**kwargs):
        return {"intent_id": "intent-1", "ok": True}

    monkeypatch.setattr(module, "create_binance_intent", fake_create_binance_intent)

    import pytest
    with pytest.raises(ValueError, match="real_execution_authorization_required"):
        persist_binance_intent_from_draft(
            draft=_draft(),
            db="fake-db",
            user_id="user-1",
            current_user=_user(),
            account_id="acc-1",
            execute_real=True,
        )


def test_persist_binance_intent_from_draft_consumes_then_executes_when_authorized(monkeypatch):
    from types import SimpleNamespace

    events = []

    def fake_create_binance_intent(**kwargs):
        events.append(("create", kwargs))
        return {"intent_id": "intent-1", "ok": True}

    def fake_assert_exposure_limits(**kwargs):
        events.append(("assert_exposure_limits", kwargs))

    monkeypatch.setattr(module, "assert_exposure_limits", fake_assert_exposure_limits)

    def fake_get_intent(db, intent_id):
        events.append(("get_intent", {"intent_id": intent_id}))
        return SimpleNamespace(
            intent_id="intent-1",
            user_id="user-1",
            broker="BINANCE",
            account_id="acc-1",
            lifecycle_status="CREATED",
            symbol="BTCUSDT",
            side="BUY",
            expected_qty=1.25,
            entry_price=100.0,
        )

    def fake_consume_intent(**kwargs):
        events.append(("consume", kwargs))
        return {"lifecycle_status": "CONSUMED"}

    def fake_execute(**kwargs):
        events.append(("execute", kwargs))
        return {"sent": True, "mode": "live_order_spot"}

    monkeypatch.setattr(module, "create_binance_intent", fake_create_binance_intent)
    monkeypatch.setattr(module, "get_intent", fake_get_intent)
    monkeypatch.setattr(module, "consume_intent", fake_consume_intent)
    monkeypatch.setattr(module, "execute_binance_real_order_for_user", fake_execute)
    monkeypatch.setattr(module, "get_trading_enabled", lambda db: True)

    def fake_reserve_idempotent_intent(**kwargs):
        events.append(("reserve_idempotency", kwargs))
        return None

    def fake_finalize_idempotent_intent(**kwargs):
        events.append(("finalize_idempotency", kwargs))

    monkeypatch.setattr(module, "reserve_idempotent_intent", fake_reserve_idempotent_intent)
    monkeypatch.setattr(module, "finalize_idempotent_intent", fake_finalize_idempotent_intent)

    result = persist_binance_intent_from_draft(
        draft=_draft(),
        db="fake-db",
        current_user=_user(),
        user_id="user-1",
        account_id="acc-1",
        execute_real=True,
        execution_authorized=True,
        idempotency_key="idem-test-1",
    )

    assert result["execution"]["sent"] is True
    assert [event[0] for event in events] == [
        "create",
        "get_intent",
        "assert_exposure_limits",
        "reserve_idempotency",
        "consume",
        "execute",
        "finalize_idempotency",
    ]

    exposure_kwargs = events[2][1]
    assert exposure_kwargs["exchange"] == "BINANCE"
    assert exposure_kwargs["symbol"] == "BTCUSDT"

    reserve_kwargs = events[3][1]
    assert reserve_kwargs["idempotency_key"] == "idem-test-1"
    assert reserve_kwargs["endpoint"] == "/execution/binance/intent-execute"

    consume_kwargs = events[4][1]
    assert consume_kwargs["intent_id"] == "intent-1"
    assert consume_kwargs["broker"] == "BINANCE"
    assert consume_kwargs["account_id"] == "acc-1"

    execute_kwargs = events[5][1]
    assert execute_kwargs["user_id"] == "user-1"
    assert execute_kwargs["symbol"] == "BTCUSDT"
    assert execute_kwargs["side"] == "BUY"
    assert execute_kwargs["qty"] == 1.25
    assert execute_kwargs["intent_key"] == "intent-1"
    assert execute_kwargs["account_id"] == "acc-1"
    assert execute_kwargs["market"] is None
