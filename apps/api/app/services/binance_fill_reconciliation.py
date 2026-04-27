from decimal import Decimal, InvalidOperation


def _to_decimal(value, field_name: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_name} must be decimal-compatible") from None

    if not decimal_value.is_finite():
        raise ValueError(f"{field_name} must be finite")

    return decimal_value


def _invalid_result(
    *,
    execution_ref,
    execution_ref_type,
    symbol,
    market,
    expected_qty,
    filled_qty="0",
    delta_qty="0",
    matched_fills_count=0,
    reason,
) -> dict:
    return {
        "execution_ref": execution_ref,
        "execution_ref_type": execution_ref_type,
        "symbol": symbol,
        "market": market,
        "expected_qty": str(expected_qty),
        "filled_qty": str(filled_qty),
        "delta_qty": str(delta_qty),
        "matched_fills_count": matched_fills_count,
        "status": "invalid",
        "safe_for_position_update": False,
        "reason": reason,
    }


def reconcile_binance_order_fills(
    *,
    execution_ref: str,
    execution_ref_type: str,
    expected_qty,
    symbol: str,
    market: str,
    fills: list[dict],
    qty_tolerance="0.00000001",
) -> dict:
    try:
        if not isinstance(execution_ref, str) or not execution_ref.strip():
            raise ValueError("execution_ref is required")
        normalized_execution_ref = execution_ref.strip()

        if execution_ref_type != "orderId":
            raise ValueError("execution_ref_type must be orderId")

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol is required")
        normalized_symbol = symbol.strip().upper()

        if not isinstance(market, str) or market.strip().upper() not in {"SPOT", "FUTURES"}:
            raise ValueError("market must be SPOT or FUTURES")
        normalized_market = market.strip().upper()

        normalized_expected_qty = _to_decimal(expected_qty, "expected_qty")
        if normalized_expected_qty <= 0:
            raise ValueError("expected_qty must be > 0")

        normalized_tolerance = _to_decimal(qty_tolerance, "qty_tolerance")
        if normalized_tolerance < 0:
            raise ValueError("qty_tolerance must be >= 0")

        if fills is None:
            fills = []
        if not isinstance(fills, list):
            raise ValueError("fills must be a list")

        matched_fills = []
        for fill in fills:
            if not isinstance(fill, dict):
                continue
            fill_order_id = fill.get("orderId", fill.get("order_id"))
            if str(fill_order_id) == normalized_execution_ref:
                matched_fills.append(fill)

        filled_qty = Decimal("0")
        for fill in matched_fills:
            fill_qty = fill.get("qty", fill.get("executedQty", fill.get("quantity")))
            filled_qty += _to_decimal(fill_qty, "fill.qty")

        delta_qty = normalized_expected_qty - filled_qty
        abs_delta_qty = abs(delta_qty)

        if abs_delta_qty <= normalized_tolerance:
            status = "matched"
            reason = "filled_qty_matches_expected_qty"
        elif filled_qty == 0:
            status = "missing"
            reason = "no_fills_matched_execution_ref"
        elif Decimal("0") < filled_qty < normalized_expected_qty:
            status = "partial"
            reason = "filled_qty_below_expected_qty"
        elif filled_qty > normalized_expected_qty + normalized_tolerance:
            status = "overfilled"
            reason = "filled_qty_above_expected_qty"
        else:
            status = "invalid"
            reason = "unclassified_fill_reconciliation_state"

        return {
            "execution_ref": normalized_execution_ref,
            "execution_ref_type": execution_ref_type,
            "symbol": normalized_symbol,
            "market": normalized_market,
            "expected_qty": str(normalized_expected_qty),
            "filled_qty": str(filled_qty),
            "delta_qty": str(delta_qty),
            "matched_fills_count": len(matched_fills),
            "status": status,
            "safe_for_position_update": status == "matched",
            "reason": reason,
        }

    except ValueError as exc:
        return _invalid_result(
            execution_ref=execution_ref,
            execution_ref_type=execution_ref_type,
            symbol=symbol,
            market=market,
            expected_qty=expected_qty,
            reason=str(exc),
        )
