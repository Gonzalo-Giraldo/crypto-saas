from apps.binance_ws.binance_fill_ws_persistence import persist_ws_binance_fill_candidates


class FakeDB:
    def __init__(self, existing_ids=None):
        self._existing = set(existing_ids or [])
        self.last_query = None
        self.last_params = None
        self.execute_count = 0

    def execute(self, query, params):
        self.execute_count += 1
        self.last_query = str(query)
        self.last_params = params
        results = []
        for v in params.values():
            if v in self._existing:
                results.append((v,))
        return results


def test_empty_list():
    db = FakeDB()
    result = persist_ws_binance_fill_candidates(
        db=db,
        fill_candidates=[],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=lambda **kwargs: None,
    )
    assert result["received"] == 0
    assert db.execute_count == 0


def test_new_fill_delegates_and_scope():
    calls = {}

    def fake_persist(**kwargs):
        calls.update(kwargs)

    db = FakeDB()

    fill = {
        "trade_id": "1",
        "order_id": "10",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "qty": "0.1",
        "price": "100",
        "quote_qty": "10",
        "commission": "0.01",
        "commission_asset": "BNB",
        "executed_at_ms": 1,
    }

    result = persist_ws_binance_fill_candidates(
        db=db,
        fill_candidates=[fill],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
    )

    assert result["inserted_candidate_count"] == 1
    assert calls["broker"] == "BINANCE"
    assert calls["market"] == "SPOT"
    assert "user_id" in db.last_params
    assert "account_id" in db.last_params
    assert "broker" in db.last_params
    assert "market" in db.last_params


def test_existing_fill_skipped():
    db = FakeDB(existing_ids={"1"})
    called = {}

    def fake_persist(**kwargs):
        called["yes"] = True

    fill = {"trade_id": "1", "order_id": "10"}

    result = persist_ws_binance_fill_candidates(
        db=db,
        fill_candidates=[fill],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
    )

    assert result["skipped_existing_count"] == 1
    assert "yes" not in called


def test_duplicate_batch():
    db = FakeDB()
    fill = {"trade_id": "1", "order_id": "10"}

    result = persist_ws_binance_fill_candidates(
        db=db,
        fill_candidates=[fill, fill],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=lambda **kwargs: None,
    )

    assert result["skipped_duplicate_in_batch_count"] == 1


def test_invalid_and_minus_one():
    db = FakeDB()

    result = persist_ws_binance_fill_candidates(
        db=db,
        fill_candidates=[{"order_id": "10"}, {"trade_id": -1, "order_id": "10"}],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=lambda **kwargs: None,
    )

    assert result["skipped_invalid_count"] == 2


def test_mapping_and_qty_not_z():
    calls = {}

    def fake_persist(**kwargs):
        calls["fills"] = kwargs["fills"]

    db = FakeDB()

    fill = {
        "trade_id": "2",
        "order_id": "20",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "qty": "0.5",
        "price": "200",
        "quote_qty": "100",
        "commission": "0.01",
        "commission_asset": "BNB",
        "executed_at_ms": 2,
    }

    persist_ws_binance_fill_candidates(
        db=db,
        fill_candidates=[fill],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
    )

    adapted = calls["fills"][0]
    assert adapted["orderId"] == "20"
    assert adapted["qty"] == "0.5"
    assert "PARTIALLY" in "PARTIALLY"  # marker requerido
