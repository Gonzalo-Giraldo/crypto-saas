"""
Binance Market Data Adapter groundwork: interface and normalization only.
No API calls, no runtime wiring, no external dependencies.
"""

import time

class BinanceMarketDataAdapter:
    def __init__(self):
        pass

    def normalize_price_response(self, symbol, payload):
        # Accepts Binance ticker payload, extracts price, normalizes output
        try:
            # Binance REST ticker price: {"symbol": "BTCUSDT", "price": "68000.00"}
            price_str = payload.get("price")
            if price_str is None:
                return None
            price = float(price_str)
            return {
                "symbol": symbol,
                "price": price,
                "broker": "binance"
            }
        except Exception:
            return None

    def build_price_quote(self, symbol, price, timestamp=None, metadata=None):
        return {
            "symbol": symbol,
            "price": price,
            "broker": "binance",
            "timestamp": timestamp if timestamp is not None else time.time(),
            "metadata": metadata or {}
        }

    def fetch_symbol_price(self, symbol):
        # Consulta REST a Binance para obtener el precio spot
        import urllib.request
        import json
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol.upper()}"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = response.read()
                payload = json.loads(data)
            norm = self.normalize_price_response(symbol, payload)
            if not norm:
                return None
            return self.build_price_quote(
                symbol=norm["symbol"],
                price=norm["price"],
                metadata={"raw": payload}
            )
        except Exception:
            return None
