import uuid


def generate_internal_ibkr_intent_key(
    *,
    user_id: str | None,
    account_id: str | None,
    symbol: str | None,
    side: str | None,
) -> str:
    """
    Genera un intent_key interno para el flujo directo IBKR.
    No reutiliza X-Idempotency-Key.
    """
    uid = str(user_id or "").strip() or "no-user"
    acc = str(account_id or "").strip() or "no-account"
    sym = str(symbol or "").strip().upper() or "NO-SYMBOL"
    sde = str(side or "").strip().upper() or "NO-SIDE"
    return f"ibkr-intent::{uid}::{acc}::{sym}::{sde}::{uuid.uuid4().hex}"
