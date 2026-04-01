import asyncio
import json
import signal
import time

from pathlib import Path
from ib_insync import IB, Stock, MarketOrder



HOST = "127.0.0.1"
PORT = 4002
CLIENT_ID = 1
STATUS_FILE = Path("/tmp/ibkr_runtime_status.json")
COMMAND_FILE = Path("/tmp/ibkr_runtime_command.json")
RESULT_FILE = Path("/tmp/ibkr_runtime_result.json")

ib = IB()
stop = False


def snapshot_positions():
    out = []
    try:
        for p in ib.positions():
            contract = getattr(p, "contract", None)
            out.append({
                "symbol": getattr(contract, "symbol", None),
                "qty": float(getattr(p, "position", 0.0) or 0.0),
                "avg_price": float(getattr(p, "avgCost", 0.0) or 0.0),
                "account": getattr(p, "account", None),
            })
    except Exception as e:
        return [], f"positions_snapshot_error: {type(e).__name__}: {e}"

    return out, None


def write_status(connected: bool, error: str | None = None, positions: list | None = None):
    payload = {
        "connected": connected,
        "client_id": CLIENT_ID,
        "host": HOST,
        "port": PORT,
        "error": error,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "positions": positions if positions is not None else [],
    }
    STATUS_FILE.write_text(json.dumps(payload))

def atomic_write_json(path: Path, data: dict):
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w") as f:
        json.dump(data, f)
        f.flush()
        import os
        os.fsync(f.fileno())
    tmp_path.replace(path)


def safe_remove(path: Path):
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def process_command_file():
    if not COMMAND_FILE.exists():
        return

    try:
        cmd = json.loads(COMMAND_FILE.read_text())
    except Exception as e:
        atomic_write_json(
            RESULT_FILE,
            {
                "request_id": None,
                "success": False,
                "error": f"invalid_command_file: {type(e).__name__}: {e}",
            },
        )
        safe_remove(COMMAND_FILE)
        return

    required = ["request_id", "symbol", "side", "qty"]
    if not all(k in cmd for k in required):
        atomic_write_json(
            RESULT_FILE,
            {
                "request_id": cmd.get("request_id"),
                "success": False,
                "error": "missing_fields",
            },
        )
        safe_remove(COMMAND_FILE)
        return

    request_id = cmd["request_id"]
    symbol = cmd["symbol"]
    side = cmd["side"]
    qty = cmd["qty"]
    order_ref = cmd.get("order_ref")

    if not symbol or not isinstance(symbol, str):
        atomic_write_json(
            RESULT_FILE,
            {
                "request_id": request_id,
                "success": False,
                "error": "invalid_symbol",
            },
        )
        safe_remove(COMMAND_FILE)
        return

    if side not in ("BUY", "SELL"):
        atomic_write_json(
            RESULT_FILE,
            {
                "request_id": request_id,
                "success": False,
                "error": "invalid_side",
            },
        )
        safe_remove(COMMAND_FILE)
        return

    try:
        qty_val = float(qty)
        if qty_val <= 0:
            raise ValueError()
    except Exception:
        atomic_write_json(
            RESULT_FILE,
            {
                "request_id": request_id,
                "success": False,
                "error": "invalid_qty",
            },
        )
        safe_remove(COMMAND_FILE)
        return

    try:
        contract = Stock(symbol, "SMART", "USD")
        order = MarketOrder(side, qty_val)
        if order_ref:
            order.orderRef = str(order_ref)

        trade = ib.placeOrder(contract, order)

        order_id = None
        status = None
        for _ in range(20):
            if trade.orderStatus and trade.orderStatus.status:
                status = trade.orderStatus.status
            if trade.order and trade.order.orderId:
                order_id = trade.order.orderId
            if order_id or status:
                break
            time.sleep(0.1)

        atomic_write_json(
            RESULT_FILE,
            {
                "request_id": request_id,
                "success": True,
                "status": status,
                "symbol": symbol,
                "qty": qty_val,
                "side": side,
                "order_ref": order_ref,
                "order_id": order_id,
            },
        )
    except Exception as e:
        atomic_write_json(
            RESULT_FILE,
            {
                "request_id": request_id,
                "success": False,
                "error": f"order_error: {type(e).__name__}: {e}",
            },
        )

    safe_remove(COMMAND_FILE)

def handle_stop(signum, frame):
    global stop
    print(f"[IBKR_RUNTIME] stop signal received: {signum}")
    stop = True


signal.signal(signal.SIGINT, handle_stop)
signal.signal(signal.SIGTERM, handle_stop)


def main():
    global stop

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    write_status(connected=False, error=None, positions=[])

    print(f"[IBKR_RUNTIME] connecting to {HOST}:{PORT} clientId={CLIENT_ID}")
    ib.connect(HOST, PORT, clientId=CLIENT_ID, timeout=2)

    positions, positions_error = snapshot_positions()
    initial_error = positions_error if positions_error else None

    print(f"[IBKR_RUNTIME] connected={ib.isConnected()} positions={len(positions)}")
    write_status(
        connected=ib.isConnected(),
        error=initial_error,
        positions=positions,
    )

    try:
        while not stop:
            process_command_file()
            connected = ib.isConnected()
            positions, positions_error = snapshot_positions()
            write_status(
                connected=connected,
                error=positions_error,
                positions=positions,
            )
            print(
                f"[IBKR_RUNTIME] heartbeat connected={connected} "
                f"positions={len(positions)} "
                f"time={time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            time.sleep(5)
    finally:
        if ib.isConnected():
            print("[IBKR_RUNTIME] disconnecting")
            ib.disconnect()
        write_status(connected=False, error=None, positions=[])
        print("[IBKR_RUNTIME] stopped")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        write_status(connected=False, error=f"{type(e).__name__}: {e}", positions=[])
        print(f"[IBKR_RUNTIME] ERROR {type(e).__name__}: {e}")
        raise
