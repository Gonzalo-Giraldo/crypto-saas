from __future__ import annotations

from apps.api.app.services.auto_pick.binance.observation_contracts import (
    BinanceMarketObservationSnapshot,
    BinanceMarketReadResult,
)
from apps.api.app.services.auto_pick.binance.snapshot_runtime import (
    run_binance_auto_pick_observation_from_snapshot,
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


def test_runs_autopick_observation_from_snapshot(monkeypatch):
    import apps.api.app.services.auto_pick.binance.snapshot_runtime as runtime
    import apps.api.app.services.auto_pick.binance.evaluation_engine as engine

    snapshot = BinanceMarketObservationSnapshot(
        snapshot_id="snapshot-1",
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
    monkeypatch.setattr(runtime, "build_candidate_symbols", symbols)
    monkeypatch.setattr(engine, "build_candidate_symbols", symbols)

    def fake_build_crypto_model_input(*, symbol, klines_1h, klines_15m, ticker_24h):
        return {
            "symbol": symbol,
            "entry_price": ticker_24h["lastPrice"],
            "market_metrics": {},
            "ohlc": {},
        }

    def fake_compute_final_score(candidate):
        scores = {"BTCUSDT": 0.7, "ETHUSDT": 0.9}
        return {
            "symbol": candidate["symbol"],
            "side": "BUY",
            "valid": True,
            "reason": "ok",
            "final_score": scores[candidate["symbol"]],
        }

    monkeypatch.setattr(runtime, "build_crypto_model_input", fake_build_crypto_model_input)
    monkeypatch.setattr(engine, "build_crypto_model_input", fake_build_crypto_model_input)
    monkeypatch.setattr(runtime, "compute_final_score", fake_compute_final_score)
    monkeypatch.setattr(engine, "compute_final_score", fake_compute_final_score)

    report = run_binance_auto_pick_observation_from_snapshot(snapshot, top_n=2)

    assert report.decision_status == "SELECTED"
    assert report.selected_symbol == "ETHUSDT"
    assert report.selected_rank == 1
    assert [row.symbol for row in report.candidates] == ["ETHUSDT", "BTCUSDT"]


def test_snapshot_missing_market_data_returns_no_selection():
    snapshot = BinanceMarketObservationSnapshot(
        snapshot_id="snapshot-empty",
        broker="BINANCE",
        market="FUTURES",
        reads=(),
    )

    report = run_binance_auto_pick_observation_from_snapshot(snapshot, top_n=10)

    assert report.decision_status == "NO_SELECTION"
    assert report.selected_symbol is None
    assert report.no_selection_reason == "no_ticker_data"


def _snapshot_with_read_order(reads):
    return BinanceMarketObservationSnapshot(
        snapshot_id="snapshot-determinism",
        broker="BINANCE",
        market="FUTURES",
        reads=tuple(reads),
    )


def test_snapshot_decision_is_stable_when_reads_are_reordered(monkeypatch):
    import apps.api.app.services.auto_pick.binance.snapshot_runtime as runtime
    import apps.api.app.services.auto_pick.binance.evaluation_engine as engine

    ticker_read = BinanceMarketReadResult(
        source_type="ticker_24h",
        symbol=None,
        interval=None,
        status="OK",
        rows=[_ticker("BTCUSDT"), _ticker("ETHUSDT")],
        error_code=None,
        latency_ms=10,
    )
    btc_1h = BinanceMarketReadResult("klines", "BTCUSDT", "1h", "OK", _klines(), None, 10)
    btc_15m = BinanceMarketReadResult("klines", "BTCUSDT", "15m", "OK", _klines(), None, 10)
    eth_1h = BinanceMarketReadResult("klines", "ETHUSDT", "1h", "OK", _klines(), None, 10)
    eth_15m = BinanceMarketReadResult("klines", "ETHUSDT", "15m", "OK", _klines(), None, 10)

    symbols = lambda rows: ["BTCUSDT", "ETHUSDT"]
    monkeypatch.setattr(runtime, "build_candidate_symbols", symbols)
    monkeypatch.setattr(engine, "build_candidate_symbols", symbols)
    build_input = lambda **kwargs: {
        "symbol": kwargs["symbol"],
        "entry_price": kwargs["ticker_24h"]["lastPrice"],
        "market_metrics": {},
        "ohlc": {},
    }
    monkeypatch.setattr(runtime, "build_crypto_model_input", build_input)
    monkeypatch.setattr(engine, "build_crypto_model_input", build_input)

    score = lambda candidate: {
        "symbol": candidate["symbol"],
        "side": "BUY",
        "valid": True,
        "reason": "ok",
        "final_score": {"BTCUSDT": 0.7, "ETHUSDT": 0.9}[candidate["symbol"]],
    }
    monkeypatch.setattr(runtime, "compute_final_score", score)
    monkeypatch.setattr(engine, "compute_final_score", score)

    report_a = run_binance_auto_pick_observation_from_snapshot(
        _snapshot_with_read_order((ticker_read, btc_1h, btc_15m, eth_1h, eth_15m)),
        top_n=2,
    )
    report_b = run_binance_auto_pick_observation_from_snapshot(
        _snapshot_with_read_order((eth_15m, btc_15m, ticker_read, eth_1h, btc_1h)),
        top_n=2,
    )

    assert report_a.selected_symbol == report_b.selected_symbol == "ETHUSDT"
    assert [row.symbol for row in report_a.candidates] == [row.symbol for row in report_b.candidates]
    assert [row.final_score for row in report_a.candidates] == [row.final_score for row in report_b.candidates]


def test_snapshot_decision_ignores_unrelated_symbol_reads(monkeypatch):
    import apps.api.app.services.auto_pick.binance.snapshot_runtime as runtime
    import apps.api.app.services.auto_pick.binance.evaluation_engine as engine

    symbols = lambda rows: ["BTCUSDT"]
    monkeypatch.setattr(runtime, "build_candidate_symbols", symbols)
    monkeypatch.setattr(engine, "build_candidate_symbols", symbols)
    monkeypatch.setattr(
        runtime,
        "build_crypto_model_input",
        lambda **kwargs: {
            "symbol": kwargs["symbol"],
            "entry_price": kwargs["ticker_24h"]["lastPrice"],
            "market_metrics": {},
            "ohlc": {},
        },
    )
    monkeypatch.setattr(
        runtime,
        "compute_final_score",
        lambda candidate: {
            "symbol": candidate["symbol"],
            "side": "BUY",
            "valid": True,
            "reason": "ok",
            "final_score": 0.8,
        },
    )

    snapshot = BinanceMarketObservationSnapshot(
        snapshot_id="snapshot-unrelated",
        broker="BINANCE",
        market="FUTURES",
        reads=(
            BinanceMarketReadResult("ticker_24h", None, None, "OK", [_ticker("BTCUSDT")], None, 10),
            BinanceMarketReadResult("klines", "BTCUSDT", "1h", "OK", _klines(), None, 10),
            BinanceMarketReadResult("klines", "BTCUSDT", "15m", "OK", _klines(), None, 10),
            BinanceMarketReadResult("klines", "DOGEUSDT", "1h", "OK", _klines(), None, 10),
            BinanceMarketReadResult("klines", "DOGEUSDT", "15m", "OK", _klines(), None, 10),
        ),
    )

    report = run_binance_auto_pick_observation_from_snapshot(snapshot, top_n=10)

    assert report.decision_status == "SELECTED"
    assert report.selected_symbol == "BTCUSDT"
    assert [row.symbol for row in report.candidates] == ["BTCUSDT"]


def test_snapshot_decision_reports_missing_klines_rejections():
    snapshot = BinanceMarketObservationSnapshot(
        snapshot_id="snapshot-rejections",
        broker="BINANCE",
        market="FUTURES",
        reads=(
            BinanceMarketReadResult(
                "ticker_24h",
                None,
                None,
                "OK",
                [_ticker("BTCUSDT"), _ticker("ETHUSDT")],
                None,
                10,
            ),
            BinanceMarketReadResult(
                "klines",
                "BTCUSDT",
                "1h",
                "OK",
                _klines(),
                None,
                10,
            ),
            BinanceMarketReadResult(
                "klines",
                "BTCUSDT",
                "15m",
                "OK",
                _klines(),
                None,
                10,
            ),
        ),
    )

    report = run_binance_auto_pick_observation_from_snapshot(snapshot, top_n=10)

    assert report.decision_status == "SELECTED"
    assert report.selected_symbol == "BTCUSDT"
    assert report.rejected_candidates == [
        {
            "symbol": "ETHUSDT",
            "reason": "missing_1h_klines",
        }
    ]


def test_snapshot_decision_reports_candidate_input_exception(monkeypatch):
    import apps.api.app.services.auto_pick.binance.snapshot_runtime as runtime
    import apps.api.app.services.auto_pick.binance.evaluation_engine as engine

    snapshot = BinanceMarketObservationSnapshot(
        snapshot_id="snapshot-input-error",
        broker="BINANCE",
        market="FUTURES",
        reads=(
            BinanceMarketReadResult("ticker_24h", None, None, "OK", [_ticker("BTCUSDT")], None, 10),
            BinanceMarketReadResult("klines", "BTCUSDT", "1h", "OK", _klines(), None, 10),
            BinanceMarketReadResult("klines", "BTCUSDT", "15m", "OK", _klines(), None, 10),
        ),
    )

    symbols = lambda rows: ["BTCUSDT"]
    monkeypatch.setattr(runtime, "build_candidate_symbols", symbols)
    monkeypatch.setattr(engine, "build_candidate_symbols", symbols)

    def boom(**kwargs):
        raise ValueError("ticker_24h_required")

    monkeypatch.setattr(runtime, "build_crypto_model_input", boom)
    monkeypatch.setattr(engine, "build_crypto_model_input", boom)

    report = run_binance_auto_pick_observation_from_snapshot(snapshot, top_n=10)

    assert report.decision_status == "NO_SELECTION"
    assert report.no_selection_reason == "no_valid_candidates"
    assert report.rejected_candidates == [
        {
            "symbol": "BTCUSDT",
            "reason": "candidate_input_exception:ticker_24h_required",
        }
    ]
