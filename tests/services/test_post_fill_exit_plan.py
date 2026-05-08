from apps.api.app.services.intent_math import build_fixed_reward_risk_plan
from apps.api.app.services.risk.post_fill_exit_plan import build_post_fill_reward_risk_plan


def test_post_fill_buy_reuses_existing_formula():
    expected = build_fixed_reward_risk_plan(
        side="BUY",
        entry_price=101.0,
        risk_pct=1.0,
        reward_risk_ratio=2.0,
    )

    result = build_post_fill_reward_risk_plan(
        side="BUY",
        avg_entry_price=101.0,
        risk_pct=1.0,
        reward_risk_ratio=2.0,
    )

    assert result == expected


def test_post_fill_sell_reuses_existing_formula():
    expected = build_fixed_reward_risk_plan(
        side="SELL",
        entry_price=101.0,
        risk_pct=1.0,
        reward_risk_ratio=2.0,
    )

    result = build_post_fill_reward_risk_plan(
        side="SELL",
        avg_entry_price=101.0,
        risk_pct=1.0,
        reward_risk_ratio=2.0,
    )

    assert result == expected
