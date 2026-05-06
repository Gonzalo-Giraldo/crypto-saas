from apps.api.app.services.global_orchestrator import run_global_shadow_cycle


def test_global_shadow_cycle_delegates_without_persisting_or_executing(monkeypatch):
    def fake_run_modular_shadow_trading_tick(**kwargs):
        return {
            "status": "ok",
            "binance": {"status": "draft_ready", "symbol": "BTCUSDT"},
            "persisted": False,
            "executed": False,
        }

    monkeypatch.setattr(
        "apps.api.app.services.global_orchestrator.run_modular_shadow_trading_tick",
        fake_run_modular_shadow_trading_tick,
    )

    out = run_global_shadow_cycle(db=object())

    assert out["status"] == "ok"
    assert out["trading"]["binance"]["symbol"] == "BTCUSDT"
    assert out["persisted"] is False
    assert out["executed"] is False
