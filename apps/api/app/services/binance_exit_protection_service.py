from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.app.models.binance_exit_protection import BinanceExitProtection


def _validate_inputs(
    *,
    exit_key: str,
    intent_id: str,
    entry_execution_ref: str,
    symbol: str,
    market: str,
    direction: str,
    filled_qty,
    avg_entry_price,
    sl_client_algo_id: str,
    tp_client_algo_id: str,
):
    if not exit_key:
        raise ValueError("exit_key_required")

    if not intent_id:
        raise ValueError("intent_id_required")

    if not entry_execution_ref:
        raise ValueError("entry_execution_ref_required")

    if not symbol:
        raise ValueError("symbol_required")

    if market != "FUTURES":
        raise ValueError("market_must_be_futures")

    if direction not in ("LONG", "SHORT"):
        raise ValueError("invalid_direction")

    if filled_qty is None or float(filled_qty) <= 0:
        raise ValueError("invalid_filled_qty")

    if avg_entry_price is None or float(avg_entry_price) <= 0:
        raise ValueError("invalid_avg_entry_price")

    if not sl_client_algo_id:
        raise ValueError("sl_client_algo_id_required")

    if not tp_client_algo_id:
        raise ValueError("tp_client_algo_id_required")


def create_exit_protection(
    db: Session,
    *,
    exit_key: str,
    intent_id: str,
    entry_execution_ref: str,
    symbol: str,
    market: str,
    direction: str,
    filled_qty,
    avg_entry_price,
    sl_client_algo_id: str,
    tp_client_algo_id: str,
):
    _validate_inputs(
        exit_key=exit_key,
        intent_id=intent_id,
        entry_execution_ref=entry_execution_ref,
        symbol=symbol,
        market=market,
        direction=direction,
        filled_qty=filled_qty,
        avg_entry_price=avg_entry_price,
        sl_client_algo_id=sl_client_algo_id,
        tp_client_algo_id=tp_client_algo_id,
    )

    obj = BinanceExitProtection(
        exit_key=exit_key,
        intent_id=intent_id,
        entry_execution_ref=entry_execution_ref,
        symbol=symbol,
        market=market,
        direction=direction,
        filled_qty=filled_qty,
        avg_entry_price=avg_entry_price,
        sl_client_algo_id=sl_client_algo_id,
        tp_client_algo_id=tp_client_algo_id,
    )

    db.add(obj)

    try:
        db.commit()
        return {"status": "created", "exit_key": exit_key}
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate", "exit_key": exit_key}
