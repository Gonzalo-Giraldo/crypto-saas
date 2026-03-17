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
        """
        Consulta REST a Binance para obtener el precio spot.
        Endurecido: maneja timeout, HTTPError, URLError, JSONDecodeError, symbol/precio inválido.
        Retorna None ante cualquier fallo o respuesta inesperada.
        """
        import urllib.request
        import urllib.error
        import json
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol.upper()}"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = response.read()
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    return None
        except urllib.error.HTTPError:
            # 4xx/5xx de Binance
            return None
        except urllib.error.URLError:
            # Problemas de red, timeout, DNS, etc.
            return None
        except TimeoutError:
            return None
        except Exception:
            return None

        # Validar payload esperado
        if not isinstance(payload, dict):
            return None
        norm = self.normalize_price_response(symbol, payload)
        if not norm:
            return None
        # Validar symbol y precio presentes
        if not norm.get("symbol") or norm.get("price") is None:
            return None
        return self.build_price_quote(
            symbol=norm["symbol"],
            price=norm["price"],
            metadata={"raw": payload}
        )
