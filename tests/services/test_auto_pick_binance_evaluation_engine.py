from apps.api.app.services.auto_pick.binance.evaluation_engine import (
    evaluate_binance_autopick_market_context,
)


def test_evaluation_engine_imports_as_single_factual_engine():
    assert callable(evaluate_binance_autopick_market_context)
