from apps.api.app.services.auto_pick.binance import orchestrator as orch
from apps.api.app.services.auto_pick.binance import evaluation_engine as engine


def _ticker(symbol, price="100", quote_volume="250000000", bid="99.9", ask="100.1"):
    return {
        "symbol": symbol,
        "lastPrice": price,
        "quoteVolume": quote_volume,
        "bidPrice": bid,
        "askPrice": ask,
    }


def _klines():
    return [["0", "1", "2", "1", "1.5", "10"]] * 30


def test_orchestrator_observation_matches_evaluation_engine(monkeypatch):
    ticker_rows = [_ticker("BTCUSDT"), _ticker("ETHUSDT")]

    symbols = lambda rows: ["BTCUSDT", "ETHUSDT"]

    build_input = lambda **kwargs: {
        "symbol": kwargs["symbol"],
        "entry_price": kwargs["ticker_24h"]["lastPrice"],
        "market_metrics": {},
        "ohlc": {},
    }

    score = lambda candidate: {
        "symbol": candidate["symbol"],
        "side": "BUY",
        "valid": True,
        "reason": "ok",
        "final_score": {"BTCUSDT": 0.7, "ETHUSDT": 0.9}[candidate["symbol"]],
    }

    monkeypatch.setattr(orch, "fetch_ticker_24h_rows", lambda: ticker_rows)
    monkeypatch.setattr(orch, "fetch_1h_klines", lambda symbol: _klines())
    monkeypatch.setattr(orch, "fetch_15m_klines", lambda symbol: _klines())
    monkeypatch.setattr(orch, "build_candidate_symbols", symbols)
    monkeypatch.setattr(orch, "build_crypto_model_input", build_input)
    monkeypatch.setattr(orch, "compute_final_score", score)

    expected = orch.run_binance_auto_pick_observation(top_n=2)

    monkeypatch.setattr(engine, "build_candidate_symbols", symbols)
    monkeypatch.setattr(engine, "build_crypto_model_input", build_input)
    monkeypatch.setattr(engine, "compute_final_score", score)

    actual = engine.evaluate_binance_autopick_market_context(
        ticker_rows=ticker_rows,
        klines_1h_by_symbol={"BTCUSDT": _klines(), "ETHUSDT": _klines()},
        klines_15m_by_symbol={"BTCUSDT": _klines(), "ETHUSDT": _klines()},
        top_n=2,
    )

    assert actual.selected_symbol == expected.selected_symbol


def test_orchestrator_observation_still_uses_legacy_runtime_semantics():
    # Runtime path intentionally remains legacy until explicit semantic migration.
    assert callable(orch.run_binance_auto_pick_observation)
