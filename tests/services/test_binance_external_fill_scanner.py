import pytest
from apps.api.app.services.binance_external_fill_scanner import scan_binance_external_fills

class DummyDB:
    def __init__(self, existing_ids):
        self._existing = existing_ids

    def execute(self, *args, **kwargs):
        class R:
            def __init__(self, rows):
                self._rows = rows
            def fetchall(self):
                return self._rows
        return R([(tid,) for tid in self._existing])

def test_inserts_only_new_trades():
    db = DummyDB(existing_ids={"1"})

    trades = [
        {"id": "1"},
        {"id": "2"},
    ]

    def fetch(*args, **kwargs):
        return trades

    def persist(db, trades, user_id, account_id, market):
        return trades

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
    assert result["skipped_existing_count"] == 1
    assert "2" in result["inserted_trade_ids"]

def test_no_duplicates():
    db = DummyDB(existing_ids={"1","2"})

    def fetch(*args, **kwargs):
        return [{"id":"1"},{"id":"2"}]

    def persist(*args, **kwargs):
        return []

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

    assert result["inserted_count"] == 0
    assert result["skipped_existing_count"] == 2

def test_no_execution_ref_required():
    db = DummyDB(existing_ids=set())

    def fetch(*args, **kwargs):
        return [{"id":"10"}]

    def persist(db, trades, user_id, account_id, market):
        return trades

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

def test_reject_non_spot():
    db = DummyDB(existing_ids=set())

    with pytest.raises(ValueError):
        scan_binance_external_fills(
            db=db,
            user_id="u",
            account_id="a",
            symbol="BTCUSDT",
            market="FUTURES",
            api_key="k",
            api_secret="s",
            fetch_binance_trades=lambda **k: [],
            persist_binance_fills_db=lambda **k: [],
        )

def test_summary_counts():
    db = DummyDB(existing_ids={"1"})

    def fetch(*args, **kwargs):
        return [{"id":"1"},{"id":"2"},{"id":"3"}]

    def persist(db, trades, user_id, account_id, market):
        return trades

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
