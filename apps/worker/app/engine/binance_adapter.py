from __future__ import annotations

from typing import Any

from apps.worker.app.engine.binance_client import cancel_order, query_order_status, send_test_order
from apps.worker.app.engine.broker_adapter import BrokerAdapter


class BinanceBrokerAdapter(BrokerAdapter):
    def __init__(self, *, api_key: str, api_secret: str) -> None:
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
        client_order_id: str,
        market: str = "SPOT",
        **kwargs,
    ):
        return cancel_order(
            api_key=self.api_key,
            api_secret=self.api_secret,
            symbol=symbol,
            orig_client_order_id=(client_order_id or ""),
            market=market,
        )
