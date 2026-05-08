from apps.protection.constants import (
    STATE_PROVISIONAL_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_STALE_PROVISIONAL_PRESENT,
    STATE_TRAILING_READY,
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


def test_equivalent_transition_matrix():
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
    assert decision.current_state == STATE_PROVISIONAL_ACTIVE
    assert (
        decision.next_state
        == STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT
    )


def test_replacement_transition_matrix():
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
    assert decision.current_state == STATE_PROVISIONAL_ACTIVE
    assert (
        decision.next_state
        == STATE_AUTHORITATIVE_REPLACEMENT_PENDING
    )


def test_cleanup_transition_matrix():
    decision = can_start_cleanup(
        current_state=STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        active_protection_verifiable=True,
    )

    assert decision.allowed is True
    assert (
        decision.current_state
        == STATE_AUTHORITATIVE_REPLACEMENT_PENDING
    )

    assert (
        decision.next_state
        == STATE_PROVISIONAL_CLEANUP_PENDING
    )


def test_cleanup_success_transition_matrix():
    decision = evaluate_cleanup_result(
        current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
        cleanup_successful=True,
        stale_provisional_present=False,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        active_protection_verifiable=True,
    )

    assert decision.allowed is True
    assert (
        decision.current_state
        == STATE_PROVISIONAL_CLEANUP_PENDING
    )

    assert decision.next_state == STATE_AUTHORITATIVE_ACTIVE


def test_cleanup_failure_transition_matrix():
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
        decision.current_state
        == STATE_PROVISIONAL_CLEANUP_PENDING
    )

    assert (
        decision.next_state
        == STATE_STALE_PROVISIONAL_PRESENT
    )


def test_retry_cleanup_transition_matrix():
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
        decision.current_state
        == STATE_STALE_PROVISIONAL_PRESENT
    )

    assert (
        decision.next_state
        == STATE_PROVISIONAL_CLEANUP_PENDING
    )


def test_trailing_transition_matrix_from_authoritative():
    decision = can_activate_trailing(
        current_state=STATE_AUTHORITATIVE_ACTIVE,
        baseline_stable=True,
        active_protection_verifiable=True,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        trailing_not_active=True,
    )

    assert decision.allowed is True
    assert decision.current_state == STATE_AUTHORITATIVE_ACTIVE
    assert decision.next_state == STATE_TRAILING_READY


def test_trailing_transition_matrix_from_equivalent():
    decision = can_activate_trailing(
        current_state=STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
        baseline_stable=True,
        active_protection_verifiable=True,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        trailing_not_active=True,
    )

    assert decision.allowed is True

    assert (
        decision.current_state
        == STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT
    )

    assert decision.next_state == STATE_TRAILING_READY
