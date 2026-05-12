from __future__ import annotations

from fastapi import HTTPException, status
from apps.api.app.services.trading_controls import get_trading_enabled

from apps.api.app.services.intent_draft import BinanceIntentDraft
from apps.api.app.services.binance_intent_adapter import create_binance_intent
from apps.api.app.services.intent_service import get_intent
from apps.api.app.services.intent_consumption_service import consume_intent
from apps.worker.app.engine.execution_runtime import execute_binance_real_order_for_user


def persist_binance_intent_from_draft(
    *,
    draft: BinanceIntentDraft,
    db,
    user_id,
    account_id,
    execute_real: bool = False,
    execution_authorized: bool = False,
):
    """
    SIDE EFFECT:
    - Persiste intent en DB usando adapter existente
    - NO recalcula nada
    - Por defecto NO ejecuta broker real
    - Si execute_real=True exige execution_authorized=True
    """

    if draft is None:
        raise ValueError("draft_required")

    result = create_binance_intent(
        db=db,
        user_id=user_id,
        account_id=account_id,
        symbol=draft.symbol,
        side=draft.side,
        expected_qty=draft.expected_qty,
        entry_price=draft.entry_price,
        stop_loss=draft.stop_loss,
        take_profit=draft.take_profit,
        auto_pick_trace=draft.auto_pick_trace,
        risk_policy={
            "risk_pct": draft.risk_pct,
            "risk_abs": draft.risk_abs,
            "risk_usdt": draft.risk_usdt,
            "reward_risk_ratio": draft.reward_risk_ratio,
            "entry_price_reference": draft.entry_price_reference,
            "expected_qty": draft.expected_qty,
        },
    )

    if not execute_real:
        return result

    if not execution_authorized:
        raise ValueError("real_execution_authorization_required")

    intent_id = result.get("intent_id")
    if not intent_id:
        raise ValueError("intent_id_required_for_execution")

    intent = get_intent(db, intent_id)
    if intent is None:
        raise ValueError("intent_not_found_after_persist")

    if str(intent.user_id) != str(user_id):
        raise ValueError("intent_user_mismatch")

    if str(intent.broker).upper() != "BINANCE":
        raise ValueError(f"invalid_broker_for_binance_execution:{intent.broker}")

    if str(intent.account_id) != str(account_id):
        raise ValueError("intent_account_mismatch")

    if str(intent.lifecycle_status).upper() != "CREATED":
        raise ValueError(f"invalid_state_for_execution:{intent.lifecycle_status}")

    if str(intent.side).upper() not in {"BUY", "SELL"}:
        raise ValueError(f"invalid_side_for_execution:{intent.side}")

    try:
        qty = float(intent.expected_qty)
    except Exception:
        raise ValueError("invalid_expected_qty_for_execution") from None

    if qty <= 0:
        raise ValueError("invalid_expected_qty_for_execution")

    if not get_trading_enabled(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="trading_disabled_by_admin_kill_switch",
        )

    consume_intent(
        db=db,
        intent_id=str(intent.intent_id),
        user_id=str(user_id),
        broker="BINANCE",
        account_id=str(intent.account_id),
    )

    execution = execute_binance_real_order_for_user(
        user_id=str(user_id),
        symbol=str(intent.symbol),
        side=str(intent.side),
        qty=qty,
        intent_key=str(intent.intent_id),
        account_id=str(intent.account_id),
        market=None,
    )

    return {
        **result,
        "execution": execution,
    }
