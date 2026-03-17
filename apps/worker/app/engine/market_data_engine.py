"""
Market Data Engine groundwork: in-memory SaaS-aware state and query interface.
No API connections, no polling, no streams, no persistence.
"""

from typing import Optional, Dict, Any, List
import time

class PriceQuote:
    def __init__(self, symbol: str, price: float, broker: str, timestamp: Optional[float] = None, metadata: Optional[dict] = None):
        self.symbol = symbol
        self.price = price
        self.broker = broker
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.metadata = metadata or {}

class MarketDataState:
    def __init__(self):
        # user_id -> broker -> symbol -> PriceQuote
        self.state: Dict[str, Dict[str, Dict[str, PriceQuote]]] = {}

    def set_price(self, user_id: str, broker: str, symbol: str, price: float, timestamp: Optional[float] = None, metadata: Optional[dict] = None):
        self.state.setdefault(user_id, {}).setdefault(broker, {})[symbol] = PriceQuote(symbol, price, broker, timestamp, metadata)

    def get_price(self, user_id: str, broker: str, symbol: str) -> Optional[PriceQuote]:
        return self.state.get(user_id, {}).get(broker, {}).get(symbol)

    def get_user_prices(self, user_id: str, broker: Optional[str] = None) -> Dict[str, PriceQuote]:
        result = {}
        user_brokers = self.state.get(user_id, {})
        if broker is not None:
            broker_quotes = user_brokers.get(broker, {})
            result.update(broker_quotes)
        else:
            for b_quotes in user_brokers.values():
                result.update(b_quotes)
        return result

    def get_global_symbol_prices(self, symbol: str) -> List[PriceQuote]:
        quotes = []
        for user_brokers in self.state.values():
            for broker_quotes in user_brokers.values():
                quote = broker_quotes.get(symbol)
                if quote:
                    quotes.append(quote)
        return quotes

class MarketDataEngine:
    def __init__(self):
        self._state = MarketDataState()

    def set_price(self, user_id: str, broker: str, symbol: str, price: float, timestamp: Optional[float] = None, metadata: Optional[dict] = None):
        self._state.set_price(user_id, broker, symbol, price, timestamp, metadata)

    def get_price(self, user_id: str, broker: str, symbol: str) -> Optional[PriceQuote]:
        return self._state.get_price(user_id, broker, symbol)

    def get_user_prices(self, user_id: str, broker: Optional[str] = None) -> Dict[str, PriceQuote]:
        return self._state.get_user_prices(user_id, broker)

    def get_global_symbol_prices(self, symbol: str) -> List[PriceQuote]:
        return self._state.get_global_symbol_prices(symbol)
