import json
import os
from typing import Any, Callable, Optional

from cryptography.hazmat.primitives import serialization

from apps.binance_ws.binance_ws_api_client import BinanceWsApiClient
from apps.binance_ws.run_ws_controlled_session import run_controlled_ws_session


class DryRunDb:
    """
    Minimal read-only fake DB adapter for WS dry-run.

    It intentionally returns no existing trade IDs and performs no writes.
    """

    def execute(self, query: Any, params: Optional[dict[str, Any]] = None):
        return []


def dry_run_noop_fill_writer(**kwargs: Any) -> None:
    """
    Dry-run persistence callable.

    It intentionally does not write to DB, does not commit and does not mutate external state.
    """
    return None


def load_ed25519_private_key_from_env(env_var: str = "BINANCE_WS_ED25519_PRIVATE_KEY") -> Any:
    raw = os.environ.get(env_var)
    if not raw:
        raise RuntimeError(f"{env_var} is required")

    private_key_text = raw.replace("\\n", "\n").strip().encode("utf-8")

    return serialization.load_pem_private_key(
        private_key_text,
        password=None,
    )


def build_real_ws_client_from_env(
    *,
    client_factory: Optional[Callable[..., BinanceWsApiClient]] = None,
) -> BinanceWsApiClient:
    api_key = os.environ.get("BINANCE_WS_API_KEY")
    if not api_key:
        raise RuntimeError("BINANCE_WS_API_KEY is required")

    private_key = load_ed25519_private_key_from_env()

    factory = client_factory or BinanceWsApiClient

    return factory(
        api_key=api_key,
        private_key=private_key,
    )


def run_real_ws_controlled_session_dry_run(
    *,
    max_messages: int,
    user_id: str,
    account_id: str,
    client_factory: Optional[Callable[..., BinanceWsApiClient]] = None,
) -> dict[str, Any]:
    if max_messages is None or max_messages <= 0:
        raise ValueError("max_messages must be > 0")

    ws_client = build_real_ws_client_from_env(client_factory=client_factory)

    return run_controlled_ws_session(
        ws_client=ws_client,
        db=DryRunDb(),
        user_id=user_id,
        account_id=account_id,
        persist_binance_fills_db_callable=dry_run_noop_fill_writer,
        max_messages=max_messages,
    )


def main() -> None:
    max_messages = int(os.environ.get("BINANCE_WS_MAX_MESSAGES", "5"))
    user_id = os.environ.get(
        "BINANCE_WS_USER_ID",
        "4687a88b-9a84-4277-8fdf-26b5dc7c8096",
    )
    account_id = os.environ.get("BINANCE_WS_ACCOUNT_ID", "default")

    result = run_real_ws_controlled_session_dry_run(
        max_messages=max_messages,
        user_id=user_id,
        account_id=account_id,
    )

    print("WS_CONTROLLED_SESSION_DRY_RUN_RESULT")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
