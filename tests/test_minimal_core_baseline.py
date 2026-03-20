# Test file for minimal core baseline: MinimalExecutionRuntime, MarketDataEngine, RiskEngine, PortfolioEngine

import pytest
import time
from apps.worker.app.engine.minimal_execution_runtime import MinimalExecutionRuntime
from apps.worker.app.engine.market_data_engine import MarketDataEngine
from apps.worker.app.engine.risk_engine import RiskEngine, RiskIntent
from apps.worker.app.engine.portfolio_engine import PortfolioEngine

# ---- MinimalExecutionRuntime tests ----
def test_minimal_execution_runtime_accept_binance_stub():
    runtime = MinimalExecutionRuntime()
    result = runtime.submit_intent(
        user_id="user1",
        strategy_id="strat1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="buy",
        quantity=1.0,
        order_ref="order-1",
        mode="stub"
    )
    assert result["accepted"] is True
    assert result["order_ref"] == "order-1"

def test_minimal_execution_runtime_duplicate_order_ref():
    runtime = MinimalExecutionRuntime()
    runtime.submit_intent(
        user_id="user1",
        strategy_id="strat1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="buy",
        quantity=1.0,
        order_ref="order-dup",
        mode="stub"
    )
    result = runtime.submit_intent(
        user_id="user1",
        strategy_id="strat1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="buy",
        quantity=1.0,
        order_ref="order-dup",
        mode="stub"
    )
    assert result["idempotency_status"] == "duplicate"

def test_minimal_execution_runtime_reject_unsupported_broker():
    runtime = MinimalExecutionRuntime()
    result = runtime.submit_intent(
        user_id="user1",
        strategy_id="strat1",
        broker="kraken",
        market="spot",
        symbol="BTCUSDT",
        side="buy",
        quantity=1.0,
        order_ref="order-x",
        mode="stub"
    )
    assert result["accepted"] is False
    assert "broker" in result["reason"]

def test_minimal_execution_runtime_reject_unsupported_mode():
    runtime = MinimalExecutionRuntime()
    result = runtime.submit_intent(
        user_id="user1",
        strategy_id="strat1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="buy",
        quantity=1.0,
        order_ref="order-x",
        mode="live"
    )
    assert result["accepted"] is False
    assert "mode" in result["reason"]

def test_minimal_execution_runtime_reject_empty_order_ref():
    runtime = MinimalExecutionRuntime()
    result = runtime.submit_intent(
        user_id="user1",
        strategy_id="strat1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="buy",
        quantity=1.0,
        order_ref="",
        mode="stub"
    )
    assert result["accepted"] is False
    assert "order_ref" in result["reason"]

def test_minimal_execution_runtime_reject_nonpositive_quantity():
    runtime = MinimalExecutionRuntime()
    result = runtime.submit_intent(
        user_id="user1",
        strategy_id="strat1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="buy",
        quantity=0,
        order_ref="order-x",
        mode="stub"
    )
    assert result["accepted"] is False
    assert "quantity" in result["reason"]

def test_minimal_execution_runtime_reject_invalid_side():
    runtime = MinimalExecutionRuntime()
    result = runtime.submit_intent(
        user_id="user1",
        strategy_id="strat1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="hold",
        quantity=1.0,
        order_ref="order-x",
        mode="stub"
    )
    assert result["accepted"] is False
    assert "side" in result["reason"]

# ---- MarketDataEngine tests ----
def test_market_data_engine_set_and_get_price():
    mde = MarketDataEngine()
    mde.set_price("user1", "binance", "BTCUSDT", 42000.0)
    quote = mde.get_price("user1", "binance", "BTCUSDT")
    assert quote is not None
    assert quote.price == 42000.0

def test_market_data_engine_get_fresh_price_returns_value():
    mde = MarketDataEngine()
    mde.set_price("user1", "binance", "BTCUSDT", 42000.0)
    quote = mde.get_fresh_price("user1", "binance", "BTCUSDT")
    assert quote is not None
    assert quote.price == 42000.0

def test_market_data_engine_get_fresh_price_returns_none_if_stale():
    mde = MarketDataEngine()
    now = time.time()
    mde.set_price("user1", "binance", "BTCUSDT", 42000.0, timestamp=now - 100)
    quote = mde.get_fresh_price("user1", "binance", "BTCUSDT", now_ts=now)
    assert quote is None

# ---- RiskEngine tests ----
def test_risk_engine_evaluate_intent_accepts_base():
    re = RiskEngine()
    intent = RiskIntent(
        strategy_id="strat1",
        symbol="BTCUSDT",
        side="buy",
        quantity=1.0,
        broker="binance",
        market="spot"
    )
    result = re.evaluate_intent(intent)
    assert hasattr(result, "approved")
    assert result.approved is True

# ---- PortfolioEngine tests ----
def test_portfolio_engine_update_and_get_position_quantity():
    pe = PortfolioEngine()
    pe.update_position("user1", "binance", "BTCUSDT", 2.5)
    qty = pe.get_position_quantity("user1", "binance", "BTCUSDT")
    assert qty == 2.5

def test_portfolio_engine_set_and_get_available_balance():
    pe = PortfolioEngine()
    pe.set_balance("user1", "binance", "USDT", 1000.0)
    bal = pe.get_available_balance("user1", "binance", "USDT")
    assert bal == 1000.0

def test_portfolio_engine_get_portfolio_snapshot_contains_broker():
    pe = PortfolioEngine()
    pe.set_balance("user1", "binance", "USDT", 1000.0)
    snap = pe.get_portfolio_snapshot(user_id="user1")
    assert "binance" in snap
