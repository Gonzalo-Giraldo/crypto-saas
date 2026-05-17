from apps.api.app.services.auto_pick.binance.observation_contracts import (
    BinanceMarketObservationSnapshot,
    BinanceMarketReadResult,
)
from apps.api.app.services.auto_pick.binance.snapshot_runtime import (
    extract_snapshot_market_context,
    run_binance_auto_pick_observation_from_snapshot,
)
from apps.api.app.services.auto_pick.binance.evaluation_engine import (
    evaluate_binance_autopick_market_context,
)


def _ticker(symbol, price="100", quote_volume="250000000", bid="99.9", ask="100.1"):
    return {
        "symbol": symbol,
        "lastPrice": price,
        "quoteVolume": quote_volume,
        "bidPrice": bid,
        "askPrice": ask,
    }


def _klines():
    rows = []
    price = 100.0
    for _ in range(30):
        rows.append([0, price, price * 1.01, price * 0.99, price, 1000])
        price *= 1.001
    return rows


def test_evaluation_engine_matches_snapshot_runtime(monkeypatch):
    import apps.api.app.services.auto_pick.binance.snapshot_runtime as runtime
    import apps.api.app.services.auto_pick.binance.evaluation_engine as engine

    snapshot = BinanceMarketObservationSnapshot(
        snapshot_id="snapshot-equivalence",
        broker="BINANCE",
        market="FUTURES",
        reads=(
            BinanceMarketReadResult(
                source_type="ticker_24h",
                symbol=None,
                interval=None,
                status="OK",
                rows=[_ticker("BTCUSDT"), _ticker("ETHUSDT")],
                error_code=None,
                latency_ms=10,
            ),
            BinanceMarketReadResult(
                source_type="klines",
                symbol="BTCUSDT",
                interval="1h",
                status="OK",
                rows=_klines(),
                error_code=None,
                latency_ms=10,
            ),
            BinanceMarketReadResult(
                source_type="klines",
                symbol="BTCUSDT",
                interval="15m",
                status="OK",
                rows=_klines(),
                error_code=None,
                latency_ms=10,
            ),
            BinanceMarketReadResult(
                source_type="klines",
                symbol="ETHUSDT",
                interval="1h",
                status="OK",
                rows=_klines(),
                error_code=None,
                latency_ms=10,
            ),
            BinanceMarketReadResult(
                source_type="klines",
                symbol="ETHUSDT",
                interval="15m",
                status="OK",
                rows=_klines(),
                error_code=None,
                latency_ms=10,
            ),
        ),
    )

    symbols = lambda rows: ["BTCUSDT", "ETHUSDT"]
    monkeypatch.setattr(engine, "build_candidate_symbols", symbols)

    build_input = lambda **kwargs: {
        "symbol": kwargs["symbol"],
        "entry_price": kwargs["ticker_24h"]["lastPrice"],
        "market_metrics": {},
        "ohlc": {},
    }
    monkeypatch.setattr(engine, "build_crypto_model_input", build_input)

    score = lambda candidate: {
        "symbol": candidate["symbol"],
        "side": "BUY",
        "valid": True,
        "reason": "ok",
        "final_score": {"BTCUSDT": 0.7, "ETHUSDT": 0.9}[candidate["symbol"]],
    }
    monkeypatch.setattr(engine, "compute_final_score", score)

    expected = run_binance_auto_pick_observation_from_snapshot(
        snapshot,
        top_n=2,
    )

    context = extract_snapshot_market_context(snapshot)

    actual = evaluate_binance_autopick_market_context(
        ticker_rows=context["ticker_rows"],
        klines_1h_by_symbol=context["klines_1h"],
        klines_15m_by_symbol=context["klines_15m"],
        top_n=2,
    )

    assert actual.selected_symbol == expected.selected_symbol
