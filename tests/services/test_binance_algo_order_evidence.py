from apps.worker.app.engine.binance_algo_order_evidence import (
    extract_algo_order_evidence,
)


def test_extracts_minimal_algo_order_status_evidence():
    evidence = extract_algo_order_evidence(
        {
            "status": "NEW",
            "algoId": 123,
            "clientAlgoId": "cid-sl",
            "executedQty": "0",
        }
    )

    assert evidence["has_payload"] is True
    assert evidence["status"] == "NEW"
    assert evidence["has_status"] is True
    assert evidence["algo_id"] == 123
    assert evidence["has_algo_id"] is True
    assert evidence["client_algo_id"] == "cid-sl"
    assert evidence["has_client_algo_id"] is True
    assert evidence["executed_qty"] == "0"
    assert evidence["has_executed_qty"] is True
    assert evidence["protection_active_declared"] is False


def test_missing_fields_remain_unknown_not_active():
    evidence = extract_algo_order_evidence({})

    assert evidence["has_payload"] is True
    assert evidence["status"] is None
    assert evidence["has_status"] is False
    assert evidence["has_algo_id"] is False
    assert evidence["has_client_algo_id"] is False
    assert evidence["has_executed_qty"] is False
    assert evidence["protection_active_declared"] is False


def test_non_dict_payload_is_not_valid_evidence():
    evidence = extract_algo_order_evidence(None)

    assert evidence["has_payload"] is False
    assert evidence["raw_payload_type"] == "NoneType"
    assert evidence["protection_active_declared"] is False


def test_accepts_alternate_identifier_spellings_without_classifying():
    evidence = extract_algo_order_evidence(
        {
            "status": "filled",
            "algo_id": 456,
            "client_order_id": "ignored",
            "clientOrderId": "cid-tp",
            "cumQty": "0.01",
        }
    )

    assert evidence["status"] == "FILLED"
    assert evidence["algo_id"] == 456
    assert evidence["client_algo_id"] == "cid-tp"
    assert evidence["executed_qty"] == "0.01"
    assert evidence["protection_active_declared"] is False


def test_extract_algo_order_evidence_preserves_stop_price_when_present():
    from apps.worker.app.engine.binance_algo_order_evidence import (
        extract_algo_order_evidence,
    )

    out = extract_algo_order_evidence(
        {
            "status": "NEW",
            "algoId": 123,
            "clientAlgoId": "sl-1",
            "stopPrice": "90000",
        }
    )

    assert out["stop_price"] == "90000"
    assert out["has_stop_price"] is True


def test_extract_algo_order_evidence_marks_missing_stop_price():
    from apps.worker.app.engine.binance_algo_order_evidence import (
        extract_algo_order_evidence,
    )

    out = extract_algo_order_evidence(
        {
            "status": "NEW",
            "algoId": 123,
            "clientAlgoId": "sl-1",
        }
    )

    assert out["stop_price"] is None
    assert out["has_stop_price"] is False
