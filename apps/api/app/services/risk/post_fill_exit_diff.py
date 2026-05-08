from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PostFillExitDiff:
    sl_diff_abs: float
    tp_diff_abs: float
    sl_diff_pct: float
    tp_diff_pct: float
    min_diff_pct: float
    correction_required: bool


def compare_post_fill_exit_plan_diff(
    *,
    provisional_stop_loss: float,
    provisional_take_profit: float,
    authoritative_stop_loss: float,
    authoritative_take_profit: float,
    min_diff_pct: float = 0.5,
) -> PostFillExitDiff:
    """
    PURE FUNCTION.

    Dry-run comparison only.
    NO DB.
    NO broker.
    NO runtime side effects.
    """

    if provisional_stop_loss <= 0:
        raise ValueError("provisional_stop_loss_must_be_positive")
    if provisional_take_profit <= 0:
        raise ValueError("provisional_take_profit_must_be_positive")
    if authoritative_stop_loss <= 0:
        raise ValueError("authoritative_stop_loss_must_be_positive")
    if authoritative_take_profit <= 0:
        raise ValueError("authoritative_take_profit_must_be_positive")
    if min_diff_pct < 0:
        raise ValueError("min_diff_pct_must_be_nonnegative")

    sl_diff_abs = abs(authoritative_stop_loss - provisional_stop_loss)
    tp_diff_abs = abs(authoritative_take_profit - provisional_take_profit)

    sl_diff_pct = (sl_diff_abs / provisional_stop_loss) * 100.0
    tp_diff_pct = (tp_diff_abs / provisional_take_profit) * 100.0

    correction_required = (
        sl_diff_pct > min_diff_pct
        or tp_diff_pct > min_diff_pct
    )

    return PostFillExitDiff(
        sl_diff_abs=sl_diff_abs,
        tp_diff_abs=tp_diff_abs,
        sl_diff_pct=sl_diff_pct,
        tp_diff_pct=tp_diff_pct,
        min_diff_pct=min_diff_pct,
        correction_required=correction_required,
    )
