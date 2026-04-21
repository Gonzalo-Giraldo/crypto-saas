from apps.api.app.services.intent_service import create_intent


def create_ibkr_intent(
    *,
    db,
    user_id: str,
    account_id: str,
    symbol: str,
    side: str,
    expected_qty,
    order_type: str = "MARKET",
    source: str = "ibkr_adapter",
    entry_price=None,
    stop_loss=None,
    take_profit=None,
) -> dict:

    intent = create_intent(
        db=db,
        user_id=user_id,
        broker="IBKR",
        account_id=account_id,
        symbol=symbol,
        side=side,
        expected_qty=expected_qty,
        order_type=order_type,
        source=source,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )

    return {
        "intent_id": str(intent.intent_id),
        "broker": intent.broker,
    }
