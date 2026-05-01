from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from apps.api.app.db.session import SessionLocal


ERROR_ACTIONS = {
    "execution.binance.fill_ingestion.error",
    "execution.binance.fill_backfill.error",
}

COMPLETED_ACTIONS = {
    "execution.binance.fill_ingestion.completed",
    "execution.binance.fill_backfill.completed",
}


def _parse_details(value: Any) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {"raw_details": value}
    return {}


def _is_zero_fill_completed(action: str, details: dict) -> bool:
    if action not in COMPLETED_ACTIONS:
        return False

    matched_count = details.get("matched_count")
    try:
        if matched_count is not None and int(matched_count) == 0:
            return True
    except (TypeError, ValueError):
        pass

    reason = str(details.get("reason") or "").lower()
    return reason in {
        "no_matching_trades",
        "reconciliation_blocked:no_fills_matched_execution_ref",
    }


def get_binance_fill_ingestion_health(*, lookback_minutes: int = 60, limit: int = 200) -> dict:
    db = SessionLocal()
    try:
        rows = db.execute(
            text("""
                SELECT action, user_id, details, created_at
                FROM audit_log
                WHERE action IN (
                    'execution.binance.fill_ingestion.completed',
                    'execution.binance.fill_ingestion.error',
                    'execution.binance.fill_backfill.completed',
                    'execution.binance.fill_backfill.error'
                )
                  AND created_at >= (NOW() - (:lookback_minutes || ' minutes')::interval)
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {
                "lookback_minutes": int(lookback_minutes),
                "limit": int(limit),
            },
        ).fetchall()

        total = 0
        completed = 0
        errors = 0
        zero_fills = 0
        latest_error = None
        latest_zero_fill = None

        for row in rows:
            total += 1
            action = str(row.action)
            details = _parse_details(row.details)

            if action in ERROR_ACTIONS:
                errors += 1
                if latest_error is None:
                    latest_error = {
                        "action": action,
                        "user_id": str(row.user_id) if row.user_id is not None else None,
                        "details": details,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }

            if action in COMPLETED_ACTIONS:
                completed += 1
                if _is_zero_fill_completed(action, details):
                    zero_fills += 1
                    if latest_zero_fill is None:
                        latest_zero_fill = {
                            "action": action,
                            "user_id": str(row.user_id) if row.user_id is not None else None,
                            "details": details,
                            "created_at": row.created_at.isoformat() if row.created_at else None,
                        }

        alerts = []
        if errors > 0:
            alerts.append("binance_fill_ingestion_errors_detected")
        if zero_fills > 0:
            alerts.append("binance_fill_ingestion_zero_fills_detected")

        if errors > 0:
            status = "BROKEN"
        elif zero_fills > 0:
            status = "DEGRADED"
        else:
            status = "OK"

        return {
            "status": status,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "lookback_minutes": int(lookback_minutes),
            "total_events": total,
            "completed_events": completed,
            "error_events": errors,
            "zero_fill_completed_events": zero_fills,
            "alerts": alerts,
            "latest_error": latest_error,
            "latest_zero_fill": latest_zero_fill,
        }
    finally:
        db.close()
