import hashlib
import hmac

from fastapi import HTTPException, status

from apps.api.app.db.session import SessionLocal
from apps.api.app.services.audit import log_audit_event
from apps.api.app.services.exchange_secrets import get_decrypted_exchange_secret
from apps.worker.app.engine.binance_client import send_test_order
from apps.worker.app.engine.ibkr_client import send_ibkr_test_order


def _mask_api_key(value: str) -> str:
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}***{value[-3:]}"


def prepare_execution_for_user(
    user_id: str,
    exchange: str,
    symbol: str,
    side: str,
    qty: float,
):
    db = SessionLocal()
    try:
        creds = get_decrypted_exchange_secret(
            db=db,
            user_id=user_id,
            exchange=exchange,
        )
        if not creds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing credentials for {exchange}",
            )

        api_key = creds["api_key"]
        api_secret = creds["api_secret"]

        # Build a deterministic dry-run signature payload without exposing raw secrets.
        payload = f"{exchange}|{symbol}|{side}|{qty}"
        signature = hmac.new(
            api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        log_audit_event(
            db,
            action="execution.prepare",
            user_id=user_id,
            entity_type="execution",
            details={
                "exchange": exchange,
                "symbol": symbol,
                "side": side,
                "qty": qty,
            },
        )
        db.commit()

        return {
            "mode": "dry_run",
            "exchange": exchange,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "api_key_masked": _mask_api_key(api_key),
            "signature_preview": signature[:12],
        }
    finally:
        db.close()


def execute_binance_test_order_for_user(
    user_id: str,
    symbol: str,
    side: str,
    qty: float,
):
    db = SessionLocal()
    try:
        creds = get_decrypted_exchange_secret(
            db=db,
            user_id=user_id,
            exchange="BINANCE",
        )
        if not creds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing credentials for BINANCE",
            )

        try:
            send_test_order(
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                symbol=symbol,
                side=side,
                quantity=qty,
            )
        except Exception as exc:
            log_audit_event(
                db,
                action="execution.binance.test_order.error",
                user_id=user_id,
                entity_type="execution",
                details={
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "error": str(exc),
                },
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Binance test order failed: {exc}",
            )

        log_audit_event(
            db,
            action="execution.binance.test_order.success",
            user_id=user_id,
            entity_type="execution",
            details={"symbol": symbol, "side": side, "qty": qty},
        )
        db.commit()

        return {
            "exchange": "BINANCE",
            "mode": "testnet_order_test",
            "symbol": symbol.upper(),
            "side": side.upper(),
            "qty": qty,
            "sent": True,
        }
    finally:
        db.close()


def execute_ibkr_test_order_for_user(
    user_id: str,
    symbol: str,
    side: str,
    qty: float,
):
    db = SessionLocal()
    try:
        creds = get_decrypted_exchange_secret(
            db=db,
            user_id=user_id,
            exchange="IBKR",
        )
        if not creds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing credentials for IBKR",
            )

        try:
            result = send_ibkr_test_order(
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                symbol=symbol,
                side=side,
                quantity=qty,
            )
        except Exception as exc:
            log_audit_event(
                db,
                action="execution.ibkr.test_order.error",
                user_id=user_id,
                entity_type="execution",
                details={
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "error": str(exc),
                },
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"IBKR test order failed: {exc}",
            )

        mode = "paper_bridge_test" if result.get("mode") == "bridge" else "paper_simulated_test"
        order_ref = result.get("order_ref", "")
        log_audit_event(
            db,
            action="execution.ibkr.test_order.success",
            user_id=user_id,
            entity_type="execution",
            details={"symbol": symbol, "side": side, "qty": qty, "mode": mode, "order_ref": order_ref},
        )
        db.commit()

        return {
            "exchange": "IBKR",
            "mode": mode,
            "symbol": symbol.upper(),
            "side": side.upper(),
            "qty": qty,
            "sent": True,
            "order_ref": order_ref,
        }
    finally:
        db.close()
