import json
from urllib import error as urllib_error
from urllib import request as urllib_request

from apps.api.app.core.config import settings


def fetch_binance_trades(
    *,
    api_key: str,
    api_secret: str,
    symbol: str,
    market: str,
    start_time_ms: int = None,   # 🔴 NUEVO
):
    if not (settings.BINANCE_GATEWAY_ENABLED and settings.BINANCE_GATEWAY_BASE_URL):
        raise RuntimeError("binance_gateway_not_configured")

    api_key_norm = str(api_key or "").strip()
    api_secret_norm = str(api_secret or "").strip()
    symbol_norm = str(symbol or "").upper().strip()
    market_norm = str(market or "").upper().strip()

    if not api_key_norm:
        raise ValueError("api_key_required")
    if not api_secret_norm:
        raise ValueError("api_secret_required")
    if not symbol_norm:
        raise ValueError("symbol_required")
    if market_norm not in {"SPOT", "FUTURES"}:
        raise ValueError("market_must_be_SPOT_or_FUTURES")

    url = f"{settings.BINANCE_GATEWAY_BASE_URL.rstrip('/')}/binance/my-trades"

    payload_dict = {
        "api_key": api_key_norm,
        "api_secret": api_secret_norm,
        "symbol": symbol_norm,
        "market": market_norm,
    }

# 🔴 NUEVO
    if start_time_ms is not None:
        payload_dict["start_time_ms"] = int(start_time_ms)

    payload = json.dumps(payload_dict).encode("utf-8")

    req = urllib_request.Request(
        url,
        method="POST",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    if settings.BINANCE_GATEWAY_TOKEN:
        req.add_header("X-Internal-Token", settings.BINANCE_GATEWAY_TOKEN)

    timeout_seconds = max(3, int(settings.BINANCE_GATEWAY_TIMEOUT_SECONDS))

    try:
        with urllib_request.urlopen(req, timeout=timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        raise RuntimeError(f"binance_gateway_http_error:{exc.code}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"binance_gateway_url_error:{exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("binance_gateway_timeout") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("binance_gateway_invalid_json") from exc

    if isinstance(data, dict):
        rows = data.get("rows")
        if rows is None:
            return []
        if not isinstance(rows, list):
            raise RuntimeError("binance_gateway_rows_must_be_list")
        return rows

    if isinstance(data, list):
        return data

    raise RuntimeError("binance_gateway_payload_must_be_dict_or_list")
