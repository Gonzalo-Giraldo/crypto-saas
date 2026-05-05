from __future__ import annotations

from sqlalchemy.orm import Session

from apps.api.app.services.auto_pick.orchestrator import run_auto_pick
from apps.api.app.services.auto_pick.contracts import AutoPickDecision
from apps.api.app.services.auto_pick_to_risk import build_risk_from_auto_pick_decision
from apps.api.app.services.intent_draft import build_binance_intent_draft
from apps.api.app.services.intent_persistence import persist_binance_intent_from_draft


def run_binance_trading_cycle(
    *,
    db: Session,
    user_id: str | None = None,
    account_id: str = "default",
    capital_base: float = 1000.0,
    risk_pct: float = 0.01,
    reward_risk_ratio: float = 2.0,
    persist_intent: bool = False,
    execute_real: bool = False,
    execution_authorized: bool = False,
):
    result = run_auto_pick(broker="BINANCE")

    if not isinstance(result, AutoPickDecision):
        return {
            "status": "no_trade",
            "reason": getattr(result, "reason", "unknown"),
            "broker": getattr(result, "broker", "BINANCE"),
            "evidence": getattr(result, "evidence", {}),
        }

    risk = build_risk_from_auto_pick_decision(
        decision=result,
        capital_base=capital_base,
        risk_pct=risk_pct,
        reward_risk_ratio=reward_risk_ratio,
    )

    draft = build_binance_intent_draft(
        decision=result,
        risk=risk,
    )

    if not persist_intent:
        return {
            "status": "draft_ready",
            "broker": "BINANCE",
            "symbol": draft.symbol,
            "side": draft.side,
            "expected_qty": draft.expected_qty,
            "entry_price": draft.entry_price,
            "stop_loss": draft.stop_loss,
            "take_profit": draft.take_profit,
            "auto_pick_trace": draft.auto_pick_trace,
            "persisted": False,
            "executed": False,
        }

    if not user_id:
        raise ValueError("user_id_required_when_persisting_intent")

    return persist_binance_intent_from_draft(
        draft=draft,
        db=db,
        user_id=user_id,
        account_id=account_id,
        execute_real=execute_real,
        execution_authorized=execution_authorized,
    )
