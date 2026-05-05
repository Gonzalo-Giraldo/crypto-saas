from apps.api.app.services.auto_pick.contracts import AutoPickDecision, AutoPickNoTrade
from apps.api.app.services.risk.contracts import RiskSizingDecision
from apps.api.app.services.runtime_orchestrator import run_binance_trading_cycle


def test_runtime_orchestrator_no_trade_does_not_persist(monkeypatch):
    def fake_run_auto_pick(*, broker, payload=None):
        return AutoPickNoTrade(broker="BINANCE", reason="no_safe_candidate")

    monkeypatch.setattr(
        "apps.api.app.services.runtime_orchestrator.run_auto_pick",
        fake_run_auto_pick,
    )

    out = run_binance_trading_cycle(db=object())

    assert out["status"] == "no_trade"
    assert out["reason"] == "no_safe_candidate"


def test_runtime_orchestrator_draft_ready_does_not_persist_or_execute(monkeypatch):
    def fake_run_auto_pick(*, broker, payload=None):
        return AutoPickDecision(
            symbol="BTCUSDT",
            side="BUY",
            direction="LONG",
            broker="BINANCE",
            asset_profile="CRYPTO",
            model_version="test",
            final_score=90.0,
            decision_reason="test_decision",
            evidence={"entry_price_reference": 100.0},
        )

    def fake_build_risk_from_auto_pick_decision(**kwargs):
        return RiskSizingDecision(
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            risk_pct=0.01,
            risk_abs=10.0,
            expected_qty=0.01,
            evidence={"source": "test"},
        )

    monkeypatch.setattr(
        "apps.api.app.services.runtime_orchestrator.run_auto_pick",
        fake_run_auto_pick,
    )
    monkeypatch.setattr(
        "apps.api.app.services.runtime_orchestrator.build_risk_from_auto_pick_decision",
        fake_build_risk_from_auto_pick_decision,
    )

    out = run_binance_trading_cycle(db=object(), persist_intent=False)

    assert out["status"] == "draft_ready"
    assert out["symbol"] == "BTCUSDT"
    assert out["persisted"] is False
    assert out["executed"] is False
