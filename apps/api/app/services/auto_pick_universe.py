from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.api.ops import (
    _binance_fallback_symbols,
    _binance_monitor_volume_floor,
    _compute_binance_mtf_signal,
    _fetch_binance_ticker_rows,
    _ibkr_fallback_symbols,
    _is_binance_directional_symbol,
    _is_binance_monitor_row_allowed,
)
from apps.api.app.models.market_trend_snapshot import MarketTrendSnapshot
from apps.api.app.schemas.pretrade import PretradeCheckRequest

def _build_auto_pick_universe(
    exchange: str,
    *,
    db: Session | None = None,
    tenant_id: str | None = None,
    direction: str = "LONG",
) -> list[PretradeCheckRequest]:
    ex = (exchange or "").upper()
    pick_direction = (direction or "LONG").upper().strip()

    def _sides_for_direction() -> list[str]:
        if pick_direction == "LONG":
            return ["BUY"]
        if pick_direction == "SHORT":
            return ["SELL"]
        # BOTH
        return ["BUY", "SELL"]

    sides = _sides_for_direction()
    if not sides:
        return []

    if ex == "IBKR":
        symbols = _ibkr_fallback_symbols()
        base_by_symbol = {
            "SPY": (0.20, 0.12, 1.8, 6.0, 8.0),
            "QQQ": (0.25, 0.15, 2.0, 7.0, 9.0),
            "IWM": (0.08, 0.05, 2.4, 8.0, 10.0),
            "AAPL": (0.22, 0.18, 2.1, 7.0, 9.0),
            "MSFT": (0.18, 0.14, 1.9, 6.0, 8.0),
            "NVDA": (0.35, 0.30, 3.2, 9.0, 12.0),
            "AMZN": (0.15, 0.10, 2.3, 7.0, 9.0),
            "META": (0.17, 0.12, 2.5, 8.0, 10.0),
            "TSLA": (0.28, 0.22, 3.8, 10.0, 13.0),
        }
        out_ibkr: list[PretradeCheckRequest] = []
        for s in symbols:
            for side in sides:
                out_ibkr.append(
                    PretradeCheckRequest(
                        symbol=s,
                        side=side,
                        qty=1.0,
                        rr_estimate=1.6,
                        trend_tf="4H",
                        signal_tf="1H",
                        timing_tf="15M",
                        spread_bps=base_by_symbol.get(s, (0.0, 0.0, 2.2, 8.0, 10.0))[3],
                        slippage_bps=base_by_symbol.get(s, (0.0, 0.0, 2.2, 8.0, 10.0))[4],
                        volume_24h_usdt=0.0,
                        in_rth=True,
                        macro_event_block=False,
                        earnings_within_24h=False,
                        market_trend_score=base_by_symbol.get(s, (0.0, 0.0, 2.2, 8.0, 10.0))[0],
                        atr_pct=base_by_symbol.get(s, (0.0, 0.0, 2.2, 8.0, 10.0))[2],
                        momentum_score=base_by_symbol.get(s, (0.0, 0.0, 2.2, 8.0, 10.0))[1],
                    )
                )
        return out_ibkr
    # Prefer the latest market-monitor bucket so auto-pick uses the same filtered universe.
    if db is not None and tenant_id:
        latest_bucket = db.execute(
            select(func.max(MarketTrendSnapshot.bucket_5m)).where(
                MarketTrendSnapshot.tenant_id == tenant_id,
                MarketTrendSnapshot.exchange == "BINANCE",
            )
        ).scalar_one_or_none()
        if latest_bucket is not None:
            snap_rows = db.execute(
                select(MarketTrendSnapshot).where(
                    MarketTrendSnapshot.tenant_id == tenant_id,
                    MarketTrendSnapshot.exchange == "BINANCE",
                    MarketTrendSnapshot.bucket_5m == latest_bucket,
                )
            ).scalars().all()
            ranked_snapshots = sorted(
                [
                    r for r in snap_rows
                    if _is_binance_monitor_row_allowed(str(r.symbol or ""), float(r.volume_24h_usdt or 0.0))
                ],
                key=lambda r: float(r.volume_24h_usdt or 0.0),
                reverse=True,
            )[:12]
            if ranked_snapshots:
                out: list[PretradeCheckRequest] = []
                for r in ranked_snapshots:
                    qv = float(r.volume_24h_usdt or 0.0)
                    liq = min(1.0, qv / 200_000_000.0)
                    spread = max(3.0, 14.0 - (10.0 * liq))
                    slippage = max(5.0, 18.0 - (12.0 * liq))
                    for side in sides:
                        out.append(
                            PretradeCheckRequest(
                                symbol=str(r.symbol),
                                side=side,
                                qty=0.01,
                                rr_estimate=1.7,
                                trend_tf="4H",
                                signal_tf="1H",
                                timing_tf="15M",
                                spread_bps=round(spread, 2),
                                slippage_bps=round(slippage, 2),
                                volume_24h_usdt=qv,
                                market_trend_score=round(float(r.trend_score or 0.0), 3),
                                market_trend_score_1d=None,
                                market_trend_score_4h=None,
                                market_trend_score_1h=None,
                                market_micro_trend_15m=None,
                                atr_pct=round(float(r.atr_pct or 0.0), 3),
                                momentum_score=round(float(r.momentum_score or 0.0), 3),
                                funding_rate_bps=0.0,
                                crypto_event_block=False,
                            )
                        )
                return out

    ticker_rows = _fetch_binance_ticker_rows()
    if ticker_rows:
        ranked: list[tuple[dict, float]] = []
        for item in ticker_rows:
            symbol = str(item.get("symbol") or "").upper().strip()
            if not _is_binance_directional_symbol(symbol):
                continue
            try:
                qv = float(item.get("quoteVolume") or 0.0)
                pct = float(item.get("priceChangePercent") or 0.0)
                high = float(item.get("highPrice") or 0.0)
                low = float(item.get("lowPrice") or 0.0)
                last = float(item.get("lastPrice") or 0.0)
            except (TypeError, ValueError):
                continue
            if last <= 0:
                continue
            if qv < _binance_monitor_volume_floor():
                continue
            ranked.append(({
                "symbol": symbol,
                "quote_volume": qv,
                "pct": pct,
                "high": high,
                "low": low,
                "last": last,
            }, qv))
        ranked.sort(key=lambda x: x[1], reverse=True)
        selected = [r[0] for r in ranked[:12]]
        out: list[PretradeCheckRequest] = []
        for row in selected:
            qv = float(row["quote_volume"])
            pct = float(row.get("pct") or 0.0)
            mtf = _compute_binance_mtf_signal(str(row["symbol"]))
            if mtf is not None:
                trend = float(mtf.get("trend_score") or 0.0)
                momentum = float(mtf.get("momentum_score") or 0.0)
                vol = float(mtf.get("atr_pct") or 0.0)
            else:
                last = float(row.get("last") or 0.0)
                high = float(row.get("high") or 0.0)
                low = float(row.get("low") or 0.0)
                vol = ((high - low) / last) * 100.0 if high > 0 and low > 0 and last > 0 else 0.0
                trend = max(-1.0, min(1.0, pct / 8.0))
                momentum = max(-1.0, min(1.0, pct / 6.0))
            liq = min(1.0, qv / 200_000_000.0)
            spread = max(3.0, 14.0 - (10.0 * liq))
            slippage = max(5.0, 18.0 - (12.0 * liq))
            for side in sides:
                out.append(
                    PretradeCheckRequest(
                        symbol=str(row["symbol"]),
                        side=side,
                        qty=0.01,
                        rr_estimate=1.7,
                        trend_tf="4H",
                        signal_tf="1H",
                        timing_tf="15M",
                        spread_bps=round(spread, 2),
                        slippage_bps=round(slippage, 2),
                        volume_24h_usdt=qv,
                        market_trend_score=round(trend, 3),
                        market_trend_score_1d=round(float(mtf.get("trend_1d")) if mtf is not None and mtf.get("trend_1d") is not None else trend, 6),
                        market_trend_score_4h=round(float(mtf.get("trend_4h")) if mtf is not None and mtf.get("trend_4h") is not None else trend, 6),
                        market_trend_score_1h=round(float(mtf.get("trend_1h")) if mtf is not None and mtf.get("trend_1h") is not None else trend, 6),
                        market_micro_trend_15m=(
                            round(float(mtf.get("micro_trend_15m")), 6)
                            if mtf is not None and mtf.get("micro_trend_15m") is not None
                            else None
                        ),
                        atr_pct=round(vol, 3),
                        momentum_score=round(momentum, 3),
                        funding_rate_bps=0.0,
                        crypto_event_block=False,
                    )
                )
        if out:
            return out
    return [
        PretradeCheckRequest(
            symbol=s,
            side=side,
            qty=0.01,
            rr_estimate=1.7,
            trend_tf="4H",
            signal_tf="1H",
            timing_tf="15M",
            spread_bps=7.0,
            slippage_bps=10.0,
            volume_24h_usdt=90_000_000.0,
            market_trend_score=0.0,
            market_trend_score_1d=None,
            market_trend_score_4h=None,
            market_trend_score_1h=None,
            market_micro_trend_15m=None,
            atr_pct=0.0,
            momentum_score=0.0,
            funding_rate_bps=0.0,
            crypto_event_block=False,
        )
        for side in sides
        for s in _binance_fallback_symbols()
    ]
