from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from decimal import Decimal
from apps.api.app.db.session import get_db
from apps.api.app.api.deps import get_current_user
from apps.api.app.services.binance_unrealized_pnl_service import compute_binance_unrealized_pnl
from apps.api.app.services.binance_market_data_client import fetch_binance_ticker_price

router = APIRouter(prefix="/portfolio/binance", tags=["portfolio-binance"])

def _serialize_decimal(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _serialize_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_decimal(v) for v in obj]
    return obj

@router.get("/unrealized-pnl")
def get_unrealized_pnl(
    symbol: str = Query(...),
    account_id: str = Query("default"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    symbol = symbol.upper()

    if not symbol.endswith("USDT"):
        raise HTTPException(status_code=400, detail="symbol_must_be_usdt")

    rows = db.execute(
        text("""
        SELECT user_id, account_id, broker, market, symbol, side, qty, quote_qty, commission_usdt
        FROM binance_fills
        WHERE user_id = :user_id
          AND account_id = :account_id
          AND broker = 'BINANCE'
          AND market = 'SPOT'
          AND symbol = :symbol
        """),
        {
            "user_id": str(current_user.id),
            "account_id": account_id,
            "symbol": symbol,
        }
    ).fetchall()

    if not rows:
        return []

    fills = [dict(r._mapping) for r in rows]

    ticker = fetch_binance_ticker_price(symbol=symbol)
    if "price" not in ticker:
        raise HTTPException(status_code=500, detail="ticker_invalid")

    current_price = Decimal(str(ticker["price"]))

    result = compute_binance_unrealized_pnl(fills, current_price)

    return _serialize_decimal(result)
