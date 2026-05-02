import json
from urllib import request as urllib_request, error as urllib_error

from apps.api.app.core.config import settings


def fetch_binance_ticker_price(symbol: str, market: str = "SPOT") -> dict:
    if not (settings.BINANCE_GATEWAY_ENABLED and settings.BINANCE_GATEWAY_BASE_URL):
        raise RuntimeError("binance_gateway_not_configured")

    symbol_norm = str(symbol or "").upper().strip()
    market_norm = str(market or "").upper().strip()

    if not symbol_norm:
        raise ValueError("symbol_required")

    if market_norm not in {"SPOT", "FUTURES"}:
        raise ValueError("market_must_be_SPOT_or_FUTURES")

    url = f"{settings.BINANCE_GATEWAY_BASE_URL.rstrip('/')}/binance/ticker-price"

    payload = json.dumps({
        "symbol": symbol_norm,
        "market": market_norm,
    }).encode("utf-8")

    req = urllib_request.Request(
        url,
        method="POST",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    if settings.BINANCE_GATEWAY_TOKEN:
        req.add_header("X-Internal-Token", settings.BINANCE_GATEWAY_TOKEN)

    try:
        with urllib_request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        raise RuntimeError(f"binance_gateway_http_error:{exc.code}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"binance_gateway_url_error:{exc.reason}") from exc
    except Exception:
        raise RuntimeError("binance_gateway_unknown_error")

    if not isinstance(data, dict):
        raise RuntimeError("invalid_ticker_response")

    row = data.get("row")
    if not isinstance(row, dict):
        raise RuntimeError("ticker_row_missing")

    if "price" not in row:
        raise RuntimeError("ticker_price_missing")

    return row
