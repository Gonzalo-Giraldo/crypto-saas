from __future__ import annotations

import apps.api.app.services.intent_persistence as module

from apps.api.app.services.intent_draft import BinanceIntentDraft
from apps.api.app.services.intent_persistence import persist_binance_intent_from_draft


def _draft():
    return BinanceIntentDraft(
        symbol="BTCUSDT",
        side="BUY",
        expected_qty=1.0,
        entry_price=100.0,
        stop_loss=99.0,
        take_profit=102.0,
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
            account_id="acc-1",
            execute_real=True,
        )


def test_persist_binance_intent_from_draft_consumes_then_executes_when_authorized(monkeypatch):
    from types import SimpleNamespace

    events = []

    def fake_create_binance_intent(**kwargs):
        events.append(("create", kwargs))
        return {"intent_id": "intent-1", "ok": True}

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

    result = persist_binance_intent_from_draft(
        draft=_draft(),
        db="fake-db",
        user_id="user-1",
        account_id="acc-1",
        execute_real=True,
        execution_authorized=True,
    )

    assert result["execution"]["sent"] is True
    assert [event[0] for event in events] == ["create", "get_intent", "consume", "execute"]

    consume_kwargs = events[2][1]
    assert consume_kwargs["intent_id"] == "intent-1"
    assert consume_kwargs["broker"] == "BINANCE"
    assert consume_kwargs["account_id"] == "acc-1"

    execute_kwargs = events[3][1]
    assert execute_kwargs["user_id"] == "user-1"
    assert execute_kwargs["symbol"] == "BTCUSDT"
    assert execute_kwargs["side"] == "BUY"
    assert execute_kwargs["qty"] == 1.25
    assert execute_kwargs["intent_key"] == "intent-1"
    assert execute_kwargs["account_id"] == "acc-1"
    assert execute_kwargs["market"] is None
