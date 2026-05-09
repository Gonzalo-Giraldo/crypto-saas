from app.protection.execution_resolution_authority import (
    ExecutionResolution,
    ExecutionResolutionAuthorityDecision,
    ExecutionResolutionAuthorityEvidence,
    ExecutionResolutionAuthorityPolicy,
    ResolutionAuthority,
    ResolutionAuthorityReason,
    ResolutionPriority,
    evaluate_execution_resolution_authority,
)


def _priority_table():
    return frozenset(
        {
            ResolutionPriority(ExecutionResolution.NOOP, 100),
            ResolutionPriority(ExecutionResolution.RECORD_AUDIT_ONLY, 90),
            ResolutionPriority(ExecutionResolution.KEEP_PROVISIONAL, 80),
            ResolutionPriority(ExecutionResolution.CREATE_AUTHORITATIVE, 10),
            ResolutionPriority(ExecutionResolution.REPLACE_AUTHORITATIVE, 20),
            ResolutionPriority(ExecutionResolution.CLEANUP_PROVISIONAL, 30),
            ResolutionPriority(ExecutionResolution.ACTIVATE_TRAILING, 40),
        }
    )


def test_denies_when_convergence_semantics_not_allowed():
    decision = evaluate_execution_resolution_authority(
        convergence_semantics_allowed=False,
        policy=ExecutionResolutionAuthorityPolicy(
            required_authorities=frozenset(),
            granted_authorities=frozenset(),
            allowed_resolutions=frozenset({ExecutionResolution.NOOP}),
            forbidden_resolutions=frozenset(),
            priority_table=_priority_table(),
            final_resolutions=frozenset(),
            locked_resolutions=frozenset(),
        ),
        evidence=ExecutionResolutionAuthorityEvidence(
            candidate_resolutions=frozenset({ExecutionResolution.NOOP}),
            requested_resolution=ExecutionResolution.NOOP,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ResolutionAuthorityReason.CONVERGENCE_SEMANTICS_NOT_ALLOWED


def test_denies_missing_required_authority():
    decision = evaluate_execution_resolution_authority(
        convergence_semantics_allowed=True,
        policy=ExecutionResolutionAuthorityPolicy(
            required_authorities=frozenset({ResolutionAuthority.REPLACEMENT_AUTHORITY}),
            granted_authorities=frozenset(),
            allowed_resolutions=frozenset({ExecutionResolution.REPLACE_AUTHORITATIVE}),
            forbidden_resolutions=frozenset(),
            priority_table=_priority_table(),
            final_resolutions=frozenset(),
            locked_resolutions=frozenset(),
        ),
        evidence=ExecutionResolutionAuthorityEvidence(
            candidate_resolutions=frozenset({ExecutionResolution.REPLACE_AUTHORITATIVE}),
            requested_resolution=ExecutionResolution.REPLACE_AUTHORITATIVE,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ResolutionAuthorityReason.MISSING_REQUIRED_AUTHORITY
    assert decision.missing_authorities == (ResolutionAuthority.REPLACEMENT_AUTHORITY,)


def test_denies_forbidden_resolution():
    decision = evaluate_execution_resolution_authority(
        convergence_semantics_allowed=True,
        policy=ExecutionResolutionAuthorityPolicy(
            required_authorities=frozenset(),
            granted_authorities=frozenset(),
            allowed_resolutions=frozenset({ExecutionResolution.CLEANUP_PROVISIONAL}),
            forbidden_resolutions=frozenset({ExecutionResolution.CLEANUP_PROVISIONAL}),
            priority_table=_priority_table(),
            final_resolutions=frozenset(),
            locked_resolutions=frozenset(),
        ),
        evidence=ExecutionResolutionAuthorityEvidence(
            candidate_resolutions=frozenset({ExecutionResolution.CLEANUP_PROVISIONAL}),
            requested_resolution=ExecutionResolution.CLEANUP_PROVISIONAL,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ResolutionAuthorityReason.FORBIDDEN_RESOLUTION
    assert decision.forbidden_resolutions == (ExecutionResolution.CLEANUP_PROVISIONAL,)


def test_denies_unknown_resolution_priority():
    decision = evaluate_execution_resolution_authority(
        convergence_semantics_allowed=True,
        policy=ExecutionResolutionAuthorityPolicy(
            required_authorities=frozenset(),
            granted_authorities=frozenset(),
            allowed_resolutions=frozenset({ExecutionResolution.NOOP}),
            forbidden_resolutions=frozenset(),
            priority_table=frozenset(),
            final_resolutions=frozenset(),
            locked_resolutions=frozenset(),
        ),
        evidence=ExecutionResolutionAuthorityEvidence(
            candidate_resolutions=frozenset({ExecutionResolution.NOOP}),
            requested_resolution=ExecutionResolution.NOOP,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ResolutionAuthorityReason.UNKNOWN_RESOLUTION_PRIORITY


def test_denies_same_priority_competing_resolutions():
    priority_table = frozenset(
        {
            ResolutionPriority(ExecutionResolution.CREATE_AUTHORITATIVE, 10),
            ResolutionPriority(ExecutionResolution.REPLACE_AUTHORITATIVE, 10),
        }
    )

    decision = evaluate_execution_resolution_authority(
        convergence_semantics_allowed=True,
        policy=ExecutionResolutionAuthorityPolicy(
            required_authorities=frozenset(),
            granted_authorities=frozenset(),
            allowed_resolutions=frozenset(
                {
                    ExecutionResolution.CREATE_AUTHORITATIVE,
                    ExecutionResolution.REPLACE_AUTHORITATIVE,
                }
            ),
            forbidden_resolutions=frozenset(),
            priority_table=priority_table,
            final_resolutions=frozenset(),
            locked_resolutions=frozenset(),
            requires_single_winner=True,
        ),
        evidence=ExecutionResolutionAuthorityEvidence(
            candidate_resolutions=frozenset(
                {
                    ExecutionResolution.CREATE_AUTHORITATIVE,
                    ExecutionResolution.REPLACE_AUTHORITATIVE,
                }
            ),
            requested_resolution=ExecutionResolution.CREATE_AUTHORITATIVE,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ResolutionAuthorityReason.COMPETING_RESOLUTION
    assert decision.competing_resolutions == (
        ExecutionResolution.CREATE_AUTHORITATIVE,
        ExecutionResolution.REPLACE_AUTHORITATIVE,
    )


def test_denies_requested_resolution_that_is_not_selected_winner():
    decision = evaluate_execution_resolution_authority(
        convergence_semantics_allowed=True,
        policy=ExecutionResolutionAuthorityPolicy(
            required_authorities=frozenset(),
            granted_authorities=frozenset(),
            allowed_resolutions=frozenset(
                {
                    ExecutionResolution.CREATE_AUTHORITATIVE,
                    ExecutionResolution.KEEP_PROVISIONAL,
                }
            ),
            forbidden_resolutions=frozenset(),
            priority_table=_priority_table(),
            final_resolutions=frozenset(),
            locked_resolutions=frozenset(),
        ),
        evidence=ExecutionResolutionAuthorityEvidence(
            candidate_resolutions=frozenset(
                {
                    ExecutionResolution.CREATE_AUTHORITATIVE,
                    ExecutionResolution.KEEP_PROVISIONAL,
                }
            ),
            requested_resolution=ExecutionResolution.KEEP_PROVISIONAL,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ResolutionAuthorityReason.COMPETING_RESOLUTION
    assert decision.selected_resolution == ExecutionResolution.CREATE_AUTHORITATIVE


def test_denies_finality_violation():
    decision = evaluate_execution_resolution_authority(
        convergence_semantics_allowed=True,
        policy=ExecutionResolutionAuthorityPolicy(
            required_authorities=frozenset(),
            granted_authorities=frozenset(),
            allowed_resolutions=frozenset(
                {
                    ExecutionResolution.CREATE_AUTHORITATIVE,
                    ExecutionResolution.REPLACE_AUTHORITATIVE,
                }
            ),
            forbidden_resolutions=frozenset(),
            priority_table=_priority_table(),
            final_resolutions=frozenset({ExecutionResolution.REPLACE_AUTHORITATIVE}),
            locked_resolutions=frozenset(),
        ),
        evidence=ExecutionResolutionAuthorityEvidence(
            candidate_resolutions=frozenset(
                {
                    ExecutionResolution.CREATE_AUTHORITATIVE,
                    ExecutionResolution.REPLACE_AUTHORITATIVE,
                }
            ),
            requested_resolution=ExecutionResolution.CREATE_AUTHORITATIVE,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ResolutionAuthorityReason.FINALITY_VIOLATION
    assert decision.finality_violations == (ExecutionResolution.REPLACE_AUTHORITATIVE,)


def test_denies_locked_resolution_violation():
    decision = evaluate_execution_resolution_authority(
        convergence_semantics_allowed=True,
        policy=ExecutionResolutionAuthorityPolicy(
            required_authorities=frozenset(),
            granted_authorities=frozenset(),
            allowed_resolutions=frozenset(
                {
                    ExecutionResolution.CREATE_AUTHORITATIVE,
                    ExecutionResolution.CLEANUP_PROVISIONAL,
                }
            ),
            forbidden_resolutions=frozenset(),
            priority_table=_priority_table(),
            final_resolutions=frozenset(),
            locked_resolutions=frozenset({ExecutionResolution.CLEANUP_PROVISIONAL}),
        ),
        evidence=ExecutionResolutionAuthorityEvidence(
            candidate_resolutions=frozenset(
                {
                    ExecutionResolution.CREATE_AUTHORITATIVE,
                    ExecutionResolution.CLEANUP_PROVISIONAL,
                }
            ),
            requested_resolution=ExecutionResolution.CREATE_AUTHORITATIVE,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ResolutionAuthorityReason.LOCKED_RESOLUTION_VIOLATION
    assert decision.locked_resolution_violations == (
        ExecutionResolution.CLEANUP_PROVISIONAL,
    )


def test_denies_when_protection_continuity_not_proven():
    decision = evaluate_execution_resolution_authority(
        convergence_semantics_allowed=True,
        policy=ExecutionResolutionAuthorityPolicy(
            required_authorities=frozenset(),
            granted_authorities=frozenset(),
            allowed_resolutions=frozenset({ExecutionResolution.RECORD_AUDIT_ONLY}),
            forbidden_resolutions=frozenset(),
            priority_table=_priority_table(),
            final_resolutions=frozenset(),
            locked_resolutions=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=ExecutionResolutionAuthorityEvidence(
            candidate_resolutions=frozenset({ExecutionResolution.RECORD_AUDIT_ONLY}),
            requested_resolution=ExecutionResolution.RECORD_AUDIT_ONLY,
            protection_continuity_proven=False,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ResolutionAuthorityReason.PROTECTION_CONTINUITY_REQUIRED


def test_authorizes_selected_resolution_when_policy_is_satisfied():
    decision = evaluate_execution_resolution_authority(
        convergence_semantics_allowed=True,
        policy=ExecutionResolutionAuthorityPolicy(
            required_authorities=frozenset({ResolutionAuthority.REPLACEMENT_AUTHORITY}),
            granted_authorities=frozenset({ResolutionAuthority.REPLACEMENT_AUTHORITY}),
            allowed_resolutions=frozenset({ExecutionResolution.REPLACE_AUTHORITATIVE}),
            forbidden_resolutions=frozenset(),
            priority_table=_priority_table(),
            final_resolutions=frozenset({ExecutionResolution.REPLACE_AUTHORITATIVE}),
            locked_resolutions=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=ExecutionResolutionAuthorityEvidence(
            candidate_resolutions=frozenset({ExecutionResolution.REPLACE_AUTHORITATIVE}),
            requested_resolution=ExecutionResolution.REPLACE_AUTHORITATIVE,
            protection_continuity_proven=True,
        ),
    )

    assert isinstance(decision, ExecutionResolutionAuthorityDecision)
    assert decision.allowed is True
    assert decision.reason == ResolutionAuthorityReason.ALLOWED
    assert decision.selected_resolution == ExecutionResolution.REPLACE_AUTHORITATIVE
