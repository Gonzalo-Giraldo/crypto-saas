from typing import Any, Dict, Iterable, Optional

from apps.binance_ws.manual_persist_execution_report import (
    persist_manual_execution_report_payload,
)


def process_user_data_messages(
    *,
    db: Any,
    messages: Iterable[Dict],
    user_id: str,
    account_id: str,
    persist_binance_fills_db_callable,
    max_messages: Optional[int] = None,
) -> Dict[str, Any]:

    summary = {
        "received": 0,
        "execution_reports": 0,
        "ignored": 0,
        "processed": 0,
        "not_a_fill": 0,
        "inserted_candidate_count": 0,
        "skipped_existing_count": 0,
        "skipped_duplicate_in_batch_count": 0,
        "skipped_invalid_count": 0,
        "inserted_trade_ids": [],
        "skipped_trade_ids": [],
        "errors": [],
    }

    count = 0

    for msg in messages:
        if max_messages is not None and count >= max_messages:
            break

        summary["received"] += 1
        count += 1

        try:
            event = msg.get("event") or {}

            if event.get("e") != "executionReport":
                summary["ignored"] += 1
                continue

            summary["execution_reports"] += 1

            result = persist_manual_execution_report_payload(
                db=db,
                payload=msg,
                user_id=user_id,
                account_id=account_id,
                persist_binance_fills_db_callable=persist_binance_fills_db_callable,
            )

            if not result.get("processed"):
                summary["not_a_fill"] += 1
                continue

            summary["processed"] += 1

            inner = result.get("result") or {}

            summary["inserted_candidate_count"] += inner.get("inserted_candidate_count", 0)
            summary["skipped_existing_count"] += inner.get("skipped_existing_count", 0)
            summary["skipped_duplicate_in_batch_count"] += inner.get("skipped_duplicate_in_batch_count", 0)
            summary["skipped_invalid_count"] += inner.get("skipped_invalid_count", 0)

            summary["inserted_trade_ids"].extend(inner.get("inserted_trade_ids", []))
            summary["skipped_trade_ids"].extend(inner.get("skipped_trade_ids", []))

        except Exception as e:
            summary["errors"].append(str(e))

    return summary
