from __future__ import annotations

from types import SimpleNamespace

import apps.api.app.services.intent_persistence as persistence_module

from apps.api.app.services.auto_pick.contracts import AutoPickDecision
from apps.api.app.services.risk.contracts import RiskSizingDecision
from apps.api.app.services.intent_draft import build_binance_intent_draft
from apps.api.app.services.intent_persistence import persist_binance_intent_from_draft


def _decision():
    return AutoPickDecision(
        symbol="BTCUSDT",
        side="BUY",
        direction="LONG",
        broker="BINANCE",
        asset_profile="CRYPTO",
        model_version="test",
        final_score=0.9,
        decision_reason="test",
        evidence={"entry_price_reference": 100.0},
    )


def _risk():
    return RiskSizingDecision(
        entry_price=100.0,
        stop_loss=99.0,
        take_profit=102.0,
        risk_pct=1.0,
        risk_abs=1.0,
        expected_qty=1.0,
        evidence={},
    )


def test_auto_pick_to_risk_to_intent_flow(monkeypatch):
    captured = {}

    def fake_create_binance_intent(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(persistence_module, "create_binance_intent", fake_create_binance_intent)

    draft = build_binance_intent_draft(
        decision=_decision(),
        risk=_risk(),
    )

    result = persist_binance_intent_from_draft(
        draft=draft,
        db="fake-db",
        user_id="user-1",
        current_user=SimpleNamespace(id="user-1"),
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
