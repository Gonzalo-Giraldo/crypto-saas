import asyncio
import signal
import sys
import time
from ib_insync import IB

HOST = "127.0.0.1"
PORT = 4002
CLIENT_ID = 1

ib = IB()
stop = False


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

    print(f"[IBKR_RUNTIME] connecting to {HOST}:{PORT} clientId={CLIENT_ID}")
    ib.connect(HOST, PORT, clientId=CLIENT_ID, timeout=2)

    print(f"[IBKR_RUNTIME] connected={ib.isConnected()}")

    try:
        while not stop:
            print(f"[IBKR_RUNTIME] heartbeat connected={ib.isConnected()} time={time.strftime('%Y-%m-%d %H:%M:%S')}")
            time.sleep(5)
    finally:
        if ib.isConnected():
            print("[IBKR_RUNTIME] disconnecting")
            ib.disconnect()
        print("[IBKR_RUNTIME] stopped")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[IBKR_RUNTIME] ERROR {type(e).__name__}: {e}")
        raise
