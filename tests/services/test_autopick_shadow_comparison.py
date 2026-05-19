from apps.api.app.services.auto_pick.contracts import AutoPickObservationReport
from apps.api.app.services.runtime_scheduler.autopick_shadow_comparison import (
    compare_autopick_shadow_reports,
)


def _report(
    *,
    status="SELECTED",
    symbol="BTCUSDT",
    rank=1,
    ranked_count=3,
):
    return AutoPickObservationReport(
        decision_status=status,
        broker="BINANCE",
        reason="test",
        no_selection_reason=None if status == "SELECTED" else "test",
        selected=None,
        selected_symbol=symbol,
        selected_rank=rank,
        ranked_count=ranked_count,
        top_n=10,
        candidates=[],
        production_priority=True,
    )


def test_compare_autopick_shadow_reports_detects_no_divergence():
    out = compare_autopick_shadow_reports(
        legacy_report=_report(),
        shadow_report=_report(),
    )

    assert out["diverged"] is False
    assert out["fields"] == {}


def test_compare_autopick_shadow_reports_detects_core_divergence():
    out = compare_autopick_shadow_reports(
        legacy_report=_report(symbol="BTCUSDT", ranked_count=3),
        shadow_report=_report(symbol="ETHUSDT", ranked_count=4),
    )

    assert out["diverged"] is True
    assert out["fields"]["selected_symbol"] == {
        "legacy": "BTCUSDT",
        "shadow": "ETHUSDT",
    }
    assert out["fields"]["ranked_count"] == {
        "legacy": 3,
        "shadow": 4,
    }
