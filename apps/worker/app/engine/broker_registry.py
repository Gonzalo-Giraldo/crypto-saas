from apps.worker.app.engine.binance_adapter import BinanceBrokerAdapter
from apps.worker.app.engine.ibkr_adapter import IBKRBrokerAdapter

def get_broker_adapter(exchange: str, **kwargs):
    """
    Minimal broker registry. Resolves broker adapter by exchange name.
    - BINANCE: returns BinanceBrokerAdapter
    - IBKR: returns IBKRBrokerAdapter
    - Others: raises NotImplementedError
    """
    ex = exchange.upper()
    if ex == "BINANCE":
        return BinanceBrokerAdapter(**kwargs)
    elif ex == "IBKR":
        return IBKRBrokerAdapter(**kwargs)
    else:
        raise NotImplementedError(f"No broker adapter registered for exchange: {exchange}")
