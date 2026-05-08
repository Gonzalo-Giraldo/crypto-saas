import pytest

from apps.api.app.services.risk.post_fill_exit_diff import (
    compare_post_fill_exit_plan_diff,
)


def test_no_correction_when_diff_below_threshold():
    result = compare_post_fill_exit_plan_diff(
        provisional_stop_loss=100.0,
        provisional_take_profit=120.0,
        authoritative_stop_loss=100.4,
        authoritative_take_profit=120.4,
        min_diff_pct=0.5,
    )

    assert result.correction_required is False


def test_correction_when_sl_diff_above_threshold():
    result = compare_post_fill_exit_plan_diff(
        provisional_stop_loss=100.0,
        provisional_take_profit=120.0,
        authoritative_stop_loss=101.0,
        authoritative_take_profit=120.0,
        min_diff_pct=0.5,
    )

    assert result.correction_required is True
    assert result.sl_diff_pct == 1.0


def test_correction_when_tp_diff_above_threshold():
    result = compare_post_fill_exit_plan_diff(
        provisional_stop_loss=100.0,
        provisional_take_profit=120.0,
        authoritative_stop_loss=100.0,
        authoritative_take_profit=121.2,
        min_diff_pct=0.5,
    )

    assert result.correction_required is True
    assert result.tp_diff_pct == pytest.approx(1.0)


def test_negative_threshold_rejected():
    with pytest.raises(ValueError, match="min_diff_pct_must_be_nonnegative"):
        compare_post_fill_exit_plan_diff(
            provisional_stop_loss=100.0,
            provisional_take_profit=120.0,
            authoritative_stop_loss=100.0,
            authoritative_take_profit=120.0,
            min_diff_pct=-0.1,
        )
