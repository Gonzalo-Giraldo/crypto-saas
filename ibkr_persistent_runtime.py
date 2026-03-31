import asyncio
import json
import signal
import time
from pathlib import Path
from ib_insync import IB

HOST = "127.0.0.1"
PORT = 4002
CLIENT_ID = 1
STATUS_FILE = Path("/tmp/ibkr_runtime_status.json")

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
