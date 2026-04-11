from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from apps.api.app.db.session import get_db
from apps.api.app.services.exchange_secrets import get_decrypted_exchange_secret
from apps.worker.app.engine.minimal_execution_runtime import IntentConsumptionStore
from apps.worker.app.engine.ibkr_client import get_ibkr_trades

from apps.api.app.services.ibkr_reconciliation import get_ibkr_reconciliation_source, reconcile_ibkr_fills
from apps.api.app.services.ibkr_portfolio import get_ibkr_portfolio

router = APIRouter(prefix="/ops", tags=["ops-ibkr"])

# Endpoint de portfolio mínimo IBKR

@router.get("/ibkr/portfolio")
def ibkr_portfolio_endpoint(
    user_id: str = Query(...),
    account_id: str = Query(...),
    db: Session = Depends(get_db),
):
    result = get_ibkr_portfolio(user_id=user_id, account_id=account_id, db=db)
    return result
# apps/api/app/api/ops_ibkr.py

# Endpoint de reconciliación mínima IBKR

@router.get("/ibkr/reconcile")
def ibkr_reconcile_endpoint(
    execution_ref: str = Query(...),
    user_id: str = Query(...),
    account_id: str = Query(...),
    mode: str = Query("dummy_db"),
    expected_qty: float = Query(None),
    db: Session = Depends(get_db),
):
    try:
        fills = get_ibkr_reconciliation_source(
            execution_ref=execution_ref,
            user_id=user_id,
            account_id=account_id,
            db=db,
            mode=mode
        )
        result = reconcile_ibkr_fills(fills, expected_qty=expected_qty)
        return {"success": True, "reconciliation": result}
    except Exception as exc:
        return {"success": False, "error": str(exc)}

@router.get("/intent-ibkr-trades")
def get_intent_ibkr_trades(
    intent_key: str = Query(...),
    user_id: str = Query(...),
    broker: str = Query(...),
    account_id: str = Query(...),
    db: Session = Depends(get_db),
):
    if broker.lower() != "ibkr":
        return {"success": False, "error": "Only broker=ibkr is supported"}

    normalized_account_id = account_id if account_id and str(account_id).strip() else None
    store = IntentConsumptionStore()
    rec = store.get_consumption_record(
        user_id=user_id,
        broker=broker,
        intent_key=intent_key,
        account_id=normalized_account_id,
    )
    if not rec.get("found"):
        return {"success": False, "error": "No consumption record found"}
    broker_execution_id = rec.get("broker_execution_id")
    symbol = rec.get("symbol")
    if not broker_execution_id or not symbol:
        return {"success": False, "error": "Missing execution linkage"}
    creds = get_decrypted_exchange_secret(db=db, user_id=user_id, exchange="IBKR")
    if not creds:
        return {"success": False, "error": "No IBKR credentials"}
    try:
        order_ref = broker_execution_id
        result = get_ibkr_trades(
            api_key=creds["api_key"],
            api_secret=creds["api_secret"],
            symbol=symbol,
            client_order_id=order_ref,
        )
        # Persistencia mínima e idempotente de fills IBKR
        fills = []
        for trade in result.get("trades", []):
            fill_id = trade.get("trade_id")
            if not fill_id:
                continue
            try:
                fill = IbkrFill(
                    fill_id=fill_id,
                    symbol=trade.get("symbol"),
                    qty=trade.get("qty"),
                    price=trade.get("price"),
                    timestamp=trade.get("timestamp"),
                    user_id=user_id,
                    broker="ibkr",
                    execution_ref=broker_execution_id,
                )
                db.add(fill)
                db.commit()
                db.refresh(fill)

                fills.append({
                    "fill_id": fill.fill_id,
                    "symbol": fill.symbol,
                    "qty": fill.qty,
                    "price": fill.price,
                    "timestamp": fill.timestamp,
                    "user_id": fill.user_id,
                    "broker": fill.broker,
                    "execution_ref": fill.execution_ref,
                })

            except IntegrityError:
                db.rollback()
                existing = db.execute(
                    select(IbkrFill).where(IbkrFill.fill_id == fill_id)
                ).scalar_one()

                fills.append({
                    "fill_id": existing.fill_id,
                    "symbol": existing.symbol,
                    "qty": existing.qty,
                    "price": existing.price,
                    "timestamp": existing.timestamp,
                    "user_id": existing.user_id,
                    "broker": existing.broker,
                    "execution_ref": existing.execution_ref,
                })

                # Check if fill already exists
        return {"success": True, "order_ref": order_ref, "payload": result, "fills": fills}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
