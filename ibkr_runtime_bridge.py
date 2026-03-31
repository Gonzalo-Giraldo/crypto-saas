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


@app.post("/ibkr/paper/test-order")
async def ibkr_test_order(request: Request):
    return JSONResponse(
        status_code=501,
        content={
            "success": False,
            "error": "ibkr_test_order_not_implemented",
            "message": "Bridge connected to runtime but test-order not implemented yet",
        },
    )

