from __future__ import annotations

from typing import Any

from apps.worker.app.engine.binance_client import cancel_order, query_order_status, send_test_order
from apps.worker.app.engine.broker_adapter import BrokerAdapter


class BinanceBrokerAdapter(BrokerAdapter):
    def __init__(self, *, api_key: str | None = None, api_secret: str | None = None) -> None:
        self._api_key = api_key
        self._api_secret = api_secret

    def send_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        client_order_id: str | None = None,
        market: str | None = None,
    ) -> dict[str, Any]:
        return send_test_order(
            api_key=self._api_key,
            api_secret=self._api_secret,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            client_order_id=client_order_id,
            market=(market or "SPOT"),
        )

    def query_order(
        self,
        *,
        symbol: str,
        client_order_id: str | None = None,
        broker_order_id: str | None = None,
        market: str | None = None,
    ) -> dict[str, Any]:
        _ = broker_order_id
        return query_order_status(
            api_key=self._api_key,
            api_secret=self._api_secret,
            symbol=symbol,
            orig_client_order_id=(client_order_id or ""),
            market=(market or "SPOT"),
        )


    def cancel_order(
        self,
        *,
        symbol: str,
        client_order_id: str | None = None,
        market: str = "SPOT",
        **kwargs,
    ):
        if client_order_id is None:
            client_order_id = kwargs.get("orig_client_order_id")

        if client_order_id is None:
            raise ValueError("client_order_id is required")

        resolved_api_key = kwargs.get("api_key") or self._api_key
        resolved_api_secret = kwargs.get("api_secret") or self._api_secret
        client = getattr(self, "binance_client", None)

        if client is not None:
            return client.cancel_order(
                api_key=resolved_api_key,
                api_secret=resolved_api_secret,
                symbol=symbol,
                orig_client_order_id=(client_order_id or ""),
                market=market,
            )

        return cancel_order(
            api_key=resolved_api_key,
            api_secret=resolved_api_secret,
            symbol=symbol,
            orig_client_order_id=(client_order_id or ""),
            market=market,
        )
