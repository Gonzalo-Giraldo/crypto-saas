from __future__ import annotations

from typing import Any, Callable

from apps.worker.app.engine.binance_exit_protection_evidence_view import (
    build_exit_protection_evidence_view,
)
from apps.worker.app.engine.binance_gateway_executor import (
    fetch_algo_order_status_via_gateway,
)


def build_exit_protection_shadow_view(
    *,
    api_key: str,
    api_secret: str,
    symbol: str,
    sl_algo_id: int | None = None,
    sl_client_algo_id: str | None = None,
    tp_algo_id: int | None = None,
    tp_client_algo_id: str | None = None,
    post: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    sl_status_fetch = fetch_algo_order_status_via_gateway(
        api_key=api_key,
        api_secret=api_secret,
        symbol=symbol,
        algo_id=sl_algo_id,
        client_algo_id=sl_client_algo_id,
        post=post,
    )

    tp_status_fetch = fetch_algo_order_status_via_gateway(
        api_key=api_key,
        api_secret=api_secret,
        symbol=symbol,
        algo_id=tp_algo_id,
        client_algo_id=tp_client_algo_id,
        post=post,
    )

    evidence_view = build_exit_protection_evidence_view(
        sl_payload=sl_status_fetch.get("response") or sl_status_fetch.get("data"),
        tp_payload=tp_status_fetch.get("response") or tp_status_fetch.get("data"),
    )

    return {
        "shadow_mode": True,
        "sl_status_fetch": sl_status_fetch,
        "tp_status_fetch": tp_status_fetch,
        "evidence_view": evidence_view,
        "authority_granted": False,
        "runtime_action_allowed": False,
    }
