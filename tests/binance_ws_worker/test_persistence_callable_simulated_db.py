from apps.binance_ws_worker.persistence_callable_simulated_db import (
    InMemoryFillStore,
    safe_simulated_db_persistence_callable,
)


def test_insert_new_fill():
    store = InMemoryFillStore()
    fn = safe_simulated_db_persistence_callable(store)

    result = fn(fills=[{"tradeId": "1", "orderId": "2"}])

    assert result["inserted"] == 1
    assert result["skipped"] == 0


def test_skip_duplicate_fill():
    store = InMemoryFillStore()
    fn = safe_simulated_db_persistence_callable(store)

    fn(fills=[{"tradeId": "1", "orderId": "2"}])
    result = fn(fills=[{"tradeId": "1", "orderId": "2"}])

    assert result["inserted"] == 0
    assert result["skipped"] == 1



def test_requires_order_id():
    store = InMemoryFillStore()
    fn = safe_simulated_db_persistence_callable(store)

    try:
        fn(fills=[{"tradeId": "1"}])
    except ValueError as exc:
        assert "orderId required" in str(exc)
    else:
        raise AssertionError("expected ValueError")
