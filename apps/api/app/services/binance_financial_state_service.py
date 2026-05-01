from apps.api.app.services.binance_fill_reconciliation import reconcile_binance_order_fills


def compute_binance_order_financial_state(
    *,
    execution_ref: str,
    symbol: str,
    market: str,
    fills,
    expected_qty,
) -> dict:
    """
    Deriva el estado financiero de una orden Binance.
    NO toca DB. Solo calcula.
    """
    reconciliation = reconcile_binance_order_fills(
        execution_ref=execution_ref,
        execution_ref_type="orderId",
        expected_qty=expected_qty,
        symbol=symbol,
        market=market,
        fills=fills,
    )

    status = reconciliation.get("status")

    if status == "matched":
        financial_state = "COMPLETE"
    elif status in ("partial", "missing"):
        financial_state = "INCOMPLETE"
    elif status == "overfilled":
        financial_state = "INVALID"
    else:
        financial_state = "UNKNOWN"

    return {
        "financial_state": financial_state,
        "reconciliation": reconciliation,
    }
