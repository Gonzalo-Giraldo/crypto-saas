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
        def _is_price_missing_or_stale(self, intent):
            user_id = getattr(intent, 'strategy_id', None)
            broker = getattr(intent, 'broker', None)
            symbol = getattr(intent, 'symbol', None)
            mde = self.market_data_engine
            if mde and user_id and broker and symbol:
                # Usar get_fresh_price para determinar si hay precio y si está stale
                quote = mde.get_fresh_price(user_id, broker, symbol)
                if not quote or not hasattr(quote, 'price') or quote.price is None:
                    return True
            return False
    def __init__(self, portfolio_engine=None, market_data_engine=None):
        # Configurable risk guardrails (safe defaults)
        self.max_order_quantity = 100
        self.max_notional_value = 1_000_000
        self.max_symbol_exposure = 1_000_000
        self.risk_engine_enabled = True
        self.portfolio_engine = portfolio_engine
        self.market_data_engine = market_data_engine

    def set_portfolio_engine(self, portfolio_engine):
        self.portfolio_engine = portfolio_engine

    def set_market_data_engine(self, market_data_engine):
        self.market_data_engine = market_data_engine

    def _get_value_context(self, intent):
        # intent debe tener user_id, broker, symbol
        user_id = getattr(intent, 'strategy_id', None)  # Asumimos strategy_id como user_id
        broker = getattr(intent, 'broker', None)
        symbol = getattr(intent, 'symbol', None)
        pe = self.portfolio_engine
        mde = self.market_data_engine
        if pe and mde and user_id and broker and symbol:
            try:
                position_value = pe.get_position_value(user_id, broker, symbol, mde)
            except Exception:
                position_value = None
            try:
                total_portfolio_value = pe.get_total_portfolio_value(user_id, broker, mde)
            except Exception:
                total_portfolio_value = None
            return {
                'position_value': position_value,
                'total_portfolio_value': total_portfolio_value
            }
        return {'position_value': None, 'total_portfolio_value': None}

    def disable_trading(self):
        self.risk_engine_enabled = False

    def enable_trading(self):
        self.risk_engine_enabled = True

    def evaluate_intent(self, intent: RiskIntent) -> RiskDecision:
        # Contexto de valuación (no afecta decisión)
        value_ctx = self._get_value_context(intent)
        position_value = value_ctx['position_value']
        total_portfolio_value = value_ctx['total_portfolio_value']

        # 0️⃣ Global kill switch
        if not self.risk_engine_enabled:
            return RiskDecision(
                approved=False,
                reason="risk_engine_disabled"
            )
        # 1️⃣ Quantity guardrail
        if intent.quantity > self.max_order_quantity:
            return RiskDecision(
                approved=False,
                reason="order_quantity_exceeds_limit"
            )
        # 2️⃣ Notional guardrail (price-dependent)
        if self._is_price_missing_or_stale(intent):
            return RiskDecision(
                approved=False,
                reason="price_missing_or_stale"
            )
        # 2️⃣ Guardrail económico principal (value-based, proyectado)
        user_id = getattr(intent, 'strategy_id', None)
        broker = getattr(intent, 'broker', None)
        symbol = getattr(intent, 'symbol', None)
        pe = self.portfolio_engine
        mde = self.market_data_engine
        current_position_value = None
        order_value = None
        projected_position_value = None
        if pe and mde and user_id and broker and symbol:
            try:
                # Valor actual de la posición
                current_position_value = pe.get_position_value(user_id, broker, symbol, mde)
            except Exception:
                current_position_value = None
            try:
                # Valor de la orden (solo la cantidad de la orden * precio actual)
                price = mde.get_price_value(user_id, broker, symbol)
                if price is not None and hasattr(intent, 'quantity') and intent.quantity is not None:
                    order_value = intent.quantity * price
            except Exception:
                order_value = None
            if current_position_value is not None and order_value is not None:
                projected_position_value = current_position_value + order_value
        if projected_position_value is not None and projected_position_value > self.max_notional_value:
            return RiskDecision(
                approved=False,
                reason="order_value_exceeds_limit"
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
