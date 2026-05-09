from apps.worker.app.engine.binance_exit_protection_shadow_view import (
    build_exit_protection_shadow_view,
)


def test_shadow_view_builds_read_only_evidence_pipeline(monkeypatch):
    from apps.worker.app.engine import binance_exit_protection_shadow_view as mod

    calls = []

    def fake_fetch(**kwargs):
        calls.append(kwargs)

        if kwargs.get("client_algo_id") == "sl-1":
            return {
                "ok": True,
                "status": "SUCCESS",
                "mode": "gateway_algo_order_status_futures",
                "data": {
                    "status": "NEW",
                    "algoId": 11,
                    "clientAlgoId": "sl-1",
                },
            }

        return {
            "ok": True,
            "status": "SUCCESS",
            "mode": "gateway_algo_order_status_futures",
            "data": {
                "status": "NEW",
                "algoId": 22,
                "clientAlgoId": "tp-1",
            },
        }

    monkeypatch.setattr(
        mod,
        "fetch_algo_order_status_via_gateway",
        fake_fetch,
    )

    out = build_exit_protection_shadow_view(
        api_key="k",
        api_secret="s",
        symbol="BTCUSDT",
        sl_client_algo_id="sl-1",
        tp_client_algo_id="tp-1",
    )

    assert out["shadow_mode"] is True
    assert out["authority_granted"] is False
    assert out["runtime_action_allowed"] is False

    assert out["evidence_view"]["both_active_evidence_present"] is True
    assert out["evidence_view"]["active_protection_verifiable"] is False

    assert len(calls) == 2


def test_shadow_view_keeps_unknown_without_runtime_authority(monkeypatch):
    from apps.worker.app.engine import binance_exit_protection_shadow_view as mod

    def fake_fetch(**kwargs):
        return {
            "ok": False,
            "status": "TIMEOUT",
            "error": "gateway_read_timeout",
        }

    monkeypatch.setattr(
        mod,
        "fetch_algo_order_status_via_gateway",
        fake_fetch,
    )

    out = build_exit_protection_shadow_view(
        api_key="k",
        api_secret="s",
        symbol="BTCUSDT",
        sl_algo_id=1,
        tp_algo_id=2,
    )

    assert out["shadow_mode"] is True
    assert out["authority_granted"] is False
    assert out["runtime_action_allowed"] is False

    assert out["evidence_view"]["has_unknown"] is True
    assert out["evidence_view"]["both_active_evidence_present"] is False
