# apps/api/app/services/ibkr_reconciliation.py


from apps.api.app.models import IbkrFill
from sqlalchemy.orm import Session
from sqlalchemy import select, text
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
        try:
            creds = get_decrypted_exchange_secret(db=db, user_id=user_id, exchange="IBKR")
            if not creds:
                raise RuntimeError("No IBKR credentials for user")

            row = db.execute(
                text("""
                SELECT symbol
                FROM intent_consumptions
                WHERE execution_ref = :execution_ref
                  AND consumer LIKE :consumer
                LIMIT 1
                """),
                {
                    "execution_ref": execution_ref,
                    "consumer": f"{user_id}:IBKR:%"
                }
            ).fetchone()

            if not row or not row.symbol:
                raise RuntimeError("symbol_not_found_in_intent_consumptions")

            symbol = row.symbol

            result = get_ibkr_trades(
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                symbol=symbol,
                client_order_id=execution_ref,
            )

            trades = result.get("trades", [])

            fills = []
            for t in trades:
                fills.append(type("BridgeFill", (), {
                    "fill_id": t.get("fill_id"),
                    "execution_ref": t.get("execution_ref") or execution_ref,
                    "symbol": t.get("symbol"),
                    "qty": t.get("qty"),
                    "price": t.get("price"),
                    "timestamp": t.get("timestamp"),
                    "user_id": user_id,
                    "broker": "ibkr"
                })())

            return fills

        except Exception as exc:
            raise RuntimeError(f"ibkr_real_provider_error: {exc}")
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


def persist_ibkr_fills(db, fills):
    inserted = 0
    skipped = 0
    total = 0

    for f in fills:
        total += 1

        fill_id = getattr(f, "fill_id", None)
        execution_ref = getattr(f, "execution_ref", None)
        symbol = getattr(f, "symbol", None)
        qty = getattr(f, "qty", None)
        price = getattr(f, "price", None)
        timestamp = getattr(f, "timestamp", None)
        user_id = getattr(f, "user_id", None)

        if not fill_id:
            skipped += 1
            continue

        exists = db.execute(
            text("SELECT 1 FROM ibkr_fills WHERE fill_id = :fill_id LIMIT 1"),
            {"fill_id": fill_id},
        ).fetchone()

        if exists:
            skipped += 1
            continue

        db.execute(
            text("""
                INSERT INTO ibkr_fills (
                    fill_id,
                    execution_ref,
                    symbol,
                    qty,
                    price,
                    timestamp,
                    user_id,
                    broker
                ) VALUES (
                    :fill_id,
                    :execution_ref,
                    :symbol,
                    :qty,
                    :price,
                    :timestamp,
                    :user_id,
                    :broker
                )
            """),
            {
                "fill_id": fill_id,
                "execution_ref": execution_ref,
                "symbol": symbol,
                "qty": qty,
                "price": price,
                "timestamp": timestamp,
                "user_id": user_id,
                "broker": "ibkr",
            },
        )
        inserted += 1

    db.commit()

    return {"inserted": inserted, "skipped": skipped, "total": total}
