from apps.worker.app.engine.binance_algo_order_classifier import (
    classify_algo_order_evidence,
)


def test_non_dict_evidence_is_unknown():
    assert classify_algo_order_evidence(None) == "UNKNOWN"


def test_missing_payload_is_unknown():
    assert classify_algo_order_evidence({"has_payload": False}) == "UNKNOWN"


def test_missing_status_is_unknown():
    assert classify_algo_order_evidence(
        {
            "has_payload": True,
            "has_status": False,
            "has_algo_id": True,
            "protection_active_declared": False,
        }
    ) == "UNKNOWN"


def test_new_with_identifier_is_only_active_evidence_present():
    out = classify_algo_order_evidence(
        {
            "has_payload": True,
            "status": "NEW",
            "has_status": True,
            "has_algo_id": True,
            "has_client_algo_id": False,
            "protection_active_declared": False,
        }
    )

    assert out == "ACTIVE_EVIDENCE_PRESENT"


def test_active_evidence_without_identifier_is_inconsistent():
    out = classify_algo_order_evidence(
        {
            "has_payload": True,
            "status": "NEW",
            "has_status": True,
            "has_algo_id": False,
            "has_client_algo_id": False,
            "protection_active_declared": False,
        }
    )

    assert out == "INCONSISTENT"


def test_filled_is_triggered_or_filled_not_active():
    assert classify_algo_order_evidence(
        {
            "has_payload": True,
            "status": "FILLED",
            "has_status": True,
            "has_algo_id": True,
            "protection_active_declared": False,
        }
    ) == "TRIGGERED_OR_FILLED"


def test_partially_filled_is_triggered_or_filled_not_active():
    assert classify_algo_order_evidence(
        {
            "has_payload": True,
            "status": "PARTIALLY_FILLED",
            "has_status": True,
            "has_client_algo_id": True,
            "protection_active_declared": False,
        }
    ) == "TRIGGERED_OR_FILLED"


def test_cancelled_and_expired_are_inactive():
    for status in ("CANCELED", "CANCELLED", "EXPIRED", "EXPIRED_IN_MATCH", "REJECTED"):
        assert classify_algo_order_evidence(
            {
                "has_payload": True,
                "status": status,
                "has_status": True,
                "has_algo_id": True,
                "protection_active_declared": False,
            }
        ) == "INACTIVE_PROTECTION"


def test_unknown_status_remains_unknown():
    assert classify_algo_order_evidence(
        {
            "has_payload": True,
            "status": "SOMETHING_NEW_FROM_BINANCE",
            "has_status": True,
            "has_algo_id": True,
            "protection_active_declared": False,
        }
    ) == "UNKNOWN"


def test_claimed_active_protection_is_inconsistent():
    assert classify_algo_order_evidence(
        {
            "has_payload": True,
            "status": "NEW",
            "has_status": True,
            "has_algo_id": True,
            "protection_active_declared": True,
        }
    ) == "INCONSISTENT"
