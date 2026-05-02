import pytest
from apps.api.app.services.binance_external_fill_scanner import scan_binance_external_fills


class DummyDB:
    def __init__(self, existing_ids):
        self.existing_ids = existing_ids

    def execute(self, *args, **kwargs):
        class Result:
            def __init__(self, ids):
                self.ids = ids

            def fetchall(self):
                return [(i,) for i in self.ids]

        return Result(self.existing_ids)


def test_inserts_only_new_trades():
    db = DummyDB(existing_ids={"1"})

    trades = [
        {"id": "1"},
        {"id": "2"},
    ]

    def fetch(*args, **kwargs):
        return trades

    def persist(db, fills, user_id, account_id, broker, market):
        return {"inserted": len(fills), "skipped": 0}

    result = scan_binance_external_fills(
        db=db,
        user_id="u",
        account_id="a",
        symbol="BTCUSDT",
        market="SPOT",
        api_key="k",
        api_secret="s",
        fetch_binance_trades=fetch,
        persist_binance_fills_db=persist,
    )

    assert result["inserted_count"] == 1


def test_no_execution_ref_required():
    db = DummyDB(existing_ids=set())

    def fetch(*args, **kwargs):
        return [{"id": "10"}]

    def persist(db, fills, user_id, account_id, broker, market):
        return {"inserted": len(fills), "skipped": 0}

    result = scan_binance_external_fills(
        db=db,
        user_id="u",
        account_id="a",
        symbol="BTCUSDT",
        market="SPOT",
        api_key="k",
        api_secret="s",
        fetch_binance_trades=fetch,
        persist_binance_fills_db=persist,
    )

    assert result["inserted_count"] == 1


def test_summary_counts():
    db = DummyDB(existing_ids={"1"})

    def fetch(*args, **kwargs):
        return [{"id":"1"},{"id":"2"},{"id":"3"}]

    def persist(db, fills, user_id, account_id, broker, market):
        return {"inserted": len(fills), "skipped": 0}

    result = scan_binance_external_fills(
        db=db,
        user_id="u",
        account_id="a",
        symbol="BTCUSDT",
        market="SPOT",
        api_key="k",
        api_secret="s",
        fetch_binance_trades=fetch,
        persist_binance_fills_db=persist,
    )

    assert result["scanned_count"] == 3
    assert result["inserted_count"] == 2
    assert result["skipped_existing_count"] == 1


def test_market_rejected():
    db = DummyDB(existing_ids=set())

    def fetch(*args, **kwargs):
        return []

    def persist(*args, **kwargs):
        return {}

    with pytest.raises(ValueError):
        scan_binance_external_fills(
            db=db,
            user_id="u",
            account_id="a",
            symbol="BTCUSDT",
            market="FUTURES",
            api_key="k",
            api_secret="s",
            fetch_binance_trades=fetch,
            persist_binance_fills_db=persist,
        )
