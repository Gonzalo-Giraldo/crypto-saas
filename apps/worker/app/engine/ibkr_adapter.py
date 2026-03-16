
from apps.worker.app.engine.broker_adapter import BrokerAdapter
from apps.worker.app.engine.ibkr_client import send_order, query_order_status, cancel_order

class IBKRBrokerAdapter(BrokerAdapter):
    def __init__(self, api_key: str, api_secret: str, **kwargs):
        self.api_key = api_key
        self.api_secret = api_secret
        # Accept and ignore extra kwargs for compatibility

    def send_order(self, symbol: str, side: str, quantity: float, client_order_id: str = None, market: str = None, **kwargs):
        return send_order(
            api_key=self.api_key,
            api_secret=self.api_secret,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_ref=client_order_id,
            market=market,
            **kwargs,
        )

    def query_order(self, symbol: str, client_order_id: str, market: str = None, **kwargs):
        return query_order_status(
            api_key=self.api_key,
            api_secret=self.api_secret,
            symbol=symbol,
            client_order_id=client_order_id,
            market=market,
            **kwargs,
        )

    def cancel_order(self, *, symbol: str, client_order_id: str, market: str = "SPOT", **kwargs):
        return cancel_order(
            api_key=self.api_key,
            api_secret=self.api_secret,
            symbol=symbol,
            client_order_id=client_order_id,
            market=market,
            **kwargs,
        )
