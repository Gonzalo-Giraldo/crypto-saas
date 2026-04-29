from __future__ import annotations

from typing import Any

from apps.api.app.services.auto_pick.binance.orchestrator import run_binance_auto_pick
from apps.api.app.services.auto_pick.contracts import AutoPickNoTrade, AutoPickResult
from apps.api.app.services.auto_pick.ibkr.orchestrator import run_ibkr_auto_pick


def run_auto_pick(*, broker: str, payload: dict[str, Any] | None = None) -> AutoPickResult:
    """Route Auto-Pick by broker. Fail closed for unsupported or unavailable flows."""
    broker_norm = str(broker or "").upper().strip()

    if broker_norm == "BINANCE":
        return run_binance_auto_pick(payload=payload)

    if broker_norm == "IBKR":
        return run_ibkr_auto_pick(payload=payload)

    return AutoPickNoTrade(
        broker=broker_norm or "UNKNOWN",
        reason="unsupported_broker",
        evidence={"payload_keys": sorted((payload or {}).keys())},
    )
