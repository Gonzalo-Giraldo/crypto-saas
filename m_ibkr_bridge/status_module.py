# MODULE: status_module
# PURPOSE: read runtime status from /tmp and return simplified response

import json
from pathlib import Path

STATUS_FILE = Path("/tmp/ibkr_runtime_status.json")


def handle_status():
    if not STATUS_FILE.exists():
        return {
            "success": False,
            "connected": False,
            "error": "status_file_missing",
        }

    try:
        data = json.loads(STATUS_FILE.read_text())
        return {
            "success": True,
            "connected": data.get("connected"),
            "positions": data.get("positions", []),
            "client_id": data.get("client_id"),
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"status_parse_error: {type(e).__name__}: {e}",
        }
