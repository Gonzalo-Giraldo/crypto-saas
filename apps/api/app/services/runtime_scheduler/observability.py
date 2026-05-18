from __future__ import annotations

from datetime import datetime


def build_tick_details(*, monitor, out, exit_out, shadow_out):
    return {
        "monitor_inserted": monitor.get("inserted", 0),
        "executed_count": out.get("executed_count", 0),
        "dry_run": out.get("dry_run", True),
        "top_n": out.get("top_n", 10),
        "exit_scanned_positions": exit_out.get("scanned_positions", 0),
        "exit_candidates": exit_out.get("exit_candidates", 0),
        "exit_closed_positions": exit_out.get("closed_positions", 0),
        "exit_skipped_no_price": exit_out.get("skipped_no_price", 0),
        "exit_skipped_by_policy": exit_out.get("skipped_by_policy", 0),
        "exit_errors": exit_out.get("errors", 0),
        "exit_paused": exit_out.get("paused", False),
        "exit_dry_run": exit_out.get("dry_run", True),
        "shadow_status": (shadow_out or {}).get("status"),
        "shadow_symbol": (shadow_out or {}).get("symbol"),
        "shadow_persisted": (shadow_out or {}).get("persisted"),
        "shadow_executed": (shadow_out or {}).get("executed"),
    }


def build_common_journal_payload(
    *,
    started_at: datetime,
    finished_at,
    duration_ms: int,
    dry_run: bool,
    trading_enabled: bool,
    execution_mode: str,
) -> dict:
    return {
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "dry_run": dry_run,
        "trading_enabled": trading_enabled,
        "execution_mode": execution_mode,
        "mutation_attempted": False,
        "mutation_executed": False,
    }
