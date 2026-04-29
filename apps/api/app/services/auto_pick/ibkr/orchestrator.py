from __future__ import annotations

from typing import Any

from apps.api.app.services.auto_pick.contracts import AutoPickNoTrade


def run_ibkr_auto_pick(*, payload: dict[str, Any] | None = None) -> AutoPickNoTrade:
    """Fail-closed IBKR Auto-Pick placeholder. IBKR is intentionally not implemented here."""
    return AutoPickNoTrade(
        broker="IBKR",
        reason="ibkr_auto_pick_orchestrator_not_implemented",
        model_version="ibkr_auto_pick_orchestrator_v1",
        evidence={"payload_keys": sorted((payload or {}).keys())},
    )
