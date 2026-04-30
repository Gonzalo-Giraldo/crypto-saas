from __future__ import annotations

from apps.api.app.services.intent_draft import BinanceIntentDraft
from apps.api.app.services.binance_intent_adapter import create_binance_intent


def persist_binance_intent_from_draft(
    *,
    draft: BinanceIntentDraft,
    db,
    user_id,
    account_id,
):
    """
    SIDE EFFECT:
    - Persiste intent en DB usando adapter existente
    - NO recalcula nada
    """

    if draft is None:
        raise ValueError("draft_required")

    return create_binance_intent(
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
    )
