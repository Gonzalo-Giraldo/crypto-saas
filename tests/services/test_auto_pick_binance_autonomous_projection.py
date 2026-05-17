from apps.api.app.services.auto_pick.binance import orchestrator as orch
from apps.api.app.services.auto_pick.contracts import AutoPickDecision, AutoPickNoTrade


def _ticker(symbol, price="100", quote_volume="250000000", bid="99.9", ask="100.1"):
    return {
        "symbol": symbol,
        "lastPrice": price,
        "quoteVolume": quote_volume,
        "bidPrice": bid,
        "askPrice": ask,
    }


def test_autonomous_projection_selected_top_n_without_risk_intent_or_execution(monkeypatch):
    monkeypatch.setattr(
        orch,
        "fetch_ticker_24h_rows",
        lambda: [_ticker("BTCUSDT"), _ticker("ETHUSDT"), _ticker("ADAUSDT")],
    )
    monkeypatch.setattr(orch, "build_candidate_symbols", lambda rows: ["BTCUSDT", "ETHUSDT", "ADAUSDT"])
    monkeypatch.setattr(orch, "fetch_1h_klines", lambda symbol: [["0", "1", "2", "1", "1.5", "10"]] * 30)
    monkeypatch.setattr(orch, "fetch_15m_klines", lambda symbol: [["0", "1", "2", "1", "1.5", "10"]] * 10)

    def fake_build_crypto_model_input(*, symbol, klines_1h, klines_15m, ticker_24h):
        return {"symbol": symbol, "entry_price": ticker_24h["lastPrice"], "market_metrics": {}, "ohlc": {}}

    def fake_compute_final_score(candidate):
        scores = {"BTCUSDT": 0.70, "ETHUSDT": 0.95, "ADAUSDT": 0.80}
        return {
            "symbol": candidate["symbol"],
            "side": "BUY",
            "valid": True,
            "reason": "ok",
            "final_score": scores[candidate["symbol"]],
        }

    monkeypatch.setattr(orch, "build_crypto_model_input", fake_build_crypto_model_input)
    monkeypatch.setattr(orch, "compute_final_score", fake_compute_final_score)

    report = orch.run_binance_auto_pick_observation(top_n=2)

    assert report.decision_status == "SELECTED"
    assert report.selected_symbol == "ETHUSDT"
    assert report.selected_rank == 1
    assert len(report.candidates) == 2
    assert [row.symbol for row in report.candidates] == ["ETHUSDT", "ADAUSDT"]
    assert report.candidates[0].selected is True
    assert report.candidates[1].selected is False
    assert report.production_priority is True


def test_autonomous_projection_records_no_selection(monkeypatch):
    monkeypatch.setattr(orch, "fetch_ticker_24h_rows", lambda: [_ticker("BTCUSDT")])
    monkeypatch.setattr(orch, "build_candidate_symbols", lambda rows: ["BTCUSDT"])
    monkeypatch.setattr(orch, "fetch_1h_klines", lambda symbol: [["0", "1", "2", "1", "1.5", "10"]] * 30)
    monkeypatch.setattr(orch, "fetch_15m_klines", lambda symbol: [["0", "1", "2", "1", "1.5", "10"]] * 10)
    monkeypatch.setattr(
        orch,
        "build_crypto_model_input",
        lambda **kwargs: {"symbol": kwargs["symbol"], "entry_price": "100", "market_metrics": {}, "ohlc": {}},
    )
    monkeypatch.setattr(
        orch,
        "compute_final_score",
        lambda candidate: {
            "symbol": candidate["symbol"],
            "side": None,
            "valid": False,
            "reason": "liquidity_red",
            "final_score": 0,
        },
    )

    report = orch.run_binance_auto_pick_observation(top_n=10)

    assert report.decision_status == "NO_SELECTION"
    assert report.selected_symbol is None
    assert report.selected_rank is None
    assert report.no_selection_reason == "no_valid_candidates"
    assert report.candidates == []
    assert report.production_priority is True


def test_existing_auto_pick_contract_still_returns_decision(monkeypatch):
    monkeypatch.setattr(
        orch,
        "run_binance_auto_pick_observation",
        lambda top_n=10, max_symbols=None: orch.AutoPickObservationReport(
            decision_status="SELECTED",
            broker="BINANCE",
            reason="selected_top_ranked_candidate",
            no_selection_reason=None,
            selected=orch.AutoPickCandidateProjection(
                rank=1,
                symbol="BTCUSDT",
                side="BUY",
                valid=True,
                reason="ok",
                final_score=0.9,
                selected=True,
                entry_price_reference=100.0,
                features={},
            ),
            selected_symbol="BTCUSDT",
            selected_rank=1,
            ranked_count=1,
            top_n=top_n,
            candidates=[],
            production_priority=True,
        ),
    )

    result = orch.run_binance_auto_pick()

    assert isinstance(result, AutoPickDecision)
    assert result.symbol == "BTCUSDT"
    assert result.side == "BUY"
    assert result.direction == "LONG"
    assert result.evidence["entry_price_semantics"] == "reference_only_not_fill"


def test_existing_auto_pick_contract_still_returns_no_trade(monkeypatch):
    monkeypatch.setattr(
        orch,
        "run_binance_auto_pick_observation",
        lambda top_n=10, max_symbols=None: orch.AutoPickObservationReport(
            decision_status="NO_SELECTION",
            broker="BINANCE",
            reason="no_valid_candidates",
            no_selection_reason="no_valid_candidates",
            selected=None,
            selected_symbol=None,
            selected_rank=None,
            ranked_count=0,
            top_n=top_n,
            candidates=[],
            production_priority=True,
        ),
    )

    result = orch.run_binance_auto_pick()

    assert isinstance(result, AutoPickNoTrade)
    assert result.reason == "no_valid_candidates"
