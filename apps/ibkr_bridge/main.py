from fastapi import FastAPI, Response
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
    ib.connect("127.0.0.1", 4002, clientId=1)
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
def test_order():
    return JSONResponse(content={
        "success": True,
        "order_id": "DUMMY_ORDER_ID",
        "status": "filled",
        "filled_qty": 1,
        "symbol": "AAPL",
        "side": "BUY",
        "raw": {}
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
