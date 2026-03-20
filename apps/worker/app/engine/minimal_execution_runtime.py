
from apps.worker.app.engine.risk_engine import RiskIntent, RiskEngine

class MinimalExecutionRuntime:
    def __init__(self):
        # In-memory idempotency store: {(user_id, order_ref): result_dict}
        self._idempotency_store = {}

    def submit_intent(
        self,
        *,
        user_id,
        strategy_id,
        broker,
        market,
        symbol,
        side,
        quantity,
        order_ref,
        mode,
        metadata=None
    ):
        # Validate required fields
        if not order_ref or not str(order_ref).strip():
            return self._reject(
                stage="input_validation",
                reason="order_ref is required",
                broker=broker,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_ref=order_ref,
            )
        idempotency_key = (user_id, order_ref)
        if idempotency_key in self._idempotency_store:
            result = self._idempotency_store[idempotency_key].copy()
            result["idempotency_status"] = "duplicate"
            result["stage"] = "idempotency"
            return result
        if broker != "binance":
            return self._reject(
                stage="input_validation",
                reason=f"unsupported broker: {broker}",
                broker=broker,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_ref=order_ref,
            )
        if mode != "stub":
            return self._reject(
                stage="input_validation",
                reason=f"unsupported mode: {mode}",
                broker=broker,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_ref=order_ref,
            )
        if not symbol or not str(symbol).strip():
            return self._reject(
                stage="input_validation",
                reason="symbol is required",
                broker=broker,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_ref=order_ref,
            )
        if not isinstance(quantity, (int, float)) or quantity <= 0:
            return self._reject(
                stage="input_validation",
                reason="quantity must be > 0",
                broker=broker,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_ref=order_ref,
            )
        side_norm = str(side).upper()
        if side_norm not in ("BUY", "SELL"):
            return self._reject(
                stage="input_validation",
                reason=f"unsupported side: {side}",
                broker=broker,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_ref=order_ref,
            )
        # Risk check
        intent = RiskIntent(
            strategy_id=strategy_id,
            symbol=symbol,
            side=side_norm,
            quantity=quantity,
            broker=broker,
            market=market,
            notional=None,
            metadata=metadata or {},
        )
        risk_decision = RiskEngine().evaluate_intent(intent)
        if not getattr(risk_decision, "approved", False):
            return self._reject(
                stage="risk_check",
                reason="risk engine rejected intent",
                broker=broker,
                symbol=symbol,
                side=side_norm,
                quantity=quantity,
                order_ref=order_ref,
                risk_status="rejected",
            )
        # Simulated submission (stub)
        result = {
            "accepted": True,
            "stage": "submission",
            "reason": None,
            "broker": broker,
            "symbol": symbol,
            "side": side_norm,
            "quantity": quantity,
            "order_ref": order_ref,
            "idempotency_status": "ok",
            "risk_status": "approved",
            "submission_status": "simulated_submitted",
            "fill_status": "not_filled",
            "portfolio_effect_applied": False,
        }
        self._idempotency_store[idempotency_key] = result.copy()
        return result

    def _reject(
        self,
        *,
        stage,
        reason,
        broker,
        symbol,
        side,
        quantity,
        order_ref,
        risk_status=None,
    ):
        return {
            "accepted": False,
            "stage": stage,
            "reason": reason,
            "broker": broker,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_ref": order_ref,
            "idempotency_status": "not_checked",
            "risk_status": risk_status,
            "submission_status": None,
            "fill_status": "unknown",
            "portfolio_effect_applied": False,
        }
