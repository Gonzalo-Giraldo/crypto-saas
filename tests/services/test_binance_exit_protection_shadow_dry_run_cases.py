from apps.worker.app.engine.binance_exit_protection_evidence_view import (
    build_exit_protection_evidence_view,
)


def test_shadow_dry_run_good_new_pair_is_not_authority():
    view = build_exit_protection_evidence_view(
        sl_payload={"status": "NEW", "algoId": 1, "clientAlgoId": "sl"},
        tp_payload={"status": "NEW", "algoId": 2, "clientAlgoId": "tp"},
    )

    assert view["both_active_evidence_present"] is True
    assert view["active_protection_verifiable"] is False


def test_shadow_dry_run_missing_tp_is_unknown():
    view = build_exit_protection_evidence_view(
        sl_payload={"status": "NEW", "algoId": 1, "clientAlgoId": "sl"},
        tp_payload=None,
    )

    assert view["has_unknown"] is True
    assert view["both_active_evidence_present"] is False
    assert view["active_protection_verifiable"] is False


def test_shadow_dry_run_contradictory_sl_is_inconsistent():
    view = build_exit_protection_evidence_view(
        sl_payload={"status": "NEW"},
        tp_payload={"status": "NEW", "algoId": 2, "clientAlgoId": "tp"},
    )

    assert view["has_inconsistent"] is True
    assert view["both_active_evidence_present"] is False
    assert view["active_protection_verifiable"] is False


def test_shadow_dry_run_triggered_leg_is_not_active_pair():
    view = build_exit_protection_evidence_view(
        sl_payload={"status": "FILLED", "algoId": 1, "clientAlgoId": "sl"},
        tp_payload={"status": "NEW", "algoId": 2, "clientAlgoId": "tp"},
    )

    assert view["sl_classification"] == "TRIGGERED_OR_FILLED"
    assert view["both_active_evidence_present"] is False
    assert view["active_protection_verifiable"] is False


def test_shadow_dry_run_expired_leg_is_inactive_not_authority():
    view = build_exit_protection_evidence_view(
        sl_payload={"status": "EXPIRED", "algoId": 1, "clientAlgoId": "sl"},
        tp_payload={"status": "NEW", "algoId": 2, "clientAlgoId": "tp"},
    )

    assert view["sl_classification"] == "INACTIVE_PROTECTION"
    assert view["both_active_evidence_present"] is False
    assert view["active_protection_verifiable"] is False
