from apps.api.app.services.auto_pick.binance.evaluation_engine import (
    evaluate_binance_autopick_market_context,
)


def test_evaluation_engine_imports_as_single_factual_engine():
    assert callable(evaluate_binance_autopick_market_context)


def test_evaluation_engine_report_exposes_model_version_for_lineage():
    report = evaluate_binance_autopick_market_context(
        ticker_rows=[],
        klines_1h_by_symbol={},
        klines_15m_by_symbol={},
    )

    assert report.model_version == "binance_auto_pick_pipeline_v1"
