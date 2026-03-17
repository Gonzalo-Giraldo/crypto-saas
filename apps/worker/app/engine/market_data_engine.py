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
            def update_binance_price(self, user_id: str, symbol: str, adapter):
                """
                Trigger manual explícito para actualizar el precio de un símbolo de Binance para un usuario.
                Llama fetch_and_cache_binance_price y retorna el PriceQuote actualizado o None si falla.
                """
    def update_binance_price(self, user_id: str, symbol: str, adapter):
        """
        Trigger manual explícito para actualizar el precio de un símbolo de Binance para un usuario.
        Llama fetch_and_cache_binance_price y retorna el PriceQuote actualizado o None si falla (contrato original).
        """
        ok = self.fetch_and_cache_binance_price(user_id, symbol, adapter)
        if not ok:
            return None
        price_obj = self.get_price(user_id, "binance", symbol)
        if not price_obj or not hasattr(price_obj, "price") or price_obj.price is None:
            return None
        return price_obj
        def fetch_and_cache_binance_price(self, user_id: str, symbol: str, adapter) -> bool:
            """
            Obtiene el precio spot de Binance vía adapter y lo almacena en cache para el usuario.
            Retorna True si se actualizó el cache, False si falló.
            """
    def fetch_and_cache_binance_price(self, user_id: str, symbol: str, adapter) -> bool:
        """
        Obtiene el precio spot de Binance vía adapter y lo almacena en cache para el usuario.
        Retorna True si se actualizó el cache, False si falló (fallo explícito, no propaga None ambiguo).
        """
        quote = adapter.fetch_symbol_price(symbol)
        if not quote or not isinstance(quote, dict) or "price" not in quote or quote["price"] is None:
            # No actualiza cache si fetch falla o el precio es inválido
            return False
        self.set_price(
            user_id=user_id,
            broker="binance",
            symbol=symbol,
            price=quote["price"],
            timestamp=quote.get("timestamp"),
            metadata=quote.get("metadata")
        )
        return True
    def get_price_value(self, user_id: str, broker: str, symbol: str, now_ts: Optional[float] = None) -> Optional[float]:
        quote = self.get_fresh_price(user_id, broker, symbol, now_ts=now_ts)
        if not quote or not hasattr(quote, "price") or quote.price is None:
            return None
        return quote.price

    price_ttl_seconds = 30

    def __init__(self):
        self._state = MarketDataState()

    def is_price_stale(self, user_id: str, broker: str, symbol: str, now_ts: Optional[float] = None) -> bool:
        quote = self.get_price(user_id, broker, symbol)
        if not quote or not hasattr(quote, "timestamp") or quote.timestamp is None:
            return True
        now = now_ts if now_ts is not None else time.time()
        return (now - quote.timestamp) > self.price_ttl_seconds

    def get_fresh_price(self, user_id: str, broker: str, symbol: str, now_ts: Optional[float] = None) -> Optional[PriceQuote]:
        if self.is_price_stale(user_id, broker, symbol, now_ts=now_ts):
            return None
        return self.get_price(user_id, broker, symbol)

    def get_stale_symbols(self, user_id: Optional[str] = None, broker: Optional[str] = None, now_ts: Optional[float] = None) -> list:
        stale = set()
        now = now_ts if now_ts is not None else time.time()
        state = self._state.state
        if user_id is not None:
            user_brokers = state.get(user_id, {})
            if broker is not None:
                broker_quotes = user_brokers.get(broker, {})
                for symbol, quote in broker_quotes.items():
                    if not quote or not hasattr(quote, "timestamp") or quote.timestamp is None or (now - quote.timestamp) > self.price_ttl_seconds:
                        stale.add(symbol)
            else:
                for b_quotes in user_brokers.values():
                    for symbol, quote in b_quotes.items():
                        if not quote or not hasattr(quote, "timestamp") or quote.timestamp is None or (now - quote.timestamp) > self.price_ttl_seconds:
                            stale.add(symbol)
        else:
            for user_brokers in state.values():
                for b_quotes in user_brokers.values():
                    for symbol, quote in b_quotes.items():
                        if not quote or not hasattr(quote, "timestamp") or quote.timestamp is None or (now - quote.timestamp) > self.price_ttl_seconds:
                            stale.add(symbol)
        return list(stale)

    def set_price(self, user_id: str, broker: str, symbol: str, price: float, timestamp: Optional[float] = None, metadata: Optional[dict] = None):
        self._state.set_price(user_id, broker, symbol, price, timestamp, metadata)

    def get_price(self, user_id: str, broker: str, symbol: str) -> Optional[PriceQuote]:
        return self._state.get_price(user_id, broker, symbol)

    def get_user_prices(self, user_id: str, broker: Optional[str] = None) -> Dict[str, PriceQuote]:
        return self._state.get_user_prices(user_id, broker)

    def get_global_symbol_prices(self, symbol: str) -> List[PriceQuote]:
        return self._state.get_global_symbol_prices(symbol)
