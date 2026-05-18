from apps.api.app.services.runtime_scheduler.runtime_session_authority import (
    RuntimeSessionAuthorityEvidence,
    evaluate_runtime_session_authority,
)


def _valid_evidence() -> RuntimeSessionAuthorityEvidence:
    return RuntimeSessionAuthorityEvidence(
        ownership_row_present=True,
        advisory_session_valid=True,
        local_identity_matches=True,
        generation_matches=True,
        heartbeat_fresh=True,
        runtime_health_valid=True,
    )


def test_runtime_session_authority_valid_when_all_evidence_agrees():
    decision = evaluate_runtime_session_authority(
        evidence=_valid_evidence(),
    )

    assert decision.valid is True
    assert decision.reason is None


def test_runtime_session_authority_fails_closed_without_ownership_row():
    evidence = _valid_evidence()
    evidence = RuntimeSessionAuthorityEvidence(
        ownership_row_present=False,
        advisory_session_valid=evidence.advisory_session_valid,
        local_identity_matches=evidence.local_identity_matches,
        generation_matches=evidence.generation_matches,
        heartbeat_fresh=evidence.heartbeat_fresh,
        runtime_health_valid=evidence.runtime_health_valid,
    )

    decision = evaluate_runtime_session_authority(evidence=evidence)

    assert decision.valid is False
    assert decision.reason == "ownership_row_not_present"


def test_runtime_session_authority_fails_closed_without_advisory_session():
    evidence = _valid_evidence()
    evidence = RuntimeSessionAuthorityEvidence(
        ownership_row_present=evidence.ownership_row_present,
        advisory_session_valid=False,
        local_identity_matches=evidence.local_identity_matches,
        generation_matches=evidence.generation_matches,
        heartbeat_fresh=evidence.heartbeat_fresh,
        runtime_health_valid=evidence.runtime_health_valid,
    )

    decision = evaluate_runtime_session_authority(evidence=evidence)

    assert decision.valid is False
    assert decision.reason == "advisory_session_not_valid"


def test_runtime_session_authority_fails_closed_on_local_identity_mismatch():
    evidence = _valid_evidence()
    evidence = RuntimeSessionAuthorityEvidence(
        ownership_row_present=evidence.ownership_row_present,
        advisory_session_valid=evidence.advisory_session_valid,
        local_identity_matches=False,
        generation_matches=evidence.generation_matches,
        heartbeat_fresh=evidence.heartbeat_fresh,
        runtime_health_valid=evidence.runtime_health_valid,
    )

    decision = evaluate_runtime_session_authority(evidence=evidence)

    assert decision.valid is False
    assert decision.reason == "local_identity_mismatch"


def test_runtime_session_authority_fails_closed_on_generation_mismatch():
    evidence = _valid_evidence()
    evidence = RuntimeSessionAuthorityEvidence(
        ownership_row_present=evidence.ownership_row_present,
        advisory_session_valid=evidence.advisory_session_valid,
        local_identity_matches=evidence.local_identity_matches,
        generation_matches=False,
        heartbeat_fresh=evidence.heartbeat_fresh,
        runtime_health_valid=evidence.runtime_health_valid,
    )

    decision = evaluate_runtime_session_authority(evidence=evidence)

    assert decision.valid is False
    assert decision.reason == "runtime_generation_mismatch"


def test_runtime_session_authority_fails_closed_on_stale_heartbeat():
    evidence = _valid_evidence()
    evidence = RuntimeSessionAuthorityEvidence(
        ownership_row_present=evidence.ownership_row_present,
        advisory_session_valid=evidence.advisory_session_valid,
        local_identity_matches=evidence.local_identity_matches,
        generation_matches=evidence.generation_matches,
        heartbeat_fresh=False,
        runtime_health_valid=evidence.runtime_health_valid,
    )

    decision = evaluate_runtime_session_authority(evidence=evidence)

    assert decision.valid is False
    assert decision.reason == "runtime_heartbeat_stale"


def test_runtime_session_authority_fails_closed_on_invalid_runtime_health():
    evidence = _valid_evidence()
    evidence = RuntimeSessionAuthorityEvidence(
        ownership_row_present=evidence.ownership_row_present,
        advisory_session_valid=evidence.advisory_session_valid,
        local_identity_matches=evidence.local_identity_matches,
        generation_matches=evidence.generation_matches,
        heartbeat_fresh=evidence.heartbeat_fresh,
        runtime_health_valid=False,
    )

    decision = evaluate_runtime_session_authority(evidence=evidence)

    assert decision.valid is False
    assert decision.reason == "runtime_health_invalid"
