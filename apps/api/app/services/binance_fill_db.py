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

        raw_side = fill.get("side")
        if raw_side is None and "isBuyer" in fill:
            raw_side = "BUY" if bool(fill.get("isBuyer")) else "SELL"

        obj = BinanceFill(
            user_id=user_id,
            account_id=account_id,
            broker=broker,
            market=market,
            trade_id=trade_id,
            order_id=fill.get("orderId"),
            symbol=fill.get("symbol"),
            side=raw_side,
            raw_payload=fill,
            price=fill.get("price"),
            qty=fill.get("qty"),
            quote_qty=fill.get("quoteQty"),
            commission=fill.get("commission"),
            commission_asset=fill.get("commissionAsset"),
            executed_at_ms=fill.get("time"),
        )

        db.add(obj)

        try:
            db.commit()
            inserted += 1
        except IntegrityError:
            db.rollback()
            skipped += 1

    return {"inserted": inserted, "skipped": skipped}
