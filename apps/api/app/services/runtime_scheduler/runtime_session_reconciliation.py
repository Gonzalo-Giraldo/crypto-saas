from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeGenerationReconciliation:
    matches: bool
    reason: str | None


def evaluate_runtime_generation_reconciliation(
    *,
    local_runtime_generation: int | None,
    durable_runtime_generation: int | None,
) -> RuntimeGenerationReconciliation:
    if local_runtime_generation is None:
        return RuntimeGenerationReconciliation(
            matches=False,
            reason="local_runtime_generation_missing",
        )

    if durable_runtime_generation is None:
        return RuntimeGenerationReconciliation(
            matches=False,
            reason="durable_runtime_generation_missing",
        )

    if local_runtime_generation <= 0:
        return RuntimeGenerationReconciliation(
            matches=False,
            reason="local_runtime_generation_invalid",
        )

    if durable_runtime_generation <= 0:
        return RuntimeGenerationReconciliation(
            matches=False,
            reason="durable_runtime_generation_invalid",
        )

    if local_runtime_generation != durable_runtime_generation:
        return RuntimeGenerationReconciliation(
            matches=False,
            reason="runtime_generation_mismatch",
        )

    return RuntimeGenerationReconciliation(
        matches=True,
        reason=None,
    )
