import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import subprocess

STATUS_FILE = Path("/tmp/ibkr_runtime_status.json")

app = FastAPI(title="IBKR Runtime Bridge", docs_url="/docs", openapi_url="/openapi.json")


@app.get("/health")
def health():
    return {"status": "ok"}


def _read_runtime_status():
    if not STATUS_FILE.exists():
        return None

    try:
        return json.loads(STATUS_FILE.read_text())
    except Exception as e:
        return {
            "connected": False,
            "error": f"status_file_parse_error: {type(e).__name__}: {e}",
            "positions": [],
        }


@app.get("/ibkr/status")
def ibkr_status():
    try:
        result = subprocess.check_output(
            ["pgrep", "-f", "ibkr_persistent_runtime.py"]
        ).decode().strip()

        pids = [line.strip() for line in result.splitlines() if line.strip()]
        runtime_running = len(pids) > 0
        status_payload = _read_runtime_status()

        return JSONResponse(status_code=200, content={
            "runtime_running": runtime_running,
            "pids": pids,
            "process_count": len(pids),
            "runtime_status": status_payload,
        })

    except subprocess.CalledProcessError:
        return JSONResponse(status_code=500, content={
            "runtime_running": False,
            "pids": [],
            "process_count": 0,
            "runtime_status": _read_runtime_status(),
        })


@app.get("/ibkr/paper/account-status")
def ibkr_account_status():
    try:
        result = subprocess.check_output(
            ["pgrep", "-f", "ibkr_persistent_runtime.py"]
        ).decode().strip()

        pids = [line.strip() for line in result.splitlines() if line.strip()]
        runtime_running = len(pids) > 0
        status_payload = _read_runtime_status()

        if not runtime_running:
            return JSONResponse(status_code=503, content={
                "success": False,
                "connected": False,
                "source": "runtime",
                "error": "ibkr_runtime_not_running",
                "positions": [],
            })

        if not status_payload:
            return JSONResponse(status_code=503, content={
                "success": False,
                "connected": False,
                "source": "runtime",
                "error": "ibkr_runtime_status_missing",
                "positions": [],
            })

        if not status_payload.get("connected", False):
            return JSONResponse(status_code=503, content={
                "success": False,
                "connected": False,
                "source": "runtime",
                "client_id": status_payload.get("client_id"),
                "error": status_payload.get("error") or "ibkr_runtime_not_connected",
                "positions": status_payload.get("positions") or [],
            })

        return JSONResponse(status_code=200, content={
            "success": True,
            "connected": True,
            "source": "runtime",
            "client_id": status_payload.get("client_id"),
            "host": status_payload.get("host"),
            "port": status_payload.get("port"),
            "updated_at": status_payload.get("updated_at"),
            "positions": status_payload.get("positions") or [],
        })

    except subprocess.CalledProcessError:
        return JSONResponse(status_code=503, content={
            "success": False,
            "connected": False,
            "source": "runtime",
            "error": "ibkr_runtime_not_running",
            "positions": [],
        })

from fastapi import Request
import os
import time
import uuid

COMMAND_FILE = "/tmp/ibkr_runtime_command.json"
RESULT_FILE = "/tmp/ibkr_runtime_result.json"


def atomic_write_json(path: str, data: dict) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


@app.post("/ibkr/paper/test-order")
async def ibkr_test_order(request: Request):
    try:
        result = subprocess.check_output(
            ["pgrep", "-f", "ibkr_persistent_runtime.py"]
        ).decode().strip()
        pids = [line.strip() for line in result.splitlines() if line.strip()]
        runtime_running = len(pids) > 0
    except subprocess.CalledProcessError:
        runtime_running = False

    if not runtime_running:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "ibkr_runtime_not_running"},
        )

    status_payload = _read_runtime_status()
    if not status_payload or not status_payload.get("connected", False):
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "ibkr_runtime_not_connected"},
        )

    data = await request.json()
    symbol = data.get("symbol")
    side = data.get("side")
    qty = data.get("qty")
    order_ref = data.get("order_ref")

    if not symbol or not isinstance(symbol, str):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "invalid_symbol"},
        )

    if side not in ("BUY", "SELL"):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "invalid_side"},
        )

    try:
        qty_val = float(qty)
        if qty_val <= 0:
            raise ValueError()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "invalid_qty"},
        )

    request_id = str(uuid.uuid4())
    command = {
        "request_id": request_id,
        "symbol": symbol,
        "side": side,
        "qty": qty_val,
    }
    if order_ref is not None:
        command["order_ref"] = order_ref

    atomic_write_json(COMMAND_FILE, command)

    deadline = time.time() + 5
    while time.time() < deadline:
        if os.path.exists(RESULT_FILE):
            try:
                with open(RESULT_FILE, "r") as f:
                    result_payload = json.load(f)
            except Exception:
                time.sleep(0.05)
                continue

            if result_payload.get("request_id") == request_id:
                safe_remove(RESULT_FILE)
                return JSONResponse(status_code=200, content=result_payload)

        time.sleep(0.05)

    return JSONResponse(
        status_code=504,
        content={
            "success": False,
            "error": "timeout_waiting_result",
            "request_id": request_id,
        },
    )
