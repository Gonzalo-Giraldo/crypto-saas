"""
Risk Engine groundwork: pre-trade risk validation structure.
No runtime wiring, no external dependencies.
"""

from typing import Optional, Any

class RiskIntent:
    def __init__(
        self,
        strategy_id: str,
        symbol: str,
        side: str,
        quantity: float,
        broker: str,
        market: str,
        notional: Optional[float] = None,
        current_symbol_exposure: Optional[float] = None,
        metadata: Optional[Any] = None,
    ):
        self.strategy_id = strategy_id
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.notional = notional
        self.current_symbol_exposure = current_symbol_exposure
        self.broker = broker
        self.market = market
        self.metadata = metadata

class RiskDecision:
    def __init__(self, approved: bool, reason: Optional[str] = None, adjusted_quantity: Optional[float] = None):
        self.approved = approved
        self.reason = reason
        self.adjusted_quantity = adjusted_quantity

class RiskEngine:
    def __init__(self):
        # Configurable risk guardrails (safe defaults)
        self.max_order_quantity = 100
        self.max_notional_value = 1_000_000
        self.max_symbol_exposure = 1_000_000

    def evaluate_intent(self, intent: RiskIntent) -> RiskDecision:
        # 1️⃣ Quantity guardrail
        if intent.quantity > self.max_order_quantity:
            return RiskDecision(
                approved=False,
                reason="order_quantity_exceeds_limit"
            )
        # 2️⃣ Notional guardrail (if present)
        if intent.notional is not None and intent.notional > self.max_notional_value:
            return RiskDecision(
                approved=False,
                reason="order_notional_exceeds_limit"
            )
        # 3️⃣ Symbol exposure guardrail (if exposure info present)
        if intent.current_symbol_exposure is not None and intent.notional is not None:
            projected_exposure = intent.current_symbol_exposure + intent.notional
            if projected_exposure > self.max_symbol_exposure:
                return RiskDecision(
                    approved=False,
                    reason="symbol_exposure_exceeds_limit"
                )
        # 4️⃣ Approve if within limits
        return RiskDecision(approved=True)
