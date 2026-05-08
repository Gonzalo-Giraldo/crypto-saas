from dataclasses import dataclass


@dataclass(frozen=True)
class ProtectionEvidenceSnapshot:
    current_state: str
    reconciliation_status: str
    safe_for_position_update: bool
    correction_required: bool
    provisional_sl_active: bool
    provisional_tp_active: bool
    authoritative_sl_active: bool
    authoritative_tp_active: bool
    active_protection_verifiable: bool
    replacement_not_started: bool
    cleanup_successful: bool
    stale_provisional_present: bool
    cleanup_retry_allowed: bool
    baseline_stable: bool
    trailing_not_active: bool
