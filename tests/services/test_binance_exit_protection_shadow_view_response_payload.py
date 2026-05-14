from apps.worker.app.engine.binance_exit_protection_shadow_view import (
    build_exit_protection_shadow_view,
)


class FakeResponse:
    pass


def fake_post(url, json, timeout):
    client_algo_id = json["clientAlgoId"]
    return FakeGatewayResponse(
        {
            "clientAlgoId": client_algo_id,
            "status": "NEW",
            "algoId": 12345,
        }
    )


class FakeGatewayResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_shadow_view_uses_gateway_response_payload_for_evidence():
    view = build_exit_protection_shadow_view(
        api_key="k",
        api_secret="s",
        symbol="BTCUSDT",
        sl_client_algo_id="sl-1",
        tp_client_algo_id="tp-1",
        post=fake_post,
    )

    evidence = view["evidence_view"]

    assert view["shadow_mode"] is True
    assert view["authority_granted"] is False
    assert view["runtime_action_allowed"] is False
    assert evidence["sl_classification"] == "ACTIVE_EVIDENCE_PRESENT"
    assert evidence["tp_classification"] == "ACTIVE_EVIDENCE_PRESENT"
    assert evidence["both_active_evidence_present"] is True
