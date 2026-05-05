from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from apps.worker.app.engine.binance_exit_contract import (
    BinanceExitReason,
    build_binance_exit_contract,
)


@dataclass(frozen=True)
class BinanceExitGuardResult:
    allowed: bool
    reason: str
    exit_side: str | None
    qty: Decimal | None
    exit_key: str | None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _normalize(value: Any) -> str:
    return str(value).upper().strip()


def build_binance_exit_key(
    *,
    market: str,
    position_direction: str,
    symbol: str,
    intent_id: str | None,
    exit_reason: str,
) -> str:
    return "|".join(
        [
            "BINANCE_EXIT",
            _normalize(position_direction),
            _normalize(symbol),
            str(intent_id or "NO_INTENT"),
            _normalize(exit_reason),
        ]
    )


def guard_binance_exit(
    *,
    market: str,
    position_direction: str,
    symbol: str,
    net_qty: Any,
    intent_id: str | None,
    exit_reason: str,
    is_duplicate_exit: Callable[[str], bool],
    current_sl: Any = None,
    new_sl: Any = None,
) -> BinanceExitGuardResult:
    try:
        contract = build_binance_exit_contract(
            market=market,
            position_direction=position_direction,
            exit_reason=exit_reason,
        )
    except Exception as exc:
        return BinanceExitGuardResult(
            allowed=False,
            reason=f"INVALID_CONTRACT:{exc}",
            exit_side=None,
            qty=None,
            exit_key=None,
        )

    qty = _decimal_or_none(net_qty)
    if qty is None or qty <= 0:
        return BinanceExitGuardResult(
            allowed=False,
            reason="INVALID_NET_QTY",
            exit_side=contract.exit_side.value,
            qty=qty,
            exit_key=None,
        )

    exit_key = build_binance_exit_key(
        market=contract.market.value,
        position_direction=contract.position_direction.value,
        symbol=symbol,
        intent_id=intent_id,
        exit_reason=contract.exit_reason.value,
    )

    if is_duplicate_exit(exit_key):
        return BinanceExitGuardResult(
            allowed=False,
            reason="DUPLICATE_EXIT",
            exit_side=contract.exit_side.value,
            qty=qty,
            exit_key=exit_key,
        )

    old_sl = None
    candidate_sl = None

    if contract.exit_reason == BinanceExitReason.TRAILING_STOP:
        old_sl = _decimal_or_none(current_sl)
        candidate_sl = _decimal_or_none(new_sl)

        if candidate_sl is None:
            return BinanceExitGuardResult(
                allowed=False,
                reason="MISSING_TRAILING_STOP",
                exit_side=contract.exit_side.value,
                qty=qty,
                exit_key=exit_key,
            )

    if old_sl is not None:
        if contract.position_direction.value == "LONG" and candidate_sl <= old_sl:
            return BinanceExitGuardResult(
                allowed=False,
                reason="NON_FAVORABLE_TRAILING_STOP",
                exit_side=contract.exit_side.value,
                qty=qty,
                exit_key=exit_key,
            )

        if contract.position_direction.value == "SHORT" and candidate_sl >= old_sl:
            return BinanceExitGuardResult(
                allowed=False,
                reason="NON_FAVORABLE_TRAILING_STOP",
                exit_side=contract.exit_side.value,
                qty=qty,
                exit_key=exit_key,
            )

    return BinanceExitGuardResult(
        allowed=True,
        reason="ALLOWED",
        exit_side=contract.exit_side.value,
        qty=qty,
        exit_key=exit_key,
    )
