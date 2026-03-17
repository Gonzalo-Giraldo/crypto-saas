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
            def get_total_exposure(self) -> float:
                total = 0.0
                for pos in self.state.positions.values():
                    if pos.notional is not None:
                        total += pos.notional
                    elif pos.quantity is not None:
                        total += pos.quantity
                return total

            def get_exposure_by_symbol(self) -> dict:
                exposures = {}
                for symbol, pos in self.state.positions.items():
                    if pos.notional is not None:
                        exposures[symbol] = pos.notional
                    elif pos.quantity is not None:
                        exposures[symbol] = pos.quantity
                    else:
                        exposures[symbol] = 0.0
                return exposures

            def get_exposure_by_broker(self) -> dict:
                exposures = {}
                for pos in self.state.positions.values():
                    broker = pos.broker or "unknown"
                    value = pos.notional if pos.notional is not None else (pos.quantity if pos.quantity is not None else 0.0)
                    exposures[broker] = exposures.get(broker, 0.0) + value
                return exposures
        def update_position(self, symbol: str, quantity: float, average_price: Optional[float] = None, broker: Optional[str] = None):
            pos = self.state.positions.get(symbol)
            if pos:
                pos.quantity = quantity
                if average_price is not None:
                    pos.average_price = average_price
                if broker is not None:
                    pos.broker = broker
            else:
                self.state.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    average_price=average_price,
                    broker=broker
                )

        def set_balance(self, asset: str, total: float, available: Optional[float] = None, broker: Optional[str] = None):
            bal = self.state.balances.get(asset)
            if bal:
                bal.total = total
                if available is not None:
                    bal.available = available
                if broker is not None:
                    bal.broker = broker
            else:
                self.state.balances[asset] = Balance(
                    asset=asset,
                    total=total,
                    available=available if available is not None else total,
                    broker=broker
                )
    def __init__(self):
        self.state = PortfolioState()

    def get_position(self, symbol: str) -> Optional[Position]:
        return self.state.positions.get(symbol)

    def get_balance(self, asset: str) -> Optional[Balance]:
        return self.state.balances.get(asset)

    def get_symbol_exposure(self, symbol: str) -> float:
        pos = self.get_position(symbol)
        if pos is not None:
            if pos.notional is not None:
                return pos.notional
            if pos.quantity is not None:
                return pos.quantity
        return 0.0
