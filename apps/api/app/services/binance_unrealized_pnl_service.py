from decimal import Decimal, getcontext, InvalidOperation
from collections import defaultdict

getcontext().prec = 28


def _to_decimal(v):
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        raise ValueError("decimal_invalid")
    if not d.is_finite():
        raise ValueError("decimal_not_finite")
    return d


def compute_binance_unrealized_pnl(fills, current_price):
    current_price = _to_decimal(current_price)
    if current_price <= 0:
        raise ValueError("current_price_invalid")

    grouped = defaultdict(list)
    for f in fills:
        key = (
            f["user_id"],
            f["account_id"],
            f["broker"],
            f["market"],
            f["symbol"],
        )
        grouped[key].append(f)

    results = []

    for (user_id, account_id, broker, market, symbol), rows in grouped.items():
        if broker != "BINANCE" or market != "SPOT":
            continue

        buy_qty = Decimal("0")
        sell_qty = Decimal("0")
        buy_cost = Decimal("0")
        sell_proceeds = Decimal("0")
        fees = Decimal("0")

        for r in rows:
            side = str(r["side"]).upper()
            if side not in ("BUY", "SELL"):
                raise ValueError("side_invalid")

            qty = _to_decimal(r["qty"])
            quote = _to_decimal(r["quote_qty"])
            commission = _to_decimal(r["commission_usdt"])

            if qty < 0 or quote < 0 or commission < 0:
                raise ValueError("negative_value_invalid")

            if side == "BUY":
                buy_qty += qty
                buy_cost += quote
            else:
                sell_qty += qty
                sell_proceeds += quote

            fees += commission

        net_qty = buy_qty - sell_qty
        if net_qty < 0:
            raise ValueError("net_short_not_supported_for_spot")

        current_value = net_qty * current_price

        gross_pnl = sell_proceeds + current_value - buy_cost
        net_pnl = sell_proceeds + current_value - buy_cost - fees

        avg_entry = None
        if buy_qty > 0:
            avg_entry = buy_cost / buy_qty

        status = "OPEN" if net_qty > 0 else "CLOSED"

        results.append({
            "user_id": user_id,
            "account_id": account_id,
            "symbol": symbol,
            "net_qty": net_qty,
            "buy_cost_usdt": buy_cost,
            "sell_proceeds_usdt": sell_proceeds,
            "entry_fees_usdt": fees,
            "current_value_usdt": current_value,
            "gross_unrealized_pnl_usdt": gross_pnl,
            "net_unrealized_pnl_usdt": net_pnl,
            "avg_entry_price": avg_entry,
            "status": status,
        })

    return results
