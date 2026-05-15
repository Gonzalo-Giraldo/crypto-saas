from __future__ import annotations


def test_replacement_creates_new_sl_before_canceling_old_sl():
    from apps.worker.app.engine.binance_exit_stop_loss_replacement import (
        replace_exit_stop_loss_authoritatively,
    )

    calls = []

    def fake_create_sl(order_payload):
        calls.append(("create", order_payload["clientAlgoId"]))
        return {"status": "OK", "data": {"algoId": 222}}

    def fake_fetch_status(*, client_algo_id, **kwargs):
        calls.append(("status", client_algo_id))
        return {
            "status": "OK",
            "response": {
                "status": "NEW",
                "algoId": 222,
                "clientAlgoId": client_algo_id,
            },
        }

    def fake_cancel_old(*, client_algo_id, **kwargs):
        calls.append(("cancel", client_algo_id))
        return {"status": "CANCELED", "clientAlgoId": client_algo_id}

    result = replace_exit_stop_loss_authoritatively(
        symbol="BTCUSDT",
        direction="LONG",
        qty="0.01",
        entry_price="100",
        old_stop_loss="90",
        new_stop_loss="100",
        old_sl_client_algo_id="old-sl-1",
        replacement_client_order_id="trail-1",
        create_sl_order=fake_create_sl,
        fetch_sl_status=fake_fetch_status,
        cancel_old_sl=fake_cancel_old,
    )

    assert result == {
        "status": "replaced",
        "old_sl_client_algo_id": "old-sl-1",
        "new_sl_client_algo_id": "trail-1-SL",
        "new_sl_algo_id": 222,
    }

    assert calls == [
        ("create", "trail-1-SL"),
        ("status", "trail-1-SL"),
        ("cancel", "old-sl-1"),
    ]


def test_replacement_does_not_cancel_old_sl_when_new_sl_creation_fails():
    from apps.worker.app.engine.binance_exit_stop_loss_replacement import (
        replace_exit_stop_loss_authoritatively,
    )

    calls = []

    def fake_create_sl(order_payload):
        calls.append(("create", order_payload["clientAlgoId"]))
        return {"status": "ERROR", "error": "new_sl_failed"}

    def fake_fetch_status(**kwargs):
        calls.append(("status", kwargs))
        return {"status": "OK"}

    def fake_cancel_old(**kwargs):
        calls.append(("cancel", kwargs))
        return {"status": "CANCELED"}

    result = replace_exit_stop_loss_authoritatively(
        symbol="BTCUSDT",
        direction="LONG",
        qty="0.01",
        entry_price="100",
        old_stop_loss="90",
        new_stop_loss="100",
        old_sl_client_algo_id="old-sl-1",
        replacement_client_order_id="trail-1",
        create_sl_order=fake_create_sl,
        fetch_sl_status=fake_fetch_status,
        cancel_old_sl=fake_cancel_old,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "replacement_sl_create_failed"
    assert calls == [("create", "trail-1-SL")]


def test_replacement_does_not_cancel_old_sl_when_new_sl_is_not_active():
    from apps.worker.app.engine.binance_exit_stop_loss_replacement import (
        replace_exit_stop_loss_authoritatively,
    )

    calls = []

    def fake_create_sl(order_payload):
        calls.append(("create", order_payload["clientAlgoId"]))
        return {"status": "OK", "data": {"algoId": 222}}

    def fake_fetch_status(*, client_algo_id, **kwargs):
        calls.append(("status", client_algo_id))
        return {
            "status": "OK",
            "response": {
                "status": "EXPIRED",
                "algoId": 222,
                "clientAlgoId": client_algo_id,
            },
        }

    def fake_cancel_old(**kwargs):
        calls.append(("cancel", kwargs))
        return {"status": "CANCELED"}

    result = replace_exit_stop_loss_authoritatively(
        symbol="BTCUSDT",
        direction="LONG",
        qty="0.01",
        entry_price="100",
        old_stop_loss="90",
        new_stop_loss="100",
        old_sl_client_algo_id="old-sl-1",
        replacement_client_order_id="trail-1",
        create_sl_order=fake_create_sl,
        fetch_sl_status=fake_fetch_status,
        cancel_old_sl=fake_cancel_old,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "replacement_sl_not_active"
    assert calls == [
        ("create", "trail-1-SL"),
        ("status", "trail-1-SL"),
    ]


def test_replacement_rejects_non_favorable_long_sl():
    from apps.worker.app.engine.binance_exit_stop_loss_replacement import (
        replace_exit_stop_loss_authoritatively,
    )

    result = replace_exit_stop_loss_authoritatively(
        symbol="BTCUSDT",
        direction="LONG",
        qty="0.01",
        entry_price="100",
        old_stop_loss="90",
        new_stop_loss="89",
        old_sl_client_algo_id="old-sl-1",
        replacement_client_order_id="trail-1",
        create_sl_order=lambda payload: {"status": "OK"},
        fetch_sl_status=lambda **kwargs: {"status": "OK"},
        cancel_old_sl=lambda **kwargs: {"status": "CANCELED"},
    )

    assert result == {
        "status": "blocked",
        "reason": "non_favorable_replacement_sl",
    }


def test_replacement_allows_favorable_short_sl():
    from apps.worker.app.engine.binance_exit_stop_loss_replacement import (
        replace_exit_stop_loss_authoritatively,
    )

    calls = []

    def fake_create_sl(order_payload):
        calls.append(("create", order_payload["side"], order_payload["stopPrice"]))
        return {"status": "OK", "data": {"algoId": 333}}

    def fake_fetch_status(*, client_algo_id, **kwargs):
        calls.append(("status", client_algo_id))
        return {
            "status": "OK",
            "response": {
                "status": "NEW",
                "algoId": 333,
                "clientAlgoId": client_algo_id,
            },
        }

    def fake_cancel_old(*, client_algo_id, **kwargs):
        calls.append(("cancel", client_algo_id))
        return {"status": "CANCELED", "clientAlgoId": client_algo_id}

    result = replace_exit_stop_loss_authoritatively(
        symbol="ETHUSDT",
        direction="SHORT",
        qty="0.5",
        entry_price="100",
        old_stop_loss="120",
        new_stop_loss="110",
        old_sl_client_algo_id="old-short-sl-1",
        replacement_client_order_id="trail-short-1",
        create_sl_order=fake_create_sl,
        fetch_sl_status=fake_fetch_status,
        cancel_old_sl=fake_cancel_old,
    )

    assert result["status"] == "replaced"
    assert result["new_sl_client_algo_id"] == "trail-short-1-SL"
    assert calls == [
        ("create", "BUY", "110"),
        ("status", "trail-short-1-SL"),
        ("cancel", "old-short-sl-1"),
    ]


def test_replacement_rejects_non_favorable_short_sl():
    from apps.worker.app.engine.binance_exit_stop_loss_replacement import (
        replace_exit_stop_loss_authoritatively,
    )

    result = replace_exit_stop_loss_authoritatively(
        symbol="ETHUSDT",
        direction="SHORT",
        qty="0.5",
        entry_price="100",
        old_stop_loss="120",
        new_stop_loss="121",
        old_sl_client_algo_id="old-short-sl-1",
        replacement_client_order_id="trail-short-1",
        create_sl_order=lambda payload: {"status": "OK"},
        fetch_sl_status=lambda **kwargs: {"status": "OK"},
        cancel_old_sl=lambda **kwargs: {"status": "CANCELED"},
    )

    assert result == {
        "status": "blocked",
        "reason": "non_favorable_replacement_sl",
    }


def test_replacement_reports_pending_cleanup_when_old_sl_cancel_fails():
    from apps.worker.app.engine.binance_exit_stop_loss_replacement import (
        replace_exit_stop_loss_authoritatively,
    )

    calls = []

    def fake_create_sl(order_payload):
        calls.append(("create", order_payload["clientAlgoId"]))
        return {"status": "OK", "data": {"algoId": 444}}

    def fake_fetch_status(*, client_algo_id, **kwargs):
        calls.append(("status", client_algo_id))
        return {
            "status": "OK",
            "response": {
                "status": "NEW",
                "algoId": 444,
                "clientAlgoId": client_algo_id,
            },
        }

    def fake_cancel_old(*, client_algo_id, **kwargs):
        calls.append(("cancel", client_algo_id))
        return {"status": "ERROR", "error": "cancel_failed"}

    result = replace_exit_stop_loss_authoritatively(
        symbol="BTCUSDT",
        direction="LONG",
        qty="0.01",
        entry_price="100",
        old_stop_loss="90",
        new_stop_loss="100",
        old_sl_client_algo_id="old-sl-1",
        replacement_client_order_id="trail-2",
        create_sl_order=fake_create_sl,
        fetch_sl_status=fake_fetch_status,
        cancel_old_sl=fake_cancel_old,
    )

    assert result == {
        "status": "replacement_pending_cleanup",
        "reason": "old_sl_cancel_failed",
        "old_sl_client_algo_id": "old-sl-1",
        "new_sl_client_algo_id": "trail-2-SL",
        "new_sl_algo_id": 444,
    }

    assert calls == [
        ("create", "trail-2-SL"),
        ("status", "trail-2-SL"),
        ("cancel", "old-sl-1"),
    ]
