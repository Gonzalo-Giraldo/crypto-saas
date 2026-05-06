from apps.api.app.services.scheduler_runtime import run_modular_shadow_trading_tick


def test_modular_shadow_trading_tick_does_not_persist_or_execute(monkeypatch):
    def fake_run_binance_trading_cycle(**kwargs):
        assert kwargs["persist_intent"] is False
        assert kwargs["execute_real"] is False
        assert kwargs["execution_authorized"] is False
        return {
            "status": "draft_ready",
            "symbol": "BTCUSDT",
            "persisted": False,
            "executed": False,
        }

    monkeypatch.setattr(
        "apps.api.app.services.scheduler_runtime.run_binance_trading_cycle",
        fake_run_binance_trading_cycle,
    )

    out = run_modular_shadow_trading_tick(db=object())

    assert out["status"] == "ok"
    assert out["binance"]["symbol"] == "BTCUSDT"
    assert out["persisted"] is False
    assert out["executed"] is False
    assert out["ibkr"]["status"] == "fail_closed"
    assert out["ibkr"]["broker"] == "IBKR"
    assert out["ibkr"]["persisted"] is False
    assert out["ibkr"]["executed"] is False
