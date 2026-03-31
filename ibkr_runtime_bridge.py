from fastapi import FastAPI
from fastapi.responses import JSONResponse
import subprocess

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

        return JSONResponse(status_code=200, content={
            "runtime_running": True,
            "pids": pids,
            "process_count": len(pids),
        })

    except subprocess.CalledProcessError:
        return JSONResponse(status_code=500, content={
            "runtime_running": False,
            "pids": [],
            "process_count": 0,
        })
