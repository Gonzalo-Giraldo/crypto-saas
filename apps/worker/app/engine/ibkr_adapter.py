from apps.worker.app.engine.broker_adapter import BrokerAdapter
from apps.worker.app.engine.ibkr_client import send_ibkr_test_order

class IBKRBrokerAdapter(BrokerAdapter):
    def __init__(self, api_key: str, api_secret: str, **kwargs):
        self.api_key = api_key
        self.api_secret = api_secret
        # Accept and ignore extra kwargs for compatibility

    def send_order(self, symbol: str, side: str, quantity: float, client_order_id: str = None, market: str = None, **kwargs):
        # Delegate to the existing IBKR test order seam
        return send_ibkr_test_order(
            api_key=self.api_key,
            api_secret=self.api_secret,
            symbol=symbol,
            side=side,
            qty=quantity,
            client_order_id=client_order_id,
            market=market,
        )

    def query_order(self, symbol: str, client_order_id: str, market: str = None, **kwargs):
        # No query seam exists yet for IBKR; raise explicit error
        raise NotImplementedError("IBKRBrokerAdapter.query_order is not implemented yet. No IBKR query seam exists.")
