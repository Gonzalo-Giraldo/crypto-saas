"""
Portfolio Engine groundwork: in-memory portfolio state and accessors.
No persistence, no broker queries, no async.
"""

from typing import Optional, Dict

class Position:
    def __init__(self, symbol: str, quantity: float, average_price: Optional[float] = None, notional: Optional[float] = None, broker: Optional[str] = None):
        self.symbol = symbol
        self.quantity = quantity
        self.average_price = average_price
        self.notional = notional
        self.broker = broker

class Balance:
    def __init__(self, asset: str, total: float, available: float, broker: Optional[str] = None):
        self.asset = asset
        self.total = total
        self.available = available
        self.broker = broker

class PortfolioState:
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.balances: Dict[str, Balance] = {}

class PortfolioEngine:
    def __init__(self):
        self.state = PortfolioState()

    def get_position(self, symbol: str) -> Optional[Position]:
        return self.state.positions.get(symbol)

    def get_balance(self, asset: str) -> Optional[Balance]:
        return self.state.balances.get(asset)

    def get_symbol_exposure(self, symbol: str) -> float:
        pos = self.get_position(symbol)
        if pos is not None and pos.notional is not None:
            return pos.notional
        return 0.0
