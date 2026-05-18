from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
    evaluate_runtime_advisory_session,
)
from apps.api.app.services.runtime_scheduler.runtime_authority_coordinator import (
    RuntimeAuthorityCoordinatorInput,
    evaluate_runtime_authority,
)


def _valid_input() -> RuntimeAuthorityCoordinatorInput:
    return RuntimeAuthorityCoordinatorInput(
        ownership_row_present=True,
        local_identity_matches=True,
        generation_matches=True,
        heartbeat_fresh=True,
        runtime_health_valid=True,
        advisory_session_state=evaluate_runtime_advisory_session(
            acquired=True,
            connection_alive=True,
            lock_still_held=True,
        ),
    )


def test_runtime_authority_coordinator_valid_when_all_evidence_agrees():
    result = evaluate_runtime_authority(
        authority_input=_valid_input(),
    )

    assert result.valid is True
    assert result.reason is None
    assert result.evidence.advisory_session_valid is True
    assert result.advisory_session_reason is None


def test_runtime_authority_coordinator_fails_closed_without_ownership():
    authority_input = _valid_input()
    result = evaluate_runtime_authority(
        authority_input=RuntimeAuthorityCoordinatorInput(
            ownership_row_present=False,
            local_identity_matches=authority_input.local_identity_matches,
            generation_matches=authority_input.generation_matches,
            heartbeat_fresh=authority_input.heartbeat_fresh,
            runtime_health_valid=authority_input.runtime_health_valid,
            advisory_session_state=authority_input.advisory_session_state,
        ),
    )

    assert result.valid is False
    assert result.reason == "ownership_row_not_present"


def test_runtime_authority_coordinator_fails_closed_without_advisory_session():
    authority_input = _valid_input()
    advisory_state = evaluate_runtime_advisory_session(
        acquired=False,
        connection_alive=False,
        lock_still_held=False,
    )

    result = evaluate_runtime_authority(
        authority_input=RuntimeAuthorityCoordinatorInput(
            ownership_row_present=authority_input.ownership_row_present,
            local_identity_matches=authority_input.local_identity_matches,
            generation_matches=authority_input.generation_matches,
            heartbeat_fresh=authority_input.heartbeat_fresh,
            runtime_health_valid=authority_input.runtime_health_valid,
            advisory_session_state=advisory_state,
        ),
    )

    assert result.valid is False
    assert result.reason == "advisory_session_not_valid"
    assert result.advisory_session_reason == "advisory_session_not_acquired"


def test_runtime_authority_coordinator_fails_closed_on_identity_mismatch():
    authority_input = _valid_input()
    result = evaluate_runtime_authority(
        authority_input=RuntimeAuthorityCoordinatorInput(
            ownership_row_present=authority_input.ownership_row_present,
            local_identity_matches=False,
            generation_matches=authority_input.generation_matches,
            heartbeat_fresh=authority_input.heartbeat_fresh,
            runtime_health_valid=authority_input.runtime_health_valid,
            advisory_session_state=authority_input.advisory_session_state,
        ),
    )

    assert result.valid is False
    assert result.reason == "local_identity_mismatch"


def test_runtime_authority_coordinator_fails_closed_on_generation_mismatch():
    authority_input = _valid_input()
    result = evaluate_runtime_authority(
        authority_input=RuntimeAuthorityCoordinatorInput(
            ownership_row_present=authority_input.ownership_row_present,
            local_identity_matches=authority_input.local_identity_matches,
            generation_matches=False,
            heartbeat_fresh=authority_input.heartbeat_fresh,
            runtime_health_valid=authority_input.runtime_health_valid,
            advisory_session_state=authority_input.advisory_session_state,
        ),
    )

    assert result.valid is False
    assert result.reason == "runtime_generation_mismatch"


def test_runtime_authority_coordinator_fails_closed_on_stale_heartbeat():
    authority_input = _valid_input()
    result = evaluate_runtime_authority(
        authority_input=RuntimeAuthorityCoordinatorInput(
            ownership_row_present=authority_input.ownership_row_present,
            local_identity_matches=authority_input.local_identity_matches,
            generation_matches=authority_input.generation_matches,
            heartbeat_fresh=False,
            runtime_health_valid=authority_input.runtime_health_valid,
            advisory_session_state=authority_input.advisory_session_state,
        ),
    )

    assert result.valid is False
    assert result.reason == "runtime_heartbeat_stale"


def test_runtime_authority_coordinator_fails_closed_on_invalid_runtime_health():
    authority_input = _valid_input()
    result = evaluate_runtime_authority(
        authority_input=RuntimeAuthorityCoordinatorInput(
            ownership_row_present=authority_input.ownership_row_present,
            local_identity_matches=authority_input.local_identity_matches,
            generation_matches=authority_input.generation_matches,
            heartbeat_fresh=authority_input.heartbeat_fresh,
            runtime_health_valid=False,
            advisory_session_state=authority_input.advisory_session_state,
        ),
    )

    assert result.valid is False
    assert result.reason == "runtime_health_invalid"
