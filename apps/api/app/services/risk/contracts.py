from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RiskSizingDecision:
    """Risk/sizing output. This is intentionally separate from AutoPickDecision."""

    entry_price: float
    stop_loss: float
    take_profit: float
    risk_pct: float
    risk_abs: float
    expected_qty: float
    evidence: dict[str, Any] = field(default_factory=dict)
