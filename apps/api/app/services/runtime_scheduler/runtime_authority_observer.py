from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

from apps.api.app.services.runtime_scheduler.runtime_authority_snapshot import (
    RuntimeAuthoritySnapshot,
    refresh_runtime_authority_snapshot,
)


T = TypeVar("T")


@dataclass(frozen=True)
class RuntimeAuthorityObservedResult:
    result: object
    authority_snapshot: RuntimeAuthoritySnapshot


def run_with_runtime_authority_observer(
    *,
    scheduler_name: str,
    advisory_lock,
    ownership_row_present: bool,
    local_identity_matches: bool,
    local_runtime_generation: int | None,
    durable_runtime_generation: int | None,
    heartbeat_fresh: bool,
    runtime_health_valid: bool,
    fn: Callable[[], T],
) -> RuntimeAuthorityObservedResult:
    snapshot = refresh_runtime_authority_snapshot(
        scheduler_name=scheduler_name,
        advisory_lock=advisory_lock,
        ownership_row_present=ownership_row_present,
        local_identity_matches=local_identity_matches,
        local_runtime_generation=local_runtime_generation,
        durable_runtime_generation=durable_runtime_generation,
        heartbeat_fresh=heartbeat_fresh,
        runtime_health_valid=runtime_health_valid,
    )

    result = fn()

    return RuntimeAuthorityObservedResult(
        result=result,
        authority_snapshot=snapshot,
    )
