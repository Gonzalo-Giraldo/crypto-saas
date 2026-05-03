from typing import Any, Callable, Iterable, Dict, List

from apps.binance_ws.controlled_user_data_listener import process_user_data_messages


def run_controlled_ws_batch(
    *,
    db: Any,
    messages: Iterable[Dict],
    user_id: str,
    account_id: str,
    persist_binance_fills_db_callable: Callable[..., Any],
    max_messages: int = 50,
) -> Dict[str, Any]:
    """
    Ejecuta un batch controlado de mensajes event stream (ya recibidos externamente).

    NO:
    - abre 
    - ejecuta trading
    - hace loop infinito
    - hace commit directo
    """

    batch = []
    count = 0

    for msg in messages:
        if count >= max_messages:
            break
        batch.append(msg)
        count += 1

    if not batch:
        return {
            "received": 0,
            "processed": 0,
            "inserted_candidate_count": 0,
            "skipped_existing_count": 0,
            "results": [],
        }

    result = process_user_data_messages(
        db=db,
        messages=batch,
        user_id=user_id,
        account_id=account_id,
        persist_binance_fills_db_callable=persist_binance_fills_db_callable,
        max_messages=max_messages,
    )

    return result
