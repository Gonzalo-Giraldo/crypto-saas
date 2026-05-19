from __future__ import annotations

from dataclasses import dataclass

from apps.api.app.models.scheduler_runtime_state import SchedulerRuntimeState
from apps.api.app.services.runtime_scheduler.runtime_authority_coordinator import (
    RuntimeAuthorityCoordinatorInput,
    RuntimeAuthorityCoordinatorResult,
    evaluate_runtime_authority,
)
from apps.api.app.services.runtime_scheduler.runtime_authority_state import (
    RuntimeAuthorityStateProjection,
    project_runtime_authority_state,
)
from apps.api.app.services.runtime_scheduler.runtime_ownership_lifecycle import (
    RuntimeOwnershipLifecycleProjection,
    build_runtime_ownership_lifecycle_projection,
)
from apps.api.app.services.runtime_scheduler.runtime_session_identity import (
    RuntimeSessionIdentity,
    RuntimeSessionLocalState,
    get_runtime_session_identity,
    get_runtime_session_local_state,
)
from apps.api.app.services.runtime_scheduler.runtime_session_reconciliation import (
    RuntimeGenerationReconciliation,
    evaluate_runtime_generation_reconciliation,
)


@dataclass(frozen=True)
class RuntimeAuthorityRuntimeSnapshot:
    local_runtime_identity: RuntimeSessionIdentity
    local_runtime_state: RuntimeSessionLocalState
    local_identity_matches: bool
    generation_reconciliation: RuntimeGenerationReconciliation
    generation_matches: bool
    advisory_session_valid: bool
    advisory_session_reason: str | None
    ownership_lifecycle: RuntimeOwnershipLifecycleProjection | None
    runtime_authority: RuntimeAuthorityCoordinatorResult
    runtime_authority_state: RuntimeAuthorityStateProjection


def build_runtime_authority_runtime_snapshot(
    *,
    scheduler_name: str,
    scheduler_state: SchedulerRuntimeState | None,
    scheduler_interval_minutes: int,
    runtime_health_valid: bool,
) -> RuntimeAuthorityRuntimeSnapshot:
    local_runtime_identity = get_runtime_session_identity(
        scheduler_name=scheduler_name,
    )
    local_runtime_state = get_runtime_session_local_state(
        scheduler_name=scheduler_name,
    )

    ownership_lifecycle = (
        build_runtime_ownership_lifecycle_projection(
            runtime_state=scheduler_state,
            stale_after_seconds=scheduler_interval_minutes * 60 * 2,
        )
        if scheduler_state
        else None
    )

    local_identity_matches = bool(
        scheduler_state
        and scheduler_state.runtime_owner_id == local_runtime_identity.runtime_owner_id
        and scheduler_state.runtime_instance_id == local_runtime_identity.runtime_instance_id
    )

    generation_reconciliation = evaluate_runtime_generation_reconciliation(
        local_runtime_generation=local_runtime_state.runtime_generation,
        durable_runtime_generation=(
            scheduler_state.runtime_generation
            if scheduler_state
            else None
        ),
    )
    generation_matches = generation_reconciliation.matches
    advisory_session = local_runtime_state.advisory_session_state

    runtime_authority = evaluate_runtime_authority(
        authority_input=RuntimeAuthorityCoordinatorInput(
            ownership_row_present=bool(
                scheduler_state
                and scheduler_state.runtime_owner_id
            ),
            advisory_session_state=advisory_session,
            local_identity_matches=local_identity_matches,
            generation_matches=generation_matches,
            heartbeat_fresh=bool(
                ownership_lifecycle
                and not ownership_lifecycle.stale
            ),
            runtime_health_valid=bool(runtime_health_valid),
        ),
    )

    runtime_authority_state = project_runtime_authority_state(
        authority_valid=runtime_authority.valid,
        authority_reason=runtime_authority.reason,
        advisory_session_reason=runtime_authority.advisory_session_reason,
    )

    return RuntimeAuthorityRuntimeSnapshot(
        local_runtime_identity=local_runtime_identity,
        local_runtime_state=local_runtime_state,
        local_identity_matches=local_identity_matches,
        generation_reconciliation=generation_reconciliation,
        generation_matches=generation_matches,
        advisory_session_valid=advisory_session.valid,
        advisory_session_reason=advisory_session.reason,
        ownership_lifecycle=ownership_lifecycle,
        runtime_authority=runtime_authority,
        runtime_authority_state=runtime_authority_state,
    )
