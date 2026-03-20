
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
        import time
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
            # Return the stored result, but update idempotency_status and stage for duplicate
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
        now = time.time()
        intent_id = f"{user_id}:{order_ref}"
        result = {
            "accepted": True,
            "intent_id": intent_id,
            "stage": "submission",
            "reason": None,
            "broker": broker,
            "symbol": symbol,
            "side": side_norm,
            "quantity": quantity,
            "order_ref": order_ref,
            "idempotency_status": "ok",
            "risk_status": "approved",
            "intent_status": "processed",
            "submission_status": "simulated_submitted",
            "fill_status": "not_filled",
            "created_at": now,
            "processed_at": now,
            "portfolio_effect_applied": False,
        }
        # Invariants
        assert result["fill_status"] != "filled"
        assert result["accepted"] is True
        assert result["submission_status"] is not None
        assert result["risk_status"] == "approved"
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
        import time
        intent_id = None
        now = time.time()
        result = {
            "accepted": False,
            "intent_id": intent_id,
            "stage": stage,
            "reason": reason,
            "broker": broker,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_ref": order_ref,
            "idempotency_status": "not_checked",
            "risk_status": risk_status,
            "intent_status": "rejected",
            "submission_status": None,
            "fill_status": "unknown",
            "created_at": now,
            "processed_at": now,
            "portfolio_effect_applied": False,
        }
        # Invariants
        assert result["accepted"] is False
        assert result["submission_status"] is None
        assert result["fill_status"] != "filled"
        return result
