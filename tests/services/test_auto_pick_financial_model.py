import pytest
from decimal import Decimal

from apps.api.app.services.auto_pick_financial_model import (
    calculate_support_resistance_by_percentiles,
    validate_range,
    combine_trends,
    calculate_structure_score,
    calculate_confirmation_score,
    liquidity_factor_from_state,
    calculate_final_score,
    rank_candidates_by_final_score,
)


def test_support_resistance_percentiles_basic():
    prices = [100, 110, 120, 130, 140]
    out = calculate_support_resistance_by_percentiles(prices)

    assert out["support"] > 0
    assert out["resistance"] > out["support"]


def test_support_resistance_fail_empty():
    with pytest.raises(ValueError):
        calculate_support_resistance_by_percentiles([])


def test_validate_range_valid_case():
    out = validate_range(
        support=100,
        resistance=120,
        current_price=110,
    )

    assert out["valid"] is True
    assert 0 <= out["position_in_range"] <= 1


def test_validate_range_invalid_range():
    out = validate_range(
        support=120,
        resistance=100,
        current_price=110,
    )

    assert out["valid"] is False


def test_combine_trends_weighted():
    out = combine_trends(trend_swing=1, trend_intraday=0)

    assert -1 <= out <= 1


def test_structure_score_buy():
    out = calculate_structure_score(
        position_in_range=0.2,
        combined_trend=0.5,
        side="BUY",
    )

    assert 0 <= out <= 1


def test_structure_score_sell():
    out = calculate_structure_score(
        position_in_range=0.8,
        combined_trend=-0.5,
        side="SELL",
    )

    assert 0 <= out <= 1


def test_structure_invalid_side():
    with pytest.raises(ValueError):
        calculate_structure_score(
            position_in_range=0.5,
            combined_trend=0,
            side="HOLD",
        )


def test_confirmation_score_bounds():
    out = calculate_confirmation_score(
        confirmations={
            "momentum": 1,
            "volume": 1,
            "micro": 1,
            "atr_risk": 0,
        }
    )

    assert 0 <= out["confirmation_score"] <= 1
    assert 0.7 <= out["confirmation_factor"] <= 1.2


def test_liquidity_factor():
    assert liquidity_factor_from_state("green") == Decimal("1")
    assert liquidity_factor_from_state("gray") == Decimal("0.75")
    assert liquidity_factor_from_state("red") == Decimal("0")


def test_final_score_basic():
    out = calculate_final_score(
        structure_score=0.8,
        confirmation_factor=1.0,
        liquidity_factor=1.0,
    )

    assert 0 <= out <= 1


def test_rank_candidates():
    candidates = [
        {"final_score": 0.1},
        {"final_score": 0.9},
        {"final_score": 0.5},
    ]

    out = rank_candidates_by_final_score(candidates)

    assert out[0]["final_score"] == 0.9
    assert out[-1]["final_score"] == 0.1
