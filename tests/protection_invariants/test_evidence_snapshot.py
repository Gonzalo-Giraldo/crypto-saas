from dataclasses import FrozenInstanceError

import pytest

from apps.protection.constants import (
    STATE_PROVISIONAL_ACTIVE,
)

from apps.protection.evidence_snapshot import (
    ProtectionEvidenceSnapshot,
)


def test_protection_evidence_snapshot_is_pure_data():
    snapshot = ProtectionEvidenceSnapshot(
        current_state=STATE_PROVISIONAL_ACTIVE,
        reconciliation_status="matched",
        safe_for_position_update=True,
        correction_required=False,
        provisional_sl_active=True,
        provisional_tp_active=True,
        authoritative_sl_active=False,
        authoritative_tp_active=False,
        active_protection_verifiable=True,
        replacement_not_started=True,
        cleanup_successful=False,
        stale_provisional_present=False,
        cleanup_retry_allowed=False,
        baseline_stable=False,
        trailing_not_active=True,
    )

    assert snapshot.current_state == STATE_PROVISIONAL_ACTIVE
    assert snapshot.reconciliation_status == "matched"
    assert snapshot.safe_for_position_update is True
    assert snapshot.correction_required is False
    assert snapshot.provisional_sl_active is True
    assert snapshot.provisional_tp_active is True
    assert snapshot.authoritative_sl_active is False
    assert snapshot.authoritative_tp_active is False
    assert snapshot.active_protection_verifiable is True
    assert snapshot.replacement_not_started is True
    assert snapshot.cleanup_successful is False
    assert snapshot.stale_provisional_present is False
    assert snapshot.cleanup_retry_allowed is False
    assert snapshot.baseline_stable is False
    assert snapshot.trailing_not_active is True


def test_protection_evidence_snapshot_is_immutable():
    snapshot = ProtectionEvidenceSnapshot(
        current_state=STATE_PROVISIONAL_ACTIVE,
        reconciliation_status="matched",
        safe_for_position_update=True,
        correction_required=False,
        provisional_sl_active=True,
        provisional_tp_active=True,
        authoritative_sl_active=False,
        authoritative_tp_active=False,
        active_protection_verifiable=True,
        replacement_not_started=True,
        cleanup_successful=False,
        stale_provisional_present=False,
        cleanup_retry_allowed=False,
        baseline_stable=False,
        trailing_not_active=True,
    )

    with pytest.raises(FrozenInstanceError):
        snapshot.current_state = "MUTATED"


def test_protection_evidence_snapshot_has_no_behavior_methods():
    behavior_methods = {
        name
        for name in dir(ProtectionEvidenceSnapshot)
        if not name.startswith("__")
        and callable(getattr(ProtectionEvidenceSnapshot, name))
    }

    assert behavior_methods == set()
