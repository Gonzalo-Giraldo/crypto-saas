from apps.protection.constants import (
    STATE_PROVISIONAL_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_STALE_PROVISIONAL_PRESENT,
    STATE_TRAILING_READY,
    REASON_PROTECTION_NOT_VERIFIABLE,
)

from apps.protection.equivalent_evaluator import (
    can_accept_authoritative_equivalent,
)

from apps.protection.replacement_evaluator import (
    can_start_authoritative_replacement,
)

from apps.protection.cleanup_evaluator import (
    can_start_cleanup,
)

from apps.protection.cleanup_result_evaluator import (
    evaluate_cleanup_result,
)

from apps.protection.retry_cleanup_evaluator import (
    can_retry_cleanup,
)

from apps.protection.trailing_evaluator import (
    can_activate_trailing,
)


def test_equivalent_path_is_isolated_from_replacement():
    decision = can_accept_authoritative_equivalent(
        current_state=STATE_PROVISIONAL_ACTIVE,
        reconciliation_status="matched",
        safe_for_position_update=True,
        correction_required=False,
        provisional_sl_active=True,
        provisional_tp_active=True,
        active_protection_verifiable=True,
        replacement_not_started=True,
    )

    assert decision.allowed is True

    assert (
        decision.next_state
        == STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT
    )

    assert (
        decision.next_state
        != STATE_AUTHORITATIVE_REPLACEMENT_PENDING
    )


def test_replacement_path_never_enters_equivalent_state():
    decision = can_start_authoritative_replacement(
        current_state=STATE_PROVISIONAL_ACTIVE,
        reconciliation_status="matched",
        safe_for_position_update=True,
        correction_required=True,
        provisional_sl_active=True,
        provisional_tp_active=True,
        active_protection_verifiable=True,
        replacement_not_started=True,
    )

    assert decision.allowed is True

    assert (
        decision.next_state
        == STATE_AUTHORITATIVE_REPLACEMENT_PENDING
    )

    assert (
        decision.next_state
        != STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT
    )


def test_cleanup_failure_does_not_destroy_authoritative_protection():
    decision = evaluate_cleanup_result(
        current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
        cleanup_successful=False,
        stale_provisional_present=True,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        active_protection_verifiable=True,
    )

    assert decision.allowed is True

    assert (
        decision.next_state
        == STATE_STALE_PROVISIONAL_PRESENT
    )


def test_retry_cleanup_never_recreates_authoritative_replacement():
    decision = can_retry_cleanup(
        current_state=STATE_STALE_PROVISIONAL_PRESENT,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        active_protection_verifiable=True,
        stale_provisional_present=True,
        cleanup_retry_allowed=True,
    )

    assert decision.allowed is True

    assert (
        decision.next_state
        == STATE_PROVISIONAL_CLEANUP_PENDING
    )

    assert (
        decision.next_state
        != STATE_AUTHORITATIVE_REPLACEMENT_PENDING
    )


def test_trailing_requires_stable_authoritative_baseline():
    decision = can_activate_trailing(
        current_state=STATE_AUTHORITATIVE_ACTIVE,
        baseline_stable=False,
        active_protection_verifiable=True,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        trailing_not_active=True,
    )

    assert decision.allowed is False


def test_never_unprotected_during_cleanup_transition():
    decision = can_start_cleanup(
        current_state=STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
        authoritative_sl_active=False,
        authoritative_tp_active=True,
        active_protection_verifiable=True,
    )

    assert decision.allowed is False

    assert (
        decision.reason
        == REASON_PROTECTION_NOT_VERIFIABLE
    )


def test_never_unprotected_during_retry_transition():
    decision = can_retry_cleanup(
        current_state=STATE_STALE_PROVISIONAL_PRESENT,
        authoritative_sl_active=True,
        authoritative_tp_active=False,
        active_protection_verifiable=True,
        stale_provisional_present=True,
        cleanup_retry_allowed=True,
    )

    assert decision.allowed is False

    assert (
        decision.reason
        == REASON_PROTECTION_NOT_VERIFIABLE
    )


def test_never_unprotected_during_trailing_transition():
    decision = can_activate_trailing(
        current_state=STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
        baseline_stable=True,
        active_protection_verifiable=False,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        trailing_not_active=True,
    )

    assert decision.allowed is False

    assert (
        decision.reason
        == REASON_PROTECTION_NOT_VERIFIABLE
    )


def test_trailing_ready_has_no_outbound_transition():
    forbidden_states = {
        STATE_PROVISIONAL_ACTIVE,
        STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
        STATE_PROVISIONAL_CLEANUP_PENDING,
        STATE_STALE_PROVISIONAL_PRESENT,
        STATE_AUTHORITATIVE_ACTIVE,
        STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    }

    assert STATE_TRAILING_READY not in forbidden_states
