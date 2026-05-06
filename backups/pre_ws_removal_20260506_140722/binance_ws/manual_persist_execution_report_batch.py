from typing import Any, Callable, Dict, List

from apps.binance_ws.manual_persist_execution_report import (
    persist_manual_execution_report_payload,
)


def _empty_summary(received: int) -> Dict[str, Any]:
    return {
        "received": received,
        "processed": 0,
        "not_a_fill": 0,
        "inserted_candidate_count": 0,
        "skipped_existing_count": 0,
        "skipped_duplicate_in_batch_count": 0,
        "skipped_invalid_count": 0,
        "inserted_trade_ids": [],
        "skipped_trade_ids": [],
        "results": [],
    }


def persist_manual_execution_report_payloads(
    *,
    db: Any,
    payloads: List[Dict[str, Any]],
    user_id: str,
    account_id: str,
    persist_binance_fills_db_callable: Callable[..., Any],
) -> Dict[str, Any]:
    """
    Manual-only finite batch bridge for captured Binance executionReport payloads.

    This function intentionally does not:
    - create DB engines
    - read environment variables
    - open network connections
    - start listeners
    - expose endpoints
    - schedule work
    - call  directly
    - commit directly
    """
    received = len(payloads or [])
    summary = _empty_summary(received)

    if not payloads:
        return summary

    seen_inserted_trade_ids = set()

    for payload in payloads:
        result = persist_manual_execution_report_payload(
            db=db,
            payload=payload,
            user_id=user_id,
            account_id=account_id,
            persist_binance_fills_db_callable=persist_binance_fills_db_callable,
        )

        summary["results"].append(result)

        if not result.get("processed"):
            if result.get("reason") == "not_a_fill":
                summary["not_a_fill"] += 1
            continue

        summary["processed"] += 1

        inner = result.get("result") or {}

        summary["inserted_candidate_count"] += int(
            inner.get("inserted_candidate_count") or 0
        )
        summary["skipped_existing_count"] += int(
            inner.get("skipped_existing_count") or 0
        )
        summary["skipped_duplicate_in_batch_count"] += int(
            inner.get("skipped_duplicate_in_batch_count") or 0
        )
        summary["skipped_invalid_count"] += int(
            inner.get("skipped_invalid_count") or 0
        )

        for trade_id in inner.get("inserted_trade_ids") or []:
            if trade_id in seen_inserted_trade_ids:
                summary["skipped_duplicate_in_batch_count"] += 1
                summary["inserted_candidate_count"] -= 1
                if summary["inserted_candidate_count"] < 0:
                    summary["inserted_candidate_count"] = 0
                continue
            seen_inserted_trade_ids.add(trade_id)
            summary["inserted_trade_ids"].append(trade_id)

        summary["skipped_trade_ids"].extend(inner.get("skipped_trade_ids") or [])

    return summary
