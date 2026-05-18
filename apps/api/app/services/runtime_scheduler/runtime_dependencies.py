from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class SchedulerRuntimeDependencies:
    legacy_exit_tick: Callable
    legacy_market_monitor_tick: Callable
    legacy_auto_pick_tick: Callable
    legacy_learning_tick: Callable
    global_shadow_tick: Callable
