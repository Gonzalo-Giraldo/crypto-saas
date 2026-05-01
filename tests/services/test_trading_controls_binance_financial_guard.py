import pytest
from fastapi import HTTPException

from apps.api.app.services.trading_controls import assert_exposure_limits


class DummyUser:
    def __init__(self, id):
        self.id = id


class DummyDB:
    def execute(self, *args, **kwargs):
        class DummyResult:
            def fetchall(self):
                return []
            def mappings(self):
                return self
            def all(self):
                return []
            def scalars(self):
                return self
        return DummyResult()

    def commit(self):
        pass


def test_no_block_when_no_orders():
    db = DummyDB()
    user = DummyUser(id="user-1")

    # No orders → no bloqueo
    assert_exposure_limits(
        db,
        current_user=user,
        exchange="BINANCE",
        symbol="BTCUSDT",
        qty=0.1,
        price_estimate=10000,
    )
