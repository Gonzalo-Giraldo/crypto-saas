from __future__ import annotations

import apps.api.app.services.risk_to_intent as risk_to_intent_module

from apps.api.app.services.auto_pick.contracts import AutoPickDecision
from apps.api.app.services.auto_pick_to_risk import build_risk_from_auto_pick_decision
from apps.api.app.services.risk.contracts import RiskSizingDecision
from apps.api.app.services.risk_to_intent import build_binance_intent_from_risk


def test_auto_pick_to_risk_to_intent_payload_flow_without_db_or_broker(monkeypatch):
    captured = {}

    def fake_create_binance_intent(**kwargs):
        captured.update(kwargs)
        return {
            "intent_id": "mock-intent-id",
            "payload": kwargs,
        }

    monkeypatch.setattr(
        risk_to_intent_module,
        "create_binance_intent",
        fake_create_binance_intent,
    )

    decision = AutoPickDecision(
        symbol="BTCUSDT",
        side="BUY",
        direction="LONG",
        broker="BINANCE",
        asset_profile="CRYPTO",
        model_version="binance_auto_pick_pipeline_v1",
        final_score=0.87,
        decision_reason="selected_top_ranked_candidate",
        evidence={
            "entry_price_reference": 100.0,
            "entry_price_source": "ticker.lastPrice",
            "entry_price_semantics": "reference_only_not_fill",
            "ranked_count": 3,
            "selected_rank": 1,
        },
    )

    risk = build_risk_from_auto_pick_decision(
        decision=decision,
        capital_base=1000.0,
        risk_pct=1.0,
        reward_risk_ratio=2.0,
    )

    assert isinstance(risk, RiskSizingDecision)
    assert risk.entry_price == 100.0
    assert risk.stop_loss == 99.0
    assert risk.take_profit == 102.0
    assert risk.expected_qty == 10.0
    assert risk.evidence["risk_usdt"] == 10.0
    assert risk.evidence["risk_real"] == 10.0

    result = build_binance_intent_from_risk(
        decision=decision,
        risk=risk,
    )

    assert result["intent_id"] == "mock-intent-id"

    assert captured == {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "expected_qty": 10.0,
        "entry_price": 100.0,
        "stop_loss": 99.0,
        "take_profit": 102.0,
        "auto_pick_trace": {
            "final_score": 0.87,
            "decision_reason": "selected_top_ranked_candidate",
            "evidence": {
                "entry_price_reference": 100.0,
                "entry_price_source": "ticker.lastPrice",
                "entry_price_semantics": "reference_only_not_fill",
                "ranked_count": 3,
                "selected_rank": 1,
            },
        },
    }


def test_auto_pick_to_risk_to_intent_sell_flow_without_db_or_broker(monkeypatch):
    captured = {}

    def fake_create_binance_intent(**kwargs):
        captured.update(kwargs)
        return {"intent_id": "mock-short-intent-id", "payload": kwargs}

    monkeypatch.setattr(
        risk_to_intent_module,
        "create_binance_intent",
        fake_create_binance_intent,
    )

    decision = AutoPickDecision(
        symbol="ETHUSDT",
        side="SELL",
        direction="SHORT",
        broker="BINANCE",
        asset_profile="CRYPTO",
        model_version="binance_auto_pick_pipeline_v1",
        final_score=0.81,
        decision_reason="selected_top_ranked_candidate",
        evidence={
            "entry_price_reference": 100.0,
            "entry_price_source": "ticker.lastPrice",
            "entry_price_semantics": "reference_only_not_fill",
        },
    )

    risk = build_risk_from_auto_pick_decision(
        decision=decision,
        capital_base=1000.0,
        risk_pct=1.0,
        reward_risk_ratio=2.0,
    )

    assert risk.entry_price == 100.0
    assert risk.stop_loss == 101.0
    assert risk.take_profit == 98.0
    assert risk.expected_qty == 10.0

    result = build_binance_intent_from_risk(decision=decision, risk=risk)

    assert result["intent_id"] == "mock-short-intent-id"
    assert captured["symbol"] == "ETHUSDT"
    assert captured["side"] == "SELL"
    assert captured["entry_price"] == 100.0
    assert captured["stop_loss"] == 101.0
    assert captured["take_profit"] == 98.0
    assert captured["expected_qty"] == 10.0
    assert captured["auto_pick_trace"]["evidence"]["entry_price_semantics"] == "reference_only_not_fill"
