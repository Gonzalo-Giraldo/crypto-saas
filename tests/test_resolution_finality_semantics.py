from app.protection.resolution_finality_semantics import (
    FinalityEvidenceRequirement,
    FinalityReason,
    FinalityResolution,
    ResolutionFinalityDecision,
    ResolutionFinalityEvidence,
    ResolutionFinalityPolicy,
    evaluate_resolution_finality_semantics,
)


def test_denies_when_resolution_authority_not_allowed():
    decision = evaluate_resolution_finality_semantics(
        resolution_authority_allowed=False,
        policy=ResolutionFinalityPolicy(
            finalizable_resolutions=frozenset({FinalityResolution.NOOP}),
            forbidden_finalizations=frozenset(),
            already_finalized_resolutions=frozenset(),
            locked_finality_resolutions=frozenset(),
            required_finality_evidence=frozenset(),
            mutation_resolutions=frozenset(),
        ),
        evidence=ResolutionFinalityEvidence(
            requested_finalization=FinalityResolution.NOOP,
            provided_finality_evidence=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == FinalityReason.RESOLUTION_AUTHORITY_NOT_ALLOWED


def test_denies_forbidden_finalization():
    decision = evaluate_resolution_finality_semantics(
        resolution_authority_allowed=True,
        policy=ResolutionFinalityPolicy(
            finalizable_resolutions=frozenset({FinalityResolution.CLEANUP_PROVISIONAL}),
            forbidden_finalizations=frozenset({FinalityResolution.CLEANUP_PROVISIONAL}),
            already_finalized_resolutions=frozenset(),
            locked_finality_resolutions=frozenset(),
            required_finality_evidence=frozenset(),
            mutation_resolutions=frozenset(),
        ),
        evidence=ResolutionFinalityEvidence(
            requested_finalization=FinalityResolution.CLEANUP_PROVISIONAL,
            provided_finality_evidence=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == FinalityReason.FORBIDDEN_FINALIZATION
    assert decision.forbidden_finalizations == (FinalityResolution.CLEANUP_PROVISIONAL,)


def test_denies_non_finalizable_resolution():
    decision = evaluate_resolution_finality_semantics(
        resolution_authority_allowed=True,
        policy=ResolutionFinalityPolicy(
            finalizable_resolutions=frozenset({FinalityResolution.RECORD_AUDIT_ONLY}),
            forbidden_finalizations=frozenset(),
            already_finalized_resolutions=frozenset(),
            locked_finality_resolutions=frozenset(),
            required_finality_evidence=frozenset(),
            mutation_resolutions=frozenset(),
        ),
        evidence=ResolutionFinalityEvidence(
            requested_finalization=FinalityResolution.REPLACE_AUTHORITATIVE,
            provided_finality_evidence=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == FinalityReason.FORBIDDEN_FINALIZATION
    assert decision.forbidden_finalizations == (
        FinalityResolution.REPLACE_AUTHORITATIVE,
    )


def test_denies_already_finalized_resolution():
    decision = evaluate_resolution_finality_semantics(
        resolution_authority_allowed=True,
        policy=ResolutionFinalityPolicy(
            finalizable_resolutions=frozenset({FinalityResolution.REPLACE_AUTHORITATIVE}),
            forbidden_finalizations=frozenset(),
            already_finalized_resolutions=frozenset(
                {FinalityResolution.REPLACE_AUTHORITATIVE}
            ),
            locked_finality_resolutions=frozenset(),
            required_finality_evidence=frozenset(),
            mutation_resolutions=frozenset(),
        ),
        evidence=ResolutionFinalityEvidence(
            requested_finalization=FinalityResolution.REPLACE_AUTHORITATIVE,
            provided_finality_evidence=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == FinalityReason.ALREADY_FINALIZED


def test_denies_finality_lock_violation():
    decision = evaluate_resolution_finality_semantics(
        resolution_authority_allowed=True,
        policy=ResolutionFinalityPolicy(
            finalizable_resolutions=frozenset({FinalityResolution.CLEANUP_PROVISIONAL}),
            forbidden_finalizations=frozenset(),
            already_finalized_resolutions=frozenset(),
            locked_finality_resolutions=frozenset(
                {FinalityResolution.CLEANUP_PROVISIONAL}
            ),
            required_finality_evidence=frozenset(),
            mutation_resolutions=frozenset({FinalityResolution.CLEANUP_PROVISIONAL}),
        ),
        evidence=ResolutionFinalityEvidence(
            requested_finalization=FinalityResolution.CLEANUP_PROVISIONAL,
            provided_finality_evidence=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == FinalityReason.FINALITY_LOCK_VIOLATION
    assert decision.locked_finality_violations == (
        FinalityResolution.CLEANUP_PROVISIONAL,
    )


def test_denies_post_finalization_mutation():
    decision = evaluate_resolution_finality_semantics(
        resolution_authority_allowed=True,
        policy=ResolutionFinalityPolicy(
            finalizable_resolutions=frozenset({FinalityResolution.RECORD_AUDIT_ONLY}),
            forbidden_finalizations=frozenset(),
            already_finalized_resolutions=frozenset(
                {FinalityResolution.REPLACE_AUTHORITATIVE}
            ),
            locked_finality_resolutions=frozenset(),
            required_finality_evidence=frozenset(),
            mutation_resolutions=frozenset({FinalityResolution.REPLACE_AUTHORITATIVE}),
        ),
        evidence=ResolutionFinalityEvidence(
            requested_finalization=FinalityResolution.RECORD_AUDIT_ONLY,
            provided_finality_evidence=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == FinalityReason.POST_FINALIZATION_MUTATION
    assert decision.already_finalized_resolutions == (
        FinalityResolution.REPLACE_AUTHORITATIVE,
    )


def test_denies_missing_finality_evidence():
    decision = evaluate_resolution_finality_semantics(
        resolution_authority_allowed=True,
        policy=ResolutionFinalityPolicy(
            finalizable_resolutions=frozenset({FinalityResolution.REPLACE_AUTHORITATIVE}),
            forbidden_finalizations=frozenset(),
            already_finalized_resolutions=frozenset(),
            locked_finality_resolutions=frozenset(),
            required_finality_evidence=frozenset(
                {
                    FinalityEvidenceRequirement.AUTHORITATIVE_VERIFIED,
                    FinalityEvidenceRequirement.REPLACEMENT_RECONCILED,
                }
            ),
            mutation_resolutions=frozenset(),
        ),
        evidence=ResolutionFinalityEvidence(
            requested_finalization=FinalityResolution.REPLACE_AUTHORITATIVE,
            provided_finality_evidence=frozenset(
                {FinalityEvidenceRequirement.AUTHORITATIVE_VERIFIED}
            ),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == FinalityReason.MISSING_FINALITY_EVIDENCE
    assert decision.missing_finality_evidence == (
        FinalityEvidenceRequirement.REPLACEMENT_RECONCILED,
    )


def test_denies_when_protection_continuity_not_proven():
    decision = evaluate_resolution_finality_semantics(
        resolution_authority_allowed=True,
        policy=ResolutionFinalityPolicy(
            finalizable_resolutions=frozenset({FinalityResolution.RECORD_AUDIT_ONLY}),
            forbidden_finalizations=frozenset(),
            already_finalized_resolutions=frozenset(),
            locked_finality_resolutions=frozenset(),
            required_finality_evidence=frozenset(),
            mutation_resolutions=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=ResolutionFinalityEvidence(
            requested_finalization=FinalityResolution.RECORD_AUDIT_ONLY,
            provided_finality_evidence=frozenset(),
            protection_continuity_proven=False,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == FinalityReason.PROTECTION_CONTINUITY_REQUIRED


def test_authorizes_finality_when_all_requirements_are_satisfied():
    decision = evaluate_resolution_finality_semantics(
        resolution_authority_allowed=True,
        policy=ResolutionFinalityPolicy(
            finalizable_resolutions=frozenset({FinalityResolution.REPLACE_AUTHORITATIVE}),
            forbidden_finalizations=frozenset(),
            already_finalized_resolutions=frozenset(),
            locked_finality_resolutions=frozenset(),
            required_finality_evidence=frozenset(
                {
                    FinalityEvidenceRequirement.AUTHORITATIVE_VERIFIED,
                    FinalityEvidenceRequirement.REPLACEMENT_RECONCILED,
                    FinalityEvidenceRequirement.AUDIT_TRACE_COMPLETE,
                }
            ),
            mutation_resolutions=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=ResolutionFinalityEvidence(
            requested_finalization=FinalityResolution.REPLACE_AUTHORITATIVE,
            provided_finality_evidence=frozenset(
                {
                    FinalityEvidenceRequirement.AUTHORITATIVE_VERIFIED,
                    FinalityEvidenceRequirement.REPLACEMENT_RECONCILED,
                    FinalityEvidenceRequirement.AUDIT_TRACE_COMPLETE,
                }
            ),
            protection_continuity_proven=True,
        ),
    )

    assert isinstance(decision, ResolutionFinalityDecision)
    assert decision.allowed is True
    assert decision.reason == FinalityReason.ALLOWED
    assert decision.finalized_resolution == FinalityResolution.REPLACE_AUTHORITATIVE
