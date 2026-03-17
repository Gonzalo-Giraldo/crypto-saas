"""
IBKR Market Data Adapter groundwork: interface and normalization only.
No API calls, no runtime wiring, no external dependencies.
"""

import time

class IBKRMarketDataAdapter:
    def __init__(self):
        pass

    def normalize_price_response(self, symbol, payload):
        # Accepts IBKR price payload, extracts price, normalizes output
        try:
            # Example IBKR payload: {"symbol": "AAPL", "last": 180.25}
            price = payload.get("last")
            if price is None:
                return None
            price = float(price)
            return {
                "symbol": symbol,
                "price": price,
                "broker": "ibkr"
            }
        except Exception:
            return None

    def build_price_quote(self, symbol, price, timestamp=None, metadata=None):
        return {
            "symbol": symbol,
            "price": price,
            "broker": "ibkr",
            "timestamp": timestamp if timestamp is not None else time.time(),
            "metadata": metadata or {}
        }

    def fetch_symbol_price(self, symbol):
        raise NotImplementedError("IBKRMarketDataAdapter groundwork only: no network access implemented.")
