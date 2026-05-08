from __future__ import annotations


def should_build_authoritative_post_fill_plan(
    *,
    reconciliation_status: str,
) -> bool:
    """
    PURE FUNCTION.

    Timing gate for authoritative post-fill SL/TP recalculation.

    No DB.
    No broker.
    No runtime side effects.
    """

    return str(reconciliation_status or "").lower().strip() == "matched"
