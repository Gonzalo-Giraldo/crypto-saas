from apps.api.app.services.tp_builder import compute_take_profit
from apps.api.app.services.risk_level_resolver import resolve_risk_level
from apps.api.app.services.intent_service import create_intent

def create_binance_intent(
    *,
    db,
    user_id: str,
    account_id: str,
    symbol: str,
    side: str,
    expected_qty,
    order_type: str = "MARKET",
    source: str = "binance_adapter",
    entry_price=None,
    stop_loss=None,
    take_profit=None,
    risk_profile: dict | None = None,
    auto_pick_trace: dict | None = None,
    risk_policy: dict | None = None,
) -> dict:
    if db is None:
        raise ValueError("db is required")
    if not user_id or not isinstance(user_id, str):
        raise ValueError("user_id is required and must be a string")
    if not account_id or not isinstance(account_id, str):
        raise ValueError("account_id is required and must be a string")
    if not symbol or not isinstance(symbol, str):
        raise ValueError("symbol is required and must be a string")
    if not side or not isinstance(side, str):
        raise ValueError("side is required and must be a string")
    if expected_qty is None:
        raise ValueError("expected_qty is required")
    if not order_type or not isinstance(order_type, str):
        raise ValueError("order_type is required and must be a string")
    if not source or not isinstance(source, str):
        raise ValueError("source is required and must be a string")

    # --- F24.5/F25.1 financial validation ---
    profile = risk_profile or {}
    # --- F34 + F33 integration ---
    risk_level = profile.get("risk_level")

    if take_profit is None and entry_price is not None and stop_loss is not None and risk_level:
        try:
            rl = resolve_risk_level(risk_level)

            tp_result = compute_take_profit(
                entry_price=float(entry_price),
                stop_loss=float(stop_loss),
                side=side,
                target_rr=rl["target_rr"],
                min_rr=rl["min_rr"],
            )

            take_profit = tp_result["tp"]
            profile["min_rr"] = rl["min_rr"]

        except Exception as e:
            raise ValueError(f"auto TP generation failed: {str(e)}")

    stop_loss_required = bool(profile.get("stop_loss_required", False))
    min_rr = float(profile.get("min_rr", 0) or 0)

    if stop_loss is None:
        raise ValueError("stop_loss required for Binance intent")

    if stop_loss_required and stop_loss is None:
        raise ValueError("stop_loss required by risk profile")

    if entry_price is not None and stop_loss is not None and take_profit is not None:
        try:
            entry = float(entry_price)
            sl = float(stop_loss)
            tp = float(take_profit)
        except Exception:
            raise ValueError("invalid financial fields in intent")

        side_norm = side.upper()

        if side_norm == "BUY":
            if not (sl < entry < tp):
                raise ValueError("invalid SL/TP for BUY: must be stop_loss < entry_price < take_profit")
            risk = entry - sl
            reward = tp - entry
        elif side_norm == "SELL":
            if not (tp < entry < sl):
                raise ValueError("invalid SL/TP for SELL: must be take_profit < entry_price < stop_loss")
            risk = sl - entry
            reward = entry - tp
        else:
            risk = 0
            reward = 0

        if min_rr > 0:
            if risk <= 0:
                raise ValueError("invalid risk distance in intent")
            rr = reward / risk
            if rr < min_rr:
                raise ValueError(f"risk/reward below profile minimum: rr={rr:.4f} min_rr={min_rr:.4f}")

    # --- F26 snapshot persist ---
    risk_abs = None
    if entry_price is not None and stop_loss is not None:
        try:
            entry = float(entry_price)
            sl = float(stop_loss)
            risk_abs = abs(entry - sl)
        except Exception:
            risk_abs = None

    risk_pct = None
    if entry_price and risk_abs:
        try:
            risk_pct = (risk_abs / float(entry_price)) * 100.0
        except Exception:
            risk_pct = None

    policy_snapshot = {
        "risk_profile": profile,
        "min_rr": min_rr,
    }

    if risk_policy is not None:
        if not isinstance(risk_policy, dict):
            raise ValueError("risk_policy must be a dict")
        policy_snapshot["risk_policy"] = dict(risk_policy)

    if auto_pick_trace is not None:
        if not isinstance(auto_pick_trace, dict):
            raise ValueError("auto_pick_trace must be a dict")

        final_score = auto_pick_trace.get("final_score")
        decision_reason = auto_pick_trace.get("decision_reason")
        evidence = auto_pick_trace.get("evidence")

        if final_score is None:
            raise ValueError("auto_pick_trace.final_score is required")
        if not decision_reason or not isinstance(decision_reason, str):
            raise ValueError("auto_pick_trace.decision_reason is required")
        if evidence is not None and not isinstance(evidence, dict):
            raise ValueError("auto_pick_trace.evidence must be a dict")

        policy_snapshot["auto_pick"] = {
            "final_score": float(final_score),
            "decision_reason": decision_reason,
            "evidence": evidence or {},
        }

    intent = create_intent(
        db=db,
        user_id=user_id,
        broker="BINANCE",
        account_id=account_id,
        symbol=symbol,
        side=side,
        expected_qty=expected_qty,
        order_type=order_type,
        source=source,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,

        strategy_id="SWING_V1",
        risk_pct=risk_pct,
        risk_abs=risk_abs,
        policy_snapshot=policy_snapshot,
    )

    return {
        "intent_id": str(intent.intent_id),
        "broker": intent.broker,
        "account_id": intent.account_id,
        "symbol": intent.symbol,
        "side": intent.side,
        "expected_qty": str(intent.expected_qty),
        "order_type": intent.order_type,
        "source": intent.source,
        "lifecycle_status": intent.lifecycle_status,
        "entry_price": str(intent.entry_price) if intent.entry_price is not None else None,
        "stop_loss": str(intent.stop_loss) if intent.stop_loss is not None else None,
        "take_profit": str(intent.take_profit) if intent.take_profit is not None else None,
    }
