from typing import Any, Callable

from apps.binance_ws.controlled_user_data_listener import process_user_data_messages


def run_controlled_ws_session(
    *,
    ws_client,
    db,
    user_id: str,
    account_id: str,
    persist_binance_fills_db_callable: Callable[..., dict[str, Any] | None],
    max_messages: int,
) -> dict[str, Any]:
    if max_messages is None or max_messages <= 0:
        raise ValueError("max_messages must be > 0")

    messages: list[dict[str, Any]] = []
    errors: list[str] = []

    for _ in range(max_messages):
        try:
            msg = ws_client.receive()
            messages.append(msg)
        except Exception as exc:
            errors.append(str(exc))

    result = process_user_data_messages(
        db=db,
        messages=messages,
        user_id=user_id,
        account_id=account_id,
        persist_binance_fills_db_callable=persist_binance_fills_db_callable,
        max_messages=max_messages,
    )

    result["errors"].extend(errors)

    return result
