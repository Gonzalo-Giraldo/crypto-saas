from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AutopickTickDependencies:
    db: object
    settings: object


def build_autopick_tick_dependencies(
    *,
    db,
    settings,
):
    return AutopickTickDependencies(
        db=db,
        settings=settings,
    )
