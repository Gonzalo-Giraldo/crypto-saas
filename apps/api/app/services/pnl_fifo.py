"""
FIFO PnL matching helper for auditable realized PnL calculation.

- Broker-agnostic, deterministic, pure function.
- Receives lists of buy_fills and sell_fills (dicts or objects with required fields).
- Returns detailed match results, gross/net PnL, commission, unmatched qty, and audit trail.
"""
from typing import List, Dict, Any, Optional


def calculate_fifo_pnl(
    buy_fills: List[Dict[str, Any]],
    sell_fills: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Calculate realized PnL using FIFO matching between buy and sell fills.
    Each fill must have at least:
      - 'qty' (float, positive)
      - 'price' (float)
      - 'timestamp' or 'trade_time' (sortable)
      - 'commission_value_base' (float or None)
      - 'fill_id' (str or int, optional)
    Returns dict with:
      - matches: list of dicts (buy_fill_id, sell_fill_id, matched_qty, buy_price, sell_price, pnl_gross_segment, commission_base_segment, ...)
      - gross_pnl
      - total_commission_base
      - net_pnl
      - unmatched_sell_qty (if any)
      - unmatched_buy_lots (if any)
      - complete (bool)
    """
    # Defensive copy and sort
    buy_fills_sorted = sorted(buy_fills, key=lambda f: f.get('timestamp') or f.get('trade_time'))
    sell_fills_sorted = sorted(sell_fills, key=lambda f: f.get('timestamp') or f.get('trade_time'))

    buy_lots = []
    for fill in buy_fills_sorted:
        lot = {
            'fill_id': fill.get('fill_id'),
            'qty_remaining': float(fill['qty']),
            'price': float(fill['price']),
            'commission_value_base': fill.get('commission_value_base'),
            'timestamp': fill.get('timestamp') or fill.get('trade_time'),
            'raw': fill,
        }
        buy_lots.append(lot)

    matches = []
    gross_pnl = 0.0
    total_commission_base = 0.0
    unmatched_sell_qty = 0.0
    sell_segments = []

    for sell in sell_fills_sorted:
        sell_qty_remaining = float(sell['qty'])
        sell_price = float(sell['price'])
        sell_commission = sell.get('commission_value_base')
        sell_id = sell.get('fill_id')
        sell_time = sell.get('timestamp') or sell.get('trade_time')
        sell_segments_for_this = []
        while sell_qty_remaining > 0 and any(lot['qty_remaining'] > 0 for lot in buy_lots):
            # Find first buy lot with qty_remaining > 0
            for lot in buy_lots:
                if lot['qty_remaining'] > 0:
                    match_qty = min(lot['qty_remaining'], sell_qty_remaining)
                    buy_commission = lot['commission_value_base']
                    # Pro-rate commission if partial match
                    buy_commission_segment = (buy_commission * match_qty / float(lot['raw']['qty'])) if (buy_commission is not None) else 0.0
                    sell_commission_segment = (sell_commission * match_qty / float(sell['qty'])) if (sell_commission is not None) else 0.0
                    commission_base_segment = 0.0
                    if buy_commission is not None:
                        commission_base_segment += buy_commission_segment
                    if sell_commission is not None:
                        commission_base_segment += sell_commission_segment
                    pnl_gross_segment = match_qty * (sell_price - lot['price'])
                    match = {
                        'buy_fill_id': lot['fill_id'],
                        'sell_fill_id': sell_id,
                        'matched_qty': match_qty,
                        'buy_price': lot['price'],
                        'sell_price': sell_price,
                        'pnl_gross_segment': pnl_gross_segment,
                        'commission_base_segment': commission_base_segment if commission_base_segment > 0 else None,
                        'buy_commission_segment': buy_commission_segment if buy_commission is not None else None,
                        'sell_commission_segment': sell_commission_segment if sell_commission is not None else None,
                        'buy_timestamp': lot['timestamp'],
                        'sell_timestamp': sell_time,
                    }
                    matches.append(match)
                    sell_segments_for_this.append(match)
                    gross_pnl += pnl_gross_segment
                    total_commission_base += commission_base_segment
                    lot['qty_remaining'] -= match_qty
                    sell_qty_remaining -= match_qty
                    break
        if sell_qty_remaining > 0:
            unmatched_sell_qty += sell_qty_remaining
            # Optionally, expose the unmatched portion
            matches.append({
                'buy_fill_id': None,
                'sell_fill_id': sell_id,
                'matched_qty': 0.0,
                'unmatched_sell_qty': sell_qty_remaining,
                'sell_price': sell_price,
                'sell_timestamp': sell_time,
            })

    unmatched_buy_lots = [
        {
            'buy_fill_id': lot['fill_id'],
            'qty_remaining': lot['qty_remaining'],
            'buy_price': lot['price'],
            'buy_timestamp': lot['timestamp'],
        }
        for lot in buy_lots if lot['qty_remaining'] > 0
    ]

    net_pnl = gross_pnl - total_commission_base
    result = {
        'matches': matches,
        'gross_pnl': gross_pnl,
        'total_commission_base': total_commission_base,
        'net_pnl': net_pnl,
        'unmatched_sell_qty': unmatched_sell_qty if unmatched_sell_qty > 0 else None,
        'unmatched_buy_lots': unmatched_buy_lots if unmatched_buy_lots else None,
        'complete': unmatched_sell_qty == 0.0,
    }
    return result
