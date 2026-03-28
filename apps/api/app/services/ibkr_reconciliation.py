# apps/api/app/services/ibkr_reconciliation.py


from apps.api.app.models import IbkrFill
from sqlalchemy.orm import Session
from sqlalchemy import select
from apps.worker.app.engine.ibkr_client import get_ibkr_trades
from apps.api.app.services.exchange_secrets import get_decrypted_exchange_secret

# --- Provider de fills para reconciliación IBKR ---
def get_ibkr_reconciliation_source(
    execution_ref: str,
    user_id: str,
    account_id: str,
    db: Session,
    mode: str = "dummy_db",
):
    """
    Obtiene fills reconciliables para IBKR según el provider especificado.
    Por ahora solo soporta mode="dummy_db" (Postgres local).
    Futuro: mode="ibkr_real" (no implementado).
    """
    if mode == "dummy_db":
        fills = db.execute(
            select(IbkrFill)
            .where(
                IbkrFill.execution_ref == execution_ref,
                IbkrFill.user_id == user_id,
                IbkrFill.broker == "ibkr"
            )
        ).scalars().all()
        return fills
    elif mode == "ibkr_real":
        # Provider real: llama al bridge IBKR y transforma los trades a fills reconciliables
        try:
            creds = get_decrypted_exchange_secret(db=db, user_id=user_id, exchange="IBKR")
            if not creds:
                raise RuntimeError("No IBKR credentials for user")
            # Para obtener symbol necesitamos buscar el fill local o rechazar si no existe
            local_fills = db.execute(
                select(IbkrFill)
                .where(
                    IbkrFill.execution_ref == execution_ref,
                    IbkrFill.user_id == user_id,
                    IbkrFill.broker == "ibkr"
                )
            ).scalars().all()
            if not local_fills:
                raise RuntimeError("No local fills found for execution_ref; cannot infer symbol for bridge call")
            symbol = local_fills[0].symbol
            # Llama al bridge
            result = get_ibkr_trades(
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                symbol=symbol,
                client_order_id=execution_ref,
            )
            trades = result.get("trades", [])
            # Validación: si la respuesta es dummy/stub, lanzar error explícito
            if (
                result.get("mode") == "ibkr_trades_seam"
                or any(trade.get("trade_id") == "DUMMY_TRADE_ID" for trade in trades)
            ):
                raise RuntimeError("ibkr_real_provider_not_ready: bridge returned stub/dummy data")
            # Transformar trades a shape de fill reconciliable (no persistir)
            fills = []
            for trade in trades:
                fills.append(type("BridgeFill", (), {
                    "fill_id": trade.get("trade_id"),
                    "execution_ref": execution_ref,
                    "symbol": trade.get("symbol"),
                    "qty": trade.get("qty"),
                    "price": trade.get("price"),
                    "timestamp": trade.get("timestamp"),
                    "user_id": user_id,
                    "broker": "ibkr"
                })())
            return fills
        except Exception as exc:
            raise RuntimeError(f"ibkr_real_provider_error: {exc}")
    else:
        raise ValueError(f"Modo de reconciliación IBKR no soportado: {mode}")

# --- Lógica de reconciliación IBKR ---
def reconcile_ibkr_fills(fills, expected_qty=None):
    """
    Reconciles IBKR fills and determines status based on expected_qty:
    - If no fills: status = not_found
    - If expected_qty is None: status = filled if total_qty > 0 else not_found
    - If expected_qty is set:
        - status = not_found if total_qty == 0
        - status = partial if 0 < total_qty < expected_qty
        - status = filled if total_qty >= expected_qty
    """
    if not fills:
        return {
            "status": "not_found",
            "total_qty": 0,
            "avg_price": None,
            "fills": []
        }
    total_qty = sum(f.qty for f in fills)
    avg_price = sum(f.qty * f.price for f in fills) / total_qty if total_qty > 0 else None
    if expected_qty is None:
        status = "filled" if total_qty > 0 else "not_found"
    else:
        if total_qty == 0:
            status = "not_found"
        elif total_qty < expected_qty:
            status = "partial"
        else:
            status = "filled"
    return {
        "status": status,
        "total_qty": total_qty,
        "avg_price": avg_price,
        "fills": [
            {
                "fill_id": f.fill_id,
                "symbol": f.symbol,
                "qty": f.qty,
                "price": f.price,
                "timestamp": f.timestamp,
                "user_id": f.user_id,
                "broker": f.broker,
                "execution_ref": f.execution_ref
            }
            for f in fills
        ]
    }
