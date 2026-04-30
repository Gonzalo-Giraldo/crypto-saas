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
