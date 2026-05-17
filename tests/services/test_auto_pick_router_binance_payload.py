from apps.api.app.services.auto_pick.orchestrator import run_auto_pick
from apps.api.app.services.auto_pick.contracts import AutoPickNoTrade


def test_binance_auto_pick_router_accepts_payload_without_signature_error(monkeypatch):
    import apps.api.app.services.auto_pick.orchestrator as router

    def fake_binance_auto_pick(*, payload=None):
        return AutoPickNoTrade(
            broker="BINANCE",
            reason="test",
            evidence={"payload": payload},
        )

    monkeypatch.setattr(router, "run_binance_auto_pick", fake_binance_auto_pick)

    result = run_auto_pick(broker="BINANCE", payload={"source": "test"})

    assert result.evidence["payload"] == {"source": "test"}


def test_real_binance_auto_pick_accepts_payload_keyword():
    from apps.api.app.services.auto_pick.binance.orchestrator import run_binance_auto_pick

    result = run_binance_auto_pick(payload={"source": "router"})

    assert result.broker == "BINANCE"
