from apps.api.app.services.runtime_scheduler.runtime_flow_result_builder import (
    build_scheduler_runtime_flow_result,
)


def test_build_scheduler_runtime_flow_result():
    result = build_scheduler_runtime_flow_result(
        duration_ms=123,
        tick_details={"status": "ok"},
        observation_payload={"symbol": "BTCUSDT"},
        candidate_symbol="BTCUSDT",
        candidate_score="0.99",
    )

    assert result.duration_ms == 123
    assert result.tick_details == {"status": "ok"}
    assert result.observation_payload == {"symbol": "BTCUSDT"}
    assert result.candidate_symbol == "BTCUSDT"
    assert result.candidate_score == "0.99"
