from apps.api.app.services.runtime_scheduler.runtime_authority_state import (
    RuntimeAuthorityState,
    project_runtime_authority_state,
)


def test_authority_state_active_when_valid():
    projection = project_runtime_authority_state(
        authority_valid=True,
        authority_reason=None,
        advisory_session_reason=None,
    )

    assert projection.state == RuntimeAuthorityState.ACTIVE
    assert projection.valid is True
    assert projection.operator_attention_required is False


def test_authority_state_init_without_ownership():
    projection = project_runtime_authority_state(
        authority_valid=False,
        authority_reason="ownership_row_not_present",
        advisory_session_reason=None,
    )

    assert projection.state == RuntimeAuthorityState.INIT
    assert projection.operator_attention_required is False


def test_authority_state_lost_lock_on_connection_loss():
    projection = project_runtime_authority_state(
        authority_valid=False,
        authority_reason="advisory_session_not_valid",
        advisory_session_reason="advisory_session_connection_lost",
    )

    assert projection.state == RuntimeAuthorityState.LOST_LOCK
    assert projection.reason == "advisory_session_connection_lost"
    assert projection.operator_attention_required is True


def test_authority_state_init_when_advisory_not_acquired():
    projection = project_runtime_authority_state(
        authority_valid=False,
        authority_reason="advisory_session_not_valid",
        advisory_session_reason="advisory_session_not_acquired",
    )

    assert projection.state == RuntimeAuthorityState.INIT
    assert projection.operator_attention_required is False


def test_authority_state_generation_mismatch_requires_attention():
    projection = project_runtime_authority_state(
        authority_valid=False,
        authority_reason="runtime_generation_mismatch",
        advisory_session_reason=None,
    )

    assert projection.state == RuntimeAuthorityState.GENERATION_MISMATCH
    assert projection.operator_attention_required is True


def test_authority_state_stale_requires_attention():
    projection = project_runtime_authority_state(
        authority_valid=False,
        authority_reason="runtime_heartbeat_stale",
        advisory_session_reason=None,
    )

    assert projection.state == RuntimeAuthorityState.STALE
    assert projection.operator_attention_required is True


def test_authority_state_unhealthy_requires_attention():
    projection = project_runtime_authority_state(
        authority_valid=False,
        authority_reason="runtime_health_invalid",
        advisory_session_reason=None,
    )

    assert projection.state == RuntimeAuthorityState.UNHEALTHY
    assert projection.operator_attention_required is True
