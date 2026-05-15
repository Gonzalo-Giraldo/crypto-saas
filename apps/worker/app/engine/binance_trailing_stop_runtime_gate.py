from __future__ import annotations


_REQUIRED_ACTIVE_CLASSIFICATION = "ACTIVE_EVIDENCE_PRESENT"
_REQUIRED_PROTECTION_STATE = "PROTECTED"


def can_run_trailing_stop_replacement(
    *,
    protection_reconciliation: dict | None,
    trailing_decision: dict | None,
    old_sl_client_algo_id: str,
) -> dict:
    old_sl_id = str(old_sl_client_algo_id or "").strip()
    if not old_sl_id:
        return {
            "allowed": False,
            "reason": "old_sl_client_algo_id_required",
        }

    if trailing_decision is None:
        return {
            "allowed": False,
            "reason": "no_trailing_candidate",
        }

    reconciliation = protection_reconciliation or {}

    protection_unknown = reconciliation.get("protection_unknown") is True
    protection_state = str(
        reconciliation.get("protection_state") or ""
    ).upper().strip()

    if protection_unknown or protection_state != _REQUIRED_PROTECTION_STATE:
        return {
            "allowed": False,
            "reason": "protection_not_authoritative",
        }

    sl_classification = str(
        reconciliation.get("sl_classification") or ""
    ).upper().strip()

    if sl_classification != _REQUIRED_ACTIVE_CLASSIFICATION:
        return {
            "allowed": False,
            "reason": "sl_not_authoritative_active",
        }

    return {
        "allowed": True,
        "reason": "trailing_replacement_allowed",
    }
