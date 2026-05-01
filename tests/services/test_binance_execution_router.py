from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import apps.api.app.api.binance_execution as module


def test_request_normalizes_symbol_and_side():
    payload = module.BinanceIntentExecuteRequest(
        symbol="btcusdt",
        side="buy",
        qty=0.0001,
        entry_price=60000,
        stop_loss=59000,
        take_profit=62000,
    )

    assert payload.symbol == "BTCUSDT"
    assert payload.side == "BUY"
    assert payload.account_id == "default"


def test_request_rejects_invalid_symbol_quote():
    with pytest.raises(ValidationError):
        module.BinanceIntentExecuteRequest(
            symbol="BTCUSD",
            side="BUY",
            qty=0.0001,
            entry_price=60000,
            stop_loss=59000,
            take_profit=62000,
        )


def test_request_rejects_invalid_side():
    with pytest.raises(ValidationError):
        module.BinanceIntentExecuteRequest(
            symbol="BTCUSDT",
            side="HOLD",
            qty=0.0001,
            entry_price=60000,
            stop_loss=59000,
            take_profit=62000,
        )


def test_intent_execute_requires_authorization_before_real_execution(monkeypatch):
    called = {"persist": False}

    def fake_persist(**kwargs):
        called["persist"] = True
        return {"ok": True}

    monkeypatch.setattr(module, "persist_binance_intent_from_draft", fake_persist)

    payload = module.BinanceIntentExecuteRequest(
        symbol="BTCUSDT",
        side="BUY",
        qty=0.0001,
        entry_price=60000,
        stop_loss=59000,
        take_profit=62000,
        execute_real=True,
        execution_authorized=False,
    )

    with pytest.raises(HTTPException) as exc:
        module.intent_execute_binance(
            payload=payload,
            db="fake-db",
            current_user=SimpleNamespace(id="user-1"),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "real_execution_authorization_required"
    assert called["persist"] is False


def test_intent_execute_builds_draft_and_delegates_when_authorized(monkeypatch):
    captured = {}

    def fake_persist(**kwargs):
        captured.update(kwargs)
        return {"intent_id": "intent-1", "execution": {"sent": True}}

    monkeypatch.setattr(module, "persist_binance_intent_from_draft", fake_persist)

    payload = module.BinanceIntentExecuteRequest(
        symbol="BTCUSDT",
        side="BUY",
        qty=0.0001,
        entry_price=60000,
        stop_loss=59000,
        take_profit=62000,
        account_id="default",
        execute_real=True,
        execution_authorized=True,
    )

    result = module.intent_execute_binance(
        payload=payload,
        db="fake-db",
        current_user=SimpleNamespace(id="user-1"),
    )

    assert result["execution"]["sent"] is True
    assert captured["db"] == "fake-db"
    assert captured["user_id"] == "user-1"
    assert captured["account_id"] == "default"
    assert captured["execute_real"] is True
    assert captured["execution_authorized"] is True
    assert captured["draft"].symbol == "BTCUSDT"
    assert captured["draft"].side == "BUY"
    assert captured["draft"].expected_qty == 0.0001
    assert captured["draft"].auto_pick_trace["decision_reason"] == "manual_binance_execution_request"
