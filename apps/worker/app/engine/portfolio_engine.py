"""
Portfolio Engine groundwork: in-memory portfolio state and accessors.
No persistence, no broker queries, no async.
"""

from typing import Optional, Dict


class Position:
    def __init__(self, symbol: str, quantity: float, average_price: Optional[float] = None, notional: Optional[float] = None):
        self.symbol = symbol
        self.quantity = quantity
        self.average_price = average_price
        self.notional = notional


class Balance:
    def __init__(self, asset: str, total: float, available: float):
        self.asset = asset
        self.total = total
        self.available = available


class BrokerPortfolioState:
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.balances: Dict[str, Balance] = {}

class PortfolioState:
    def __init__(self):
        # user_id -> broker -> BrokerPortfolioState
        self.user_portfolios: Dict[str, Dict[str, BrokerPortfolioState]] = {}


class PortfolioEngine:
    def __init__(self):
        self.state = PortfolioState()

    def _get_broker_portfolio(self, user_id: str, broker: str) -> BrokerPortfolioState:
        return self.state.user_portfolios.setdefault(user_id, {}).setdefault(broker, BrokerPortfolioState())

    def update_position(self, user_id: str, broker: str, symbol: str, quantity: float, average_price: Optional[float] = None):
        bp = self._get_broker_portfolio(user_id, broker)
        pos = bp.positions.get(symbol)
        if pos:
            pos.quantity = quantity
            if average_price is not None:
                pos.average_price = average_price
        else:
            bp.positions[symbol] = Position(symbol=symbol, quantity=quantity, average_price=average_price)

    def set_balance(self, user_id: str, broker: str, asset: str, total: float, available: Optional[float] = None):
        bp = self._get_broker_portfolio(user_id, broker)
        bal = bp.balances.get(asset)
        if bal:
            bal.total = total
            if available is not None:
                bal.available = available
        else:
            bp.balances[asset] = Balance(asset=asset, total=total, available=available if available is not None else total)

    def get_position(self, user_id: str, broker: str, symbol: str) -> Optional[Position]:
        bp = self.state.user_portfolios.get(user_id, {}).get(broker)
        if bp:
            return bp.positions.get(symbol)
        return None

    def get_balance(self, user_id: str, broker: str, asset: str) -> Optional[Balance]:
        bp = self.state.user_portfolios.get(user_id, {}).get(broker)
        if bp:
            return bp.balances.get(asset)
        return None

    def get_position_quantity(self, user_id: str, broker: str, symbol: str) -> float:
        pos = self.get_position(user_id, broker, symbol)
        if pos and pos.quantity is not None:
            return pos.quantity
        return 0.0

    def get_available_balance(self, user_id: str, broker: str, asset: str) -> float:
        bal = self.get_balance(user_id, broker, asset)
        if bal:
            if bal.available is not None:
                return bal.available
            elif bal.total is not None:
                return bal.total
        return 0.0

    def get_symbol_exposure(self, user_id: str, broker: str, symbol: str) -> float:
        pos = self.get_position(user_id, broker, symbol)
        if pos is not None:
            if pos.notional is not None:
                return pos.notional
            if pos.quantity is not None:
                return pos.quantity
        return 0.0

    def get_total_exposure(self, user_id: Optional[str] = None, broker: Optional[str] = None) -> float:
        total = 0.0
        if user_id is not None:
            brokers = self.state.user_portfolios.get(user_id, {})
            if broker is not None:
                bp = brokers.get(broker)
                if bp:
                    for pos in bp.positions.values():
                        total += pos.notional if pos.notional is not None else (pos.quantity if pos.quantity is not None else 0.0)
            else:
                for bp in brokers.values():
                    for pos in bp.positions.values():
                        total += pos.notional if pos.notional is not None else (pos.quantity if pos.quantity is not None else 0.0)
        else:
            for user_brokers in self.state.user_portfolios.values():
                for bp in user_brokers.values():
                    for pos in bp.positions.values():
                        total += pos.notional if pos.notional is not None else (pos.quantity if pos.quantity is not None else 0.0)
        return total

    def get_exposure_by_symbol(self, user_id: Optional[str] = None, broker: Optional[str] = None) -> dict:
        exposures = {}
        if user_id is not None:
            brokers = self.state.user_portfolios.get(user_id, {})
            if broker is not None:
                bp = brokers.get(broker)
                if bp:
                    for symbol, pos in bp.positions.items():
                        exposures[symbol] = pos.notional if pos.notional is not None else (pos.quantity if pos.quantity is not None else 0.0)
            else:
                for bp in brokers.values():
                    for symbol, pos in bp.positions.items():
                        exposures[symbol] = exposures.get(symbol, 0.0) + (pos.notional if pos.notional is not None else (pos.quantity if pos.quantity is not None else 0.0))
        else:
            for user_brokers in self.state.user_portfolios.values():
                for bp in user_brokers.values():
                    for symbol, pos in bp.positions.items():
                        exposures[symbol] = exposures.get(symbol, 0.0) + (pos.notional if pos.notional is not None else (pos.quantity if pos.quantity is not None else 0.0))
        return exposures

    def get_exposure_by_broker(self, user_id: str) -> dict:
        exposures = {}
        brokers = self.state.user_portfolios.get(user_id, {})
        for broker, bp in brokers.items():
            total = 0.0
            for pos in bp.positions.values():
                total += pos.notional if pos.notional is not None else (pos.quantity if pos.quantity is not None else 0.0)
            exposures[broker] = total
        return exposures

    def get_portfolio_snapshot(self, user_id: Optional[str] = None, broker: Optional[str] = None) -> dict:
        result = {}
        if user_id is not None:
            brokers = self.state.user_portfolios.get(user_id, {})
            if broker is not None:
                bp = brokers.get(broker)
                if bp:
                    result[broker] = {
                        "positions": {k: v.__dict__ for k, v in bp.positions.items()},
                        "balances": {k: v.__dict__ for k, v in bp.balances.items()}
                    }
            else:
                for b, bp in brokers.items():
                    result[b] = {
                        "positions": {k: v.__dict__ for k, v in bp.positions.items()},
                        "balances": {k: v.__dict__ for k, v in bp.balances.items()}
                    }
        else:
            for user, brokers in self.state.user_portfolios.items():
                result[user] = {}
                for b, bp in brokers.items():
                    result[user][b] = {
                        "positions": {k: v.__dict__ for k, v in bp.positions.items()},
                        "balances": {k: v.__dict__ for k, v in bp.balances.items()}
                    }
        return result
