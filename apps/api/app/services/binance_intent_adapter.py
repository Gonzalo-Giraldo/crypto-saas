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
