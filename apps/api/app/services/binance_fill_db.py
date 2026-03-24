from sqlalchemy.exc import IntegrityError
from apps.api.app.models.binance_fill import BinanceFill

def persist_binance_fills_db(db, fills: list, user_id: str, account_id: str, broker: str, market: str):
    inserted = 0
    skipped = 0
    for fill in fills:
        trade_id = fill.get("id") or fill.get("tradeId")
        if trade_id is not None:
            trade_id = str(trade_id)
        if not trade_id:
            continue
        # Check if already exists
        exists = db.query(BinanceFill).filter_by(
            user_id=user_id,
            account_id=account_id,
            broker=broker,
            market=market,
            trade_id=trade_id
        ).first()
        if exists:
            skipped += 1
            continue
        obj = BinanceFill(
            user_id=user_id,
            account_id=account_id,
            broker=broker,
            market=market,
            trade_id=trade_id,
            order_id=fill.get("orderId"),
            symbol=fill.get("symbol"),
            side=fill.get("side"),
            raw_payload=fill
        )
        db.add(obj)
        try:
            db.commit()
            inserted += 1
        except IntegrityError:
            db.rollback()
            skipped += 1
    return {"inserted": inserted, "skipped": skipped}
