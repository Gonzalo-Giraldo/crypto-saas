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


def write_status(connected: bool, error: str | None = None):
    payload = {
        "connected": connected,
        "client_id": CLIENT_ID,
        "host": HOST,
        "port": PORT,
        "error": error,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
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

    write_status(connected=False, error=None)

    print(f"[IBKR_RUNTIME] connecting to {HOST}:{PORT} clientId={CLIENT_ID}")
    ib.connect(HOST, PORT, clientId=CLIENT_ID, timeout=2)

    print(f"[IBKR_RUNTIME] connected={ib.isConnected()}")
    write_status(connected=ib.isConnected(), error=None)

    try:
        while not stop:
            connected = ib.isConnected()
            write_status(connected=connected, error=None)
            print(f"[IBKR_RUNTIME] heartbeat connected={connected} time={time.strftime('%Y-%m-%d %H:%M:%S')}")
            time.sleep(5)
    finally:
        if ib.isConnected():
            print("[IBKR_RUNTIME] disconnecting")
            ib.disconnect()
        write_status(connected=False, error=None)
        print("[IBKR_RUNTIME] stopped")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        write_status(connected=False, error=f"{type(e).__name__}: {e}")
        print(f"[IBKR_RUNTIME] ERROR {type(e).__name__}: {e}")
        raise
