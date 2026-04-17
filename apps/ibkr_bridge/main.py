from fastapi import FastAPI, Response, Body
from fastapi.responses import JSONResponse

app = FastAPI(title="IBKR Bridge Stub", docs_url="/docs", openapi_url="/openapi.json")

@app.get("/health")
def health():
    return {"status": "ok"}

from ib_insync import IB

def get_ib_connection():
    import asyncio
    from ib_insync import IB

    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    ib = IB()
    ib.connect("127.0.0.1", 7497, clientId=1)
    return ib

@app.post("/ibkr/paper/account-status")
def account_status():
    try:
        ib = get_ib_connection()
        account_values = ib.accountSummary()

        balance = None
        currency = "USD"

        for v in account_values:
            if v.tag == "NetLiquidation":
                balance = float(v.value)
                currency = v.currency

        ib.disconnect()

        return {
            "success": True,
            "account_id": "IBKR_REAL",
            "balance": balance,
            "currency": currency,
            "positions": [],
            "raw": {}
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/ibkr/paper/test-order")
def test_order(payload: dict = Body(...)):
    ib = None
    try:
        # --- INPUT VALIDATION ---
        symbol = str(payload.get("symbol") or "").strip()
        side = str(payload.get("side") or "").upper().strip()
        qty = payload.get("qty")
        order_ref = str(payload.get("order_ref") or "").strip()

        if not symbol:
            return JSONResponse(content={"success": False, "error": "input_error: missing_symbol"})
        if side not in {"BUY", "SELL"}:
            return JSONResponse(content={"success": False, "error": "input_error: invalid_side"})
        if not isinstance(qty, (int, float)) or qty <= 0:
            return JSONResponse(content={"success": False, "error": "input_error: invalid_qty"})
        if not order_ref:
            return JSONResponse(content={"success": False, "error": "input_error: missing_order_ref"})

        # --- IBKR CONNECTION ---
        try:
            ib = get_ib_connection()
        except Exception as e:
            return JSONResponse(content={
                "success": False,
                "error": f"ibkr_connection_error: {str(e)}"
            })

        from ib_insync import Stock, MarketOrder

        contract = Stock(symbol, "SMART", "USD")
        order = MarketOrder(side, qty)

        # correlación
        order.orderRef = order_ref

        # --- PLACE ORDER ---
        try:
            trade = ib.placeOrder(contract, order)
        except Exception as e:
            if ib:
                try:
                    ib.disconnect()
                except Exception:
                    pass
            return JSONResponse(content={
                "success": False,
                "error": f"ibkr_place_order_error: {str(e)}"
            })

        ib.sleep(1)

        status = None
        order_id = None

        if trade:
            status = str(trade.orderStatus.status)
            order_id = getattr(trade.order, "orderId", None)

        ib.disconnect()

        return JSONResponse(content={
            "success": True,
            "order_id": order_id,
            "status": status or "submitted",
            "order_ref": order_ref,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "raw": {}
        })

    except Exception as e:
        if ib:
            try:
                ib.disconnect()
            except Exception:
                pass
        return JSONResponse(content={
            "success": False,
            "error": f"unexpected_error: {str(e)}"
        })

from datetime import datetime
from fastapi import Body

@app.post("/ibkr/paper/trades")
def trades(payload: dict = Body(...)):
    data = payload
    symbol = data.get("symbol")
    client_order_id = data.get("client_order_id")
    trades_out = []
    raw = {}
    try:
        ib = get_ib_connection()
        # Buscar todas las ejecuciones (fills) abiertas
        executions = ib.reqExecutions()
        for exec_detail in executions:
            trade = exec_detail.execution
            contract = exec_detail.contract
            # Filtrar por symbol y client_order_id si están presentes
            if symbol and contract.symbol != symbol:
                continue
            # IBKR no expone client_order_id directo, pero puede estar en orderRef
            if client_order_id and trade.orderRef != client_order_id:
                continue
            trades_out.append({
                "trade_id": str(trade.execId),
                "symbol": contract.symbol,
                "qty": trade.shares,
                "price": trade.price,
                "timestamp": datetime.utcfromtimestamp(trade.time).isoformat() if isinstance(trade.time, (int, float)) else str(trade.time),
                "side": getattr(trade, "side", None),
                "account_id": getattr(trade, "acctNumber", None),
                "order_id": getattr(trade, "orderId", None),
                "perm_id": getattr(trade, "permId", None),
                "client_id": getattr(trade, "clientId", None),
                "order_ref": getattr(trade, "orderRef", None),
                "cum_qty": getattr(trade, "cumQty", None),
                "avg_price": getattr(trade, "avgPrice", None),
            })
        ib.disconnect()
        return JSONResponse(content={
            "success": True,
            "trades": trades_out,
            "raw": {}
        })
    except Exception as e:
        return JSONResponse(content={
            "success": True,
            "trades": [],
            "error": str(e),
            "raw": {}
        })
