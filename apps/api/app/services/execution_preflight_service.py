from __future__ import annotations

from typing import Any


def run_execution_preflight(*, db: Any, intent_id: str) -> dict[str, Any]:
    if not intent_id:
        raise ValueError("intent_id_required")

    from apps.api.app.services.intent_service import get_intent  # local import to avoid coupling

    intent = get_intent(db=db, intent_id=intent_id)

    if intent is None:
        raise ValueError("intent_not_found")

    lifecycle_status = getattr(intent, "lifecycle_status", None)

    if lifecycle_status != "CONSUMED":
        raise ValueError("intent_not_ready_for_execution")

    return {
        "intent_id": intent_id,
        "symbol": getattr(intent, "symbol", None),
        "side": getattr(intent, "side", None),
        "broker": getattr(intent, "broker", None),
        "asset_profile": getattr(intent, "asset_profile", None),
        "lifecycle_status": lifecycle_status,
    }
