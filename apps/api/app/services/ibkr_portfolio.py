# apps/api/app/services/ibkr_portfolio.py

from apps.api.app.models import IbkrFill
from sqlalchemy.orm import Session
from sqlalchemy import select
from collections import defaultdict

def get_ibkr_portfolio(user_id: str, account_id: str, db: Session):
    # Leer fills de IBKR para el usuario (ignora account_id por ahora)
    fills = db.execute(
        select(IbkrFill)
        .where(
            IbkrFill.user_id == user_id,
            IbkrFill.broker == "ibkr"
        )
    ).scalars().all()
    # Agrupar por symbol
    grouped = defaultdict(list)
    for f in fills:
        grouped[f.symbol].append(f)
    positions = []
    for symbol, symbol_fills in grouped.items():
        total_qty = sum(f.qty for f in symbol_fills)
        if total_qty > 0:
            avg_price = sum(f.qty * f.price for f in symbol_fills) / total_qty
        else:
            avg_price = None
        positions.append({
            "symbol": symbol,
            "qty": total_qty,
            "avg_price": avg_price
        })
    return {"positions": positions}
