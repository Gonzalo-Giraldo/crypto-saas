import json
from decimal import Decimal, InvalidOperation
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from sqlalchemy.exc import IntegrityError

from apps.api.app.core.config import settings
from apps.api.app.models.binance_fill import BinanceFill


def _to_decimal(value):
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _fetch_historical_usdt_price(symbol: str, timestamp_ms: int):
    sym = str(symbol or "").upper().strip()
    if not sym:
        return None

    start_time = int(timestamp_ms) - 60_000
    end_time = int(timestamp_ms) + 60_000
    params = {
        "symbol": sym,
        "interval": "1m",
        "limit": 3,
        "startTime": start_time,
        "endTime": end_time,
    }

    rows = None
    gateway_enabled = bool(settings.BINANCE_GATEWAY_ENABLED and settings.BINANCE_GATEWAY_BASE_URL)

    if gateway_enabled:
        try:
            base = settings.BINANCE_GATEWAY_BASE_URL.rstrip("/")
            payload = {
                "symbol": sym,
                "interval": "1m",
                "limit": 3,
                "market": "SPOT",
                "start_time_ms": start_time,
                "end_time_ms": end_time,
            }
            req = urllib_request.Request(
                f"{base}/binance/klines",
                method="POST",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            if settings.BINANCE_GATEWAY_TOKEN:
                req.add_header("X-Internal-Token", settings.BINANCE_GATEWAY_TOKEN)
            with urllib_request.urlopen(req, timeout=max(3, int(settings.BINANCE_GATEWAY_TIMEOUT_SECONDS))) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            got = body.get("rows") if isinstance(body, dict) else None
            if isinstance(got, list):
                rows = got
        except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError, json.JSONDecodeError, ValueError):
            rows = None

    if rows is None:
        try:
            base = (settings.BINANCE_SPOT_BASE_URL or settings.BINANCE_TESTNET_BASE_URL or "https://api.binance.com").rstrip("/")
            url = f"{base}/api/v3/klines?{urllib_parse.urlencode(params)}"
            req = urllib_request.Request(url, method="GET")
            with urllib_request.urlopen(req, timeout=6) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            rows = body if isinstance(body, list) else []
        except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError, json.JSONDecodeError):
            rows = []

    for row in rows or []:
        if not isinstance(row, list) or len(row) < 7:
            continue
        open_time = int(row[0])
        close_time = int(row[6])
        if open_time <= int(timestamp_ms) <= close_time:
            return _to_decimal(row[4])

    return None


def _commission_values_usdt(fill: dict):
    commission = _to_decimal(fill.get("commission"))
    asset = str(fill.get("commissionAsset") or "").upper().strip()
    executed_at_ms = fill.get("time")

    if commission is None or not asset:
        return None, None

    if asset == "USDT":
        return Decimal("1"), commission

    if executed_at_ms is None:
        return None, None

    price = _fetch_historical_usdt_price(f"{asset}USDT", int(executed_at_ms))
    if price is None:
        return None, None

    return price, commission * price


def persist_binance_fills_db(db, fills: list, user_id: str, account_id: str, broker: str, market: str):
    inserted = 0
    skipped = 0

    for fill in fills:
        trade_id = fill.get("id") or fill.get("tradeId")
        if trade_id is not None:
            trade_id = str(trade_id)
        if not trade_id:
            continue

        exists = db.query(BinanceFill).filter_by(
            user_id=user_id,
            account_id=account_id,
            broker=broker,
            market=market,
            trade_id=trade_id
        ).first()

        if exists:
            skipped += 1
            continue

        raw_side = fill.get("side")
        if raw_side is None and "isBuyer" in fill:
            raw_side = "BUY" if bool(fill.get("isBuyer")) else "SELL"

        commission_price_usdt, commission_usdt = _commission_values_usdt(fill)

        obj = BinanceFill(
            user_id=user_id,
            account_id=account_id,
            broker=broker,
            market=market,
            trade_id=trade_id,
            order_id=fill.get("orderId"),
            symbol=fill.get("symbol"),
            side=raw_side,
            raw_payload=fill,
            price=fill.get("price"),
            qty=fill.get("qty"),
            quote_qty=fill.get("quoteQty"),
            commission=fill.get("commission"),
            commission_asset=fill.get("commissionAsset"),
            commission_price_usdt=commission_price_usdt,
            commission_usdt=commission_usdt,
            executed_at_ms=fill.get("time"),
        )

        db.add(obj)

        try:
            db.commit()
            inserted += 1
        except IntegrityError:
            db.rollback()
            skipped += 1

    return {"inserted": inserted, "skipped": skipped}
