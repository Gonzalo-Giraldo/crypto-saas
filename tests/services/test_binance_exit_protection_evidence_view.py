from apps.worker.app.engine.binance_exit_protection_evidence_view import (
    build_exit_protection_evidence_view,
)


def test_both_new_orders_are_only_active_evidence_not_verifiable():
    view = build_exit_protection_evidence_view(
        sl_payload={
            "status": "NEW",
            "algoId": 11,
            "clientAlgoId": "sl-1",
        },
        tp_payload={
            "status": "NEW",
            "algoId": 22,
            "clientAlgoId": "tp-1",
        },
    )

    assert view["sl_classification"] == "ACTIVE_EVIDENCE_PRESENT"
    assert view["tp_classification"] == "ACTIVE_EVIDENCE_PRESENT"
    assert view["both_active_evidence_present"] is True
    assert view["active_protection_verifiable"] is False
    assert view["has_unknown"] is False
    assert view["has_inconsistent"] is False


def test_missing_tp_payload_keeps_unknown_and_not_verifiable():
    view = build_exit_protection_evidence_view(
        sl_payload={
            "status": "NEW",
            "algoId": 11,
            "clientAlgoId": "sl-1",
        },
        tp_payload=None,
    )

    assert view["sl_classification"] == "ACTIVE_EVIDENCE_PRESENT"
    assert view["tp_classification"] == "UNKNOWN"
    assert view["both_active_evidence_present"] is False
    assert view["active_protection_verifiable"] is False
    assert view["has_unknown"] is True


def test_inconsistent_leg_is_reported_without_authority():
    view = build_exit_protection_evidence_view(
        sl_payload={
            "status": "NEW",
        },
        tp_payload={
            "status": "NEW",
            "algoId": 22,
            "clientAlgoId": "tp-1",
        },
    )

    assert view["sl_classification"] == "INCONSISTENT"
    assert view["tp_classification"] == "ACTIVE_EVIDENCE_PRESENT"
    assert view["both_active_evidence_present"] is False
    assert view["active_protection_verifiable"] is False
    assert view["has_inconsistent"] is True


def test_filled_leg_is_not_active_evidence_pair():
    view = build_exit_protection_evidence_view(
        sl_payload={
            "status": "FILLED",
            "algoId": 11,
            "clientAlgoId": "sl-1",
        },
        tp_payload={
            "status": "NEW",
            "algoId": 22,
            "clientAlgoId": "tp-1",
        },
    )

    assert view["sl_classification"] == "TRIGGERED_OR_FILLED"
    assert view["tp_classification"] == "ACTIVE_EVIDENCE_PRESENT"
    assert view["both_active_evidence_present"] is False
    assert view["active_protection_verifiable"] is False
    assert view["has_unknown"] is False
