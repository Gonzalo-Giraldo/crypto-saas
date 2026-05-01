from sqlalchemy import text

from apps.api.app.db.session import SessionLocal
from apps.api.app.services.audit import log_audit_event
from apps.api.app.services.binance_fill_db import persist_binance_fills_db
from apps.api.app.services.binance_fill_manual_runner import run_binance_fill_ingestion_for_intent
from apps.api.app.services.binance_trades_gateway_client import fetch_binance_trades
from apps.api.app.services.exchange_secrets import get_decrypted_exchange_secret


def run_binance_fill_backfill(*, limit: int = 50) -> dict:
    db = SessionLocal()
    scanned = 0
    completed = 0
    skipped = 0
    errors = 0

    try:
        rows = db.execute(text("""
            SELECT
                i.intent_id,
                i.expected_qty,
                ic.execution_ref,
                ic.broker_execution_id_type,
                ic.symbol,
                ic.market,
                split_part(ic.consumer, ':', 1) AS user_id,
                NULLIF(split_part(ic.consumer, ':', 3), 'no-account') AS account_id
            FROM intents i
            JOIN intent_consumptions ic ON ic.intent_id = i.intent_id::text
            LEFT JOIN binance_fills bf
              ON bf.order_id = ic.execution_ref
             AND bf.symbol = ic.symbol
            WHERE i.lifecycle_status = 'EXECUTED'
              AND ic.execution_ref IS NOT NULL
              AND ic.broker_execution_id_type = 'orderId'
              AND ic.symbol IS NOT NULL
              AND ic.market IN ('SPOT', 'FUTURES')
            GROUP BY
                i.intent_id,
                i.expected_qty,
                ic.execution_ref,
                ic.broker_execution_id_type,
                ic.symbol,
                ic.market,
                ic.consumer
            HAVING COUNT(bf.id) = 0
   OR ABS(COALESCE(SUM(bf.qty), 0) - i.expected_qty) > 0.00000001
            LIMIT :limit
        """), {"limit": int(limit)}).fetchall()

        for r in rows:
            scanned += 1
            user_id = str(r.user_id or "").strip()
            account_id = str(r.account_id or "no-account").strip()

            try:
                if not user_id:
                    skipped += 1
                    continue

                creds = get_decrypted_exchange_secret(
                    db=db,
                    user_id=user_id,
                    exchange="BINANCE",
                )
                if not creds:
                    skipped += 1
                    continue

                result = run_binance_fill_ingestion_for_intent(
                    db=db,
                    intent_id=str(r.intent_id),
                    symbol=str(r.symbol),
                    order_id=str(r.execution_ref),
                    execution_ref_type="orderId",
                    user_id=user_id,
                    account_id=account_id,
                    market=str(r.market),
                    expected_qty=r.expected_qty,
                    gateway_fetch_trades=lambda symbol, order_id, creds=creds, market=str(r.market): fetch_binance_trades(
                        api_key=creds["api_key"],
                        api_secret=creds["api_secret"],
                        symbol=symbol,
                        market=market,
                    ),
                    persist_binance_fills_db=persist_binance_fills_db,
                    persist=True,
                )

                log_audit_event(
                    db,
                    action="execution.binance.fill_backfill.completed",
                    user_id=user_id,
                    entity_type="execution",
                    details=result,
                )
                db.commit()
                completed += 1

            except Exception as exc:
                db.rollback()
                errors += 1
                try:
                    log_audit_event(
                        db,
                        action="execution.binance.fill_backfill.error",
                        user_id=user_id or None,
                        entity_type="execution",
                        details={
                            "intent_id": str(getattr(r, "intent_id", "")),
                            "order_id": str(getattr(r, "execution_ref", "")),
                            "symbol": str(getattr(r, "symbol", "")),
                            "market": str(getattr(r, "market", "")),
                            "error": str(exc),
                        },
                    )
                    db.commit()
                except Exception:
                    db.rollback()

        return {
            "scanned": scanned,
            "completed": completed,
            "skipped": skipped,
            "errors": errors,
        }
    finally:
        db.close()
