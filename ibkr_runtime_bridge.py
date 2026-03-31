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


@app.get("/ibkr/status")
def ibkr_status():
    try:
        result = subprocess.check_output(
            ["pgrep", "-f", "ibkr_persistent_runtime.py"]
        ).decode().strip()

        pids = [line.strip() for line in result.splitlines() if line.strip()]

        runtime_running = len(pids) > 0

        status_payload = None
        if STATUS_FILE.exists():
            try:
                status_payload = json.loads(STATUS_FILE.read_text())
            except Exception as e:
                status_payload = {
                    "connected": False,
                    "error": f"status_file_parse_error: {type(e).__name__}: {e}",
                }

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
            "runtime_status": None,
        })
