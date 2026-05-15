from __future__ import annotations

def test_trailing_orchestrator_calls_replacement_when_candidate_sl_exists():
    from apps.worker.app.engine.binance_trailing_stop_orchestrator import (
        run_trailing_stop_replacement_once,
    )

    calls = []

    def fake_replace(**kwargs):
        calls.append(kwargs)
        return {"status": "replaced", "new_sl_client_algo_id": "trail-1-SL"}

    transition_claim = {
        "claim_status": "ACTIVE",
        "owner_id": "worker-1",
    }

    result = run_trailing_stop_replacement_once(
        position={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "direction": "LONG",
            "entry_price": "100",
            "stop_loss": "90",
            "current_price": "111",
            "qty": "0.01",
            "intent_entry_price": "100",
        },
        old_sl_client_algo_id="old-sl-1",
        replacement_client_order_id="trail-1",
        transition_claim=transition_claim,
        replace_stop_loss=fake_replace,
    )

    assert result["status"] == "replaced"
    assert calls == [
        {
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "qty": "0.01",
            "entry_price": "100",
            "old_stop_loss": "90",
            "new_stop_loss": 100.0,
            "old_sl_client_algo_id": "old-sl-1",
            "replacement_client_order_id": "trail-1",
            "transition_claim": transition_claim,
        }
    ]

def test_trailing_orchestrator_noops_when_no_candidate_sl_exists():
    from apps.worker.app.engine.binance_trailing_stop_orchestrator import (
        run_trailing_stop_replacement_once,
    )

    calls = []

    result = run_trailing_stop_replacement_once(
        position={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "direction": "LONG",
            "entry_price": "100",
            "stop_loss": "90",
            "current_price": "105",
            "qty": "0.01",
            "intent_entry_price": "100",
        },
        old_sl_client_algo_id="old-sl-1",
        replacement_client_order_id="trail-1",
        transition_claim={
            "claim_status": "ACTIVE",
            "owner_id": "worker-1",
        },
        replace_stop_loss=lambda **kwargs: calls.append(kwargs),
    )

    assert result == {
        "status": "noop",
        "reason": "no_trailing_candidate",
    }
    assert calls == []

def test_trailing_orchestrator_fails_closed_without_old_sl_id():
    from apps.worker.app.engine.binance_trailing_stop_orchestrator import (
        run_trailing_stop_replacement_once,
    )

    result = run_trailing_stop_replacement_once(
        position={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "direction": "LONG",
            "entry_price": "100",
            "stop_loss": "90",
            "current_price": "111",
            "qty": "0.01",
        },
        old_sl_client_algo_id="",
        replacement_client_order_id="trail-1",
        transition_claim={
            "claim_status": "ACTIVE",
            "owner_id": "worker-1",
        },
        replace_stop_loss=lambda **kwargs: {"status": "should_not_call"},
    )

    assert result == {
        "status": "blocked",
        "reason": "old_sl_client_algo_id_required",
    }
