# apps/api/app/api/ops_ibkr.py

from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session

from apps.api.app.db.session import get_db
from apps.api.app.services.exchange_secrets import get_decrypted_exchange_secret
from apps.worker.app.engine.minimal_execution_runtime import IntentConsumptionStore
from apps.worker.app.engine.ibkr_client import get_ibkr_trades

router = APIRouter(prefix="/ops", tags=["ops"])


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

    store = IntentConsumptionStore()
    rec = store.get_consumption_record(
        user_id=user_id,
        broker=broker,
        intent_key=intent_key,
        account_id=account_id,
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
        result = get_ibkr_trades(
            api_key=creds["api_key"],
            api_secret=creds["api_secret"],
            symbol=symbol,
            client_order_id=broker_execution_id,
        )
        return {"success": True, "payload": result}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
