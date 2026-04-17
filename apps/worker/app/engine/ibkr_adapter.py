
from apps.worker.app.engine.broker_adapter import BrokerAdapter
import apps.worker.app.engine.ibkr_client as ibkr_client

class IBKRBrokerAdapter(BrokerAdapter):
    def __init__(self, api_key: str, api_secret: str, **kwargs):
        self.api_key = api_key
        self.api_secret = api_secret
        # Accept and ignore extra kwargs for compatibility

    def send_order(self, symbol: str, side: str, quantity: float, client_order_id: str = None, market: str = None, **kwargs):
        return ibkr_client.send_order(
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
        return ibkr_client.query_order_status(
            api_key=self.api_key,
            api_secret=self.api_secret,
            symbol=symbol,
            client_order_id=client_order_id,
            market=market,
            **kwargs,
        )

    def cancel_order(self, *, symbol: str, client_order_id: str, market: str = "SPOT", **kwargs):
        raise NotImplementedError("IBKR cancel_order not supported yet")
