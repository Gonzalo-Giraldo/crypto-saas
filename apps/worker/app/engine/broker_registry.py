from apps.worker.app.engine.binance_adapter import BinanceBrokerAdapter


def get_broker_adapter(exchange: str, **kwargs):
    """
    Minimal broker registry. Resolves broker adapter by exchange name.
    - BINANCE: returns BinanceBrokerAdapter
    - IBKR: raises NotImplementedError (placeholder)
    - Others: raises NotImplementedError
    """
    ex = exchange.upper()
    if ex == "BINANCE":
        return BinanceBrokerAdapter(**kwargs)
    elif ex == "IBKR":
        raise NotImplementedError("IBKR broker adapter is not implemented yet. Please implement IBKRBrokerAdapter.")
    else:
        raise NotImplementedError(f"No broker adapter registered for exchange: {exchange}")
