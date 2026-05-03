from typing import Any, Callable, Dict

from apps.binance_ws.execution_report_parser import parse_execution_report_event
from apps.binance_ws.binance_fill_ws_persistence import (
    persist_ws_binance_fill_candidates,
)


def persist_manual_execution_report_payload(
    *,
    db: Any,
    payload: Dict[str, Any],
    user_id: str,
    account_id: str,
    persist_binance_fills_db_callable: Callable[..., Any],
) -> Dict[str, Any]:
    """
    Manual-only bridge for one captured Binance executionReport payload.

    This function intentionally does not:
    - create DB engines
    - read environment variables
    - open network connections
    - start listeners
    - loop forever
    - call db.add directly
    - commit directly
    - expose endpoints
    - schedule work
    """
    fill_candidate = parse_execution_report_event(payload)

    if fill_candidate is None:
        return {
            "processed": False,
            "reason": "not_a_fill",
        }

    result = persist_ws_binance_fill_candidates(
        db=db,
        fill_candidates=[fill_candidate],
        user_id=user_id,
        account_id=account_id,
        persist_binance_fills_db_callable=persist_binance_fills_db_callable,
    )

    return {
        "processed": True,
        "reason": "fill_candidate",
        "result": result,
    }
