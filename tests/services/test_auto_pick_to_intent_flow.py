from apps.api.app.services.auto_pick.contracts import AutoPickDecision, IntentCreateDraft
from apps.api.app.services.application.auto_pick_to_intent_flow import (
    build_intent_draft_from_autopick,
)


def test_build_intent_draft_from_autopick_preserves_trace_and_builds_risk():
    decision = AutoPickDecision(
        symbol="BTCUSDT",
        side="BUY",
        direction="LONG",
        broker="BINANCE",
        asset_profile="CRYPTO",
        model_version="binance_auto_pick_pipeline_v1",
        final_score=0.91,
        decision_reason="selected_top_ranked_candidate",
        evidence={
            "entry_price_reference": 65000.0,
            "entry_price_semantics": "reference_only_not_fill",
        },
    )

    draft = build_intent_draft_from_autopick(
        decision=decision,
        capital_base=1000.0,
        risk_pct=1.0,
        reward_risk_ratio=2.0,
    )

    assert isinstance(draft, IntentCreateDraft)
    assert draft.symbol == "BTCUSDT"
    assert draft.side == "BUY"
    assert draft.risk_sizing.entry_price == 65000.0
    assert draft.risk_sizing.stop_loss == 64350.0
    assert draft.risk_sizing.take_profit == 66300.0
    assert draft.risk_sizing.expected_qty > 0
    assert draft.final_score == 0.91
    assert draft.decision_reason == "selected_top_ranked_candidate"
    assert draft.evidence["entry_price_semantics"] == "reference_only_not_fill"


def test_build_intent_draft_from_autopick_fails_without_entry_price_reference():
    decision = AutoPickDecision(
        symbol="BTCUSDT",
        side="BUY",
        direction="LONG",
        broker="BINANCE",
        asset_profile="CRYPTO",
        model_version="binance_auto_pick_pipeline_v1",
        final_score=0.91,
        decision_reason="selected_top_ranked_candidate",
        evidence={},
    )

    try:
        build_intent_draft_from_autopick(
            decision=decision,
            capital_base=1000.0,
            risk_pct=1.0,
            reward_risk_ratio=2.0,
        )
    except ValueError as exc:
        assert str(exc) == "entry_price_reference is required"
    else:
        raise AssertionError("expected ValueError")
