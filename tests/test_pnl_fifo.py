"""
Focalized tests for FIFO PnL matching helper.
Cubre:
- caso completo: 1 BUY, 1 SELL
- caso múltiple BUY (10 y 15) + SELL parcial de 18
- caso pnl positivo
- caso pnl negativo
- caso con comisión
- caso con comisión ausente
- caso con SELL excediendo BUY disponible
"""
import pytest
from apps.api.app.services.pnl_fifo import calculate_fifo_pnl

def make_fill(qty, price, timestamp, fill_id=None, commission_value_base=None):
    return {
        'qty': qty,
        'price': price,
        'timestamp': timestamp,
        'fill_id': fill_id,
        'commission_value_base': commission_value_base,
    }

def test_fifo_pnl_simple_complete():
    buy = [make_fill(10, 100, 1, 'b1')]
    sell = [make_fill(10, 120, 2, 's1')]
    res = calculate_fifo_pnl(buy, sell)
    assert res['gross_pnl'] == 200
    assert res['net_pnl'] == 200
    assert res['complete']
    assert res['unmatched_sell_qty'] is None
    assert res['unmatched_buy_lots'] is None
    assert len(res['matches']) == 1
    m = res['matches'][0]
    assert m['matched_qty'] == 10
    assert m['buy_fill_id'] == 'b1'
    assert m['sell_fill_id'] == 's1'
    assert m['pnl_gross_segment'] == 200

def test_fifo_pnl_multiple_buy_partial_sell():
    buy = [make_fill(10, 100, 1, 'b1'), make_fill(15, 110, 2, 'b2')]
    sell = [make_fill(18, 130, 3, 's1')]
    res = calculate_fifo_pnl(buy, sell)
    # 10@100 + 8@110 sold at 130
    pnl = (10 * (130-100)) + (8 * (130-110))
    assert res['gross_pnl'] == pnl
    assert res['net_pnl'] == pnl
    assert res['complete']
    assert res['unmatched_sell_qty'] is None
    assert res['unmatched_buy_lots'] is not None
    assert res['unmatched_buy_lots'][0]['buy_fill_id'] == 'b2'
    assert res['unmatched_buy_lots'][0]['qty_remaining'] == 7
    # Check match breakdown
    segs = [m for m in res['matches'] if m.get('matched_qty', 0) > 0]
    assert len(segs) == 2
    assert segs[0]['matched_qty'] == 10
    assert segs[1]['matched_qty'] == 8

def test_fifo_pnl_positive():
    buy = [make_fill(5, 50, 1, 'b1')]
    sell = [make_fill(5, 70, 2, 's1')]
    res = calculate_fifo_pnl(buy, sell)
    assert res['gross_pnl'] == 100
    assert res['net_pnl'] == 100
    assert res['complete']

def test_fifo_pnl_negative():
    buy = [make_fill(5, 80, 1, 'b1')]
    sell = [make_fill(5, 70, 2, 's1')]
    res = calculate_fifo_pnl(buy, sell)
    assert res['gross_pnl'] == -50
    assert res['net_pnl'] == -50
    assert res['complete']

def test_fifo_pnl_with_commission():
    buy = [make_fill(10, 100, 1, 'b1', commission_value_base=2)]
    sell = [make_fill(10, 120, 2, 's1', commission_value_base=1)]
    res = calculate_fifo_pnl(buy, sell)
    assert res['gross_pnl'] == 200
    assert res['total_commission_base'] == 3
    assert res['net_pnl'] == 197
    seg = res['matches'][0]
    assert seg['commission_base_segment'] == 3
    assert seg['buy_commission_segment'] == 2
    assert seg['sell_commission_segment'] == 1

def test_fifo_pnl_commission_absent():
    buy = [make_fill(10, 100, 1, 'b1')]
    sell = [make_fill(10, 120, 2, 's1')]
    res = calculate_fifo_pnl(buy, sell)
    assert res['gross_pnl'] == 200
    assert res['total_commission_base'] == 0
    assert res['net_pnl'] == 200
    seg = res['matches'][0]
    assert seg['commission_base_segment'] is None
    assert seg['buy_commission_segment'] is None
    assert seg['sell_commission_segment'] is None

def test_fifo_pnl_sell_exceeds_buy():
    buy = [make_fill(5, 100, 1, 'b1')]
    sell = [make_fill(8, 120, 2, 's1')]
    res = calculate_fifo_pnl(buy, sell)
    # Only 5 can be matched
    assert res['gross_pnl'] == 5 * (120-100)
    assert res['net_pnl'] == 100
    assert not res['complete']
    assert res['unmatched_sell_qty'] == 3
    # There should be a match and an unmatched segment
    segs = [m for m in res['matches'] if m.get('matched_qty', 0) > 0]
    assert len(segs) == 1
    assert segs[0]['matched_qty'] == 5
    unmatched = [m for m in res['matches'] if m.get('unmatched_sell_qty')]
    assert len(unmatched) == 1
    assert unmatched[0]['unmatched_sell_qty'] == 3
