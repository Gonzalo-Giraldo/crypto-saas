from __future__ import annotations

from dataclasses import dataclass

from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
    RuntimeAdvisorySessionState,
)
from apps.api.app.services.runtime_scheduler.runtime_advisory_session_service import (
    refresh_runtime_advisory_session_state,
)
from apps.api.app.services.runtime_scheduler.runtime_authority_coordinator import (
    RuntimeAuthorityCoordinatorInput,
    RuntimeAuthorityCoordinatorResult,
    evaluate_runtime_authority,
)
from apps.api.app.services.runtime_scheduler.runtime_authority_state import (
    RuntimeAuthorityStateProjection,
    project_runtime_authority_state,
)
from apps.api.app.services.runtime_scheduler.runtime_session_reconciliation import (
    RuntimeGenerationReconciliation,
    evaluate_runtime_generation_reconciliation,
)


@dataclass(frozen=True)
class RuntimeAuthoritySnapshot:
    advisory_session: RuntimeAdvisorySessionState
    generation_reconciliation: RuntimeGenerationReconciliation
    authority: RuntimeAuthorityCoordinatorResult
    authority_state: RuntimeAuthorityStateProjection


def refresh_runtime_authority_snapshot(
    *,
    scheduler_name: str,
    advisory_lock,
    ownership_row_present: bool,
    local_identity_matches: bool,
    local_runtime_generation: int | None,
    durable_runtime_generation: int | None,
    heartbeat_fresh: bool,
    runtime_health_valid: bool,
) -> RuntimeAuthoritySnapshot:
    advisory_session = refresh_runtime_advisory_session_state(
        scheduler_name=scheduler_name,
        lock=advisory_lock,
    )

    generation_reconciliation = evaluate_runtime_generation_reconciliation(
        local_runtime_generation=local_runtime_generation,
        durable_runtime_generation=durable_runtime_generation,
    )

    authority = evaluate_runtime_authority(
        authority_input=RuntimeAuthorityCoordinatorInput(
            ownership_row_present=ownership_row_present,
            advisory_session_state=advisory_session,
            local_identity_matches=local_identity_matches,
            generation_matches=generation_reconciliation.matches,
            heartbeat_fresh=heartbeat_fresh,
            runtime_health_valid=runtime_health_valid,
        ),
    )

    authority_state = project_runtime_authority_state(
        authority_valid=authority.valid,
        authority_reason=authority.reason,
        advisory_session_reason=authority.advisory_session_reason,
    )

    return RuntimeAuthoritySnapshot(
        advisory_session=advisory_session,
        generation_reconciliation=generation_reconciliation,
        authority=authority,
        authority_state=authority_state,
    )
