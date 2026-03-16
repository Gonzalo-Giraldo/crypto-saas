from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BrokerAdapter(ABC):
    """Minimal broker-agnostic contract for order send/query operations."""

    @abstractmethod
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
        """Send an order to a broker and return a broker-specific response payload."""

    @abstractmethod
    def query_order(
        self,
        *,
        symbol: str,
        client_order_id: str | None = None,
        broker_order_id: str | None = None,
        market: str | None = None,
    ) -> dict[str, Any]:
        """Query order state by broker/client identifier and return raw status payload."""

    @abstractmethod
    def cancel_order(
        self,
        *,
        symbol: str,
        client_order_id: str,
        market: str = "SPOT",
        **kwargs
    ) -> dict[str, Any]:
        """Cancel an order by client_order_id and return broker-specific response payload."""
        raise NotImplementedError("BrokerAdapter.cancel_order must be implemented by subclasses.")
