from __future__ import annotations

from typing import Any


ACTIVE_EVIDENCE_STATUSES = {"NEW", "PENDING_NEW"}
TRIGGERED_OR_FILLED_STATUSES = {"FILLED", "PARTIALLY_FILLED"}
INACTIVE_PROTECTION_STATUSES = {
    "CANCELED",
    "CANCELLED",
    "EXPIRED",
    "EXPIRED_IN_MATCH",
    "REJECTED",
}


def classify_algo_order_evidence(evidence: dict[str, Any] | None) -> str:
    if not isinstance(evidence, dict):
        return "UNKNOWN"

    if evidence.get("protection_active_declared") is True:
        return "INCONSISTENT"

    if evidence.get("has_payload") is not True:
        return "UNKNOWN"

    status = str(evidence.get("status") or "").upper().strip()

    has_status = evidence.get("has_status") is True
    has_identifier = (
        evidence.get("has_algo_id") is True
        or evidence.get("has_client_algo_id") is True
    )

    if not has_status:
        return "UNKNOWN"

    if status in ACTIVE_EVIDENCE_STATUSES:
        if not has_identifier:
            return "INCONSISTENT"
        return "ACTIVE_EVIDENCE_PRESENT"

    if status in TRIGGERED_OR_FILLED_STATUSES:
        return "TRIGGERED_OR_FILLED"

    if status in INACTIVE_PROTECTION_STATUSES:
        return "INACTIVE_PROTECTION"

    return "UNKNOWN"
