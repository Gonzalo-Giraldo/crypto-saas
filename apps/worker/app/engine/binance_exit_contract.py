from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BinanceMarket(str, Enum):
    FUTURES = "FUTURES"


class BinancePositionDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class BinanceOrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class BinanceExitReason(str, Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"


@dataclass(frozen=True)
class BinanceExitContract:
    market: BinanceMarket
    position_direction: BinancePositionDirection
    entry_side: BinanceOrderSide
    exit_side: BinanceOrderSide
    exit_reason: BinanceExitReason
    reduce_only: bool = True


def build_binance_exit_contract(
    *,
    market: str | BinanceMarket,
    position_direction: str | BinancePositionDirection,
    exit_reason: str | BinanceExitReason,
) -> BinanceExitContract:
    normalized_market = BinanceMarket(str(market).upper())
    normalized_direction = BinancePositionDirection(str(position_direction).upper())
    normalized_reason = BinanceExitReason(str(exit_reason).upper())

    if normalized_market != BinanceMarket.FUTURES:
        raise ValueError("binance_market_must_be_FUTURES")

    if normalized_direction == BinancePositionDirection.LONG:
        return BinanceExitContract(
            market=normalized_market,
            position_direction=normalized_direction,
            entry_side=BinanceOrderSide.BUY,
            exit_side=BinanceOrderSide.SELL,
            exit_reason=normalized_reason,
            reduce_only=True,
        )

    if normalized_direction == BinancePositionDirection.SHORT:
        return BinanceExitContract(
            market=normalized_market,
            position_direction=normalized_direction,
            entry_side=BinanceOrderSide.SELL,
            exit_side=BinanceOrderSide.BUY,
            exit_reason=normalized_reason,
            reduce_only=True,
        )

    raise ValueError(f"Unsupported Binance Futures direction: {normalized_direction.value}")

@dataclass(frozen=True)
class ExitOrders:
    stop_loss_order: dict
    take_profit_order: dict

    def __post_init__(self):
        _validate_exit_order(
            self.stop_loss_order,
            expected_type="STOP_MARKET",
            field_name="stop_loss_order",
        )
        _validate_exit_order(
            self.take_profit_order,
            expected_type="TAKE_PROFIT_MARKET",
            field_name="take_profit_order",
        )


def _validate_exit_order(order: dict, *, expected_type: str, field_name: str) -> None:
    if not isinstance(order, dict):
        raise ValueError(f"{field_name}_must_be_dict")

    required = {
        "symbol",
        "side",
        "type",
        "stopPrice",
        "quantity",
        "reduceOnly",
        "clientAlgoId",
    }

    missing = sorted(key for key in required if key not in order)
    if missing:
        raise ValueError(f"{field_name}_missing_fields:{missing}")

    if order["type"] != expected_type:
        raise ValueError(f"{field_name}_type_must_be_{expected_type}")

    if order["reduceOnly"] is not True:
        raise ValueError(f"{field_name}_reduceOnly_must_be_true")

