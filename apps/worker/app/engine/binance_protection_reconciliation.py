from __future__ import annotations

from typing import Any


_ACTIVE = "ACTIVE_EVIDENCE_PRESENT"
_TRIGGERED = "TRIGGERED_OR_FILLED"
_INACTIVE = "INACTIVE_PROTECTION"
_UNKNOWN = {"UNKNOWN", "INCONSISTENT"}


def reconcile_exit_protection_state(
    *,
    sl_classification: str,
    tp_classification: str,
    sl_fetch_status: str,
    tp_fetch_status: str,
) -> dict[str, Any]:
    sl_cls = str(sl_classification or "").upper().strip()
    tp_cls = str(tp_classification or "").upper().strip()
    sl_status = str(sl_fetch_status or "").upper().strip()
    tp_status = str(tp_fetch_status or "").upper().strip()

    fetch_ok = sl_status == "OK" and tp_status == "OK"

    if not fetch_ok:
        protection_state = "PROTECTION_UNKNOWN"
    elif sl_cls in _UNKNOWN or tp_cls in _UNKNOWN:
        protection_state = "PROTECTION_UNKNOWN"
    elif sl_cls == _TRIGGERED or tp_cls == _TRIGGERED:
        protection_state = "TRIGGERED"
    elif sl_cls == _ACTIVE and tp_cls == _ACTIVE:
        protection_state = "PROTECTED"
    elif sl_cls == _ACTIVE or tp_cls == _ACTIVE:
        protection_state = "PARTIALLY_PROTECTED"
    elif sl_cls == _INACTIVE and tp_cls == _INACTIVE:
        protection_state = "EXPIRED"
    else:
        protection_state = "UNPROTECTED"

    return {
        "protection_state": protection_state,
        "sl_classification": sl_cls,
        "tp_classification": tp_cls,
        "sl_fetch_status": sl_status,
        "tp_fetch_status": tp_status,
        "protection_active_verifiable": protection_state == "PROTECTED",
        "protection_triggered": protection_state == "TRIGGERED",
        "protection_unknown": protection_state == "PROTECTION_UNKNOWN",
    }
