# MODULE: order_module
# PURPOSE: handle IBKR order → write command → wait result

import json
import os
import time
import uuid

IDEMPOTENCY_STORE = "/tmp/ibkr_order_idempotency.json"
COMMAND_FILE = "/tmp/ibkr_runtime_command.json"
RESULT_FILE = "/tmp/ibkr_runtime_result.json"


def load_store():
    if not os.path.exists(IDEMPOTENCY_STORE):
        return {}
    try:
        with open(IDEMPOTENCY_STORE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_store(store):
    tmp = IDEMPOTENCY_STORE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(store, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, IDEMPOTENCY_STORE)

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


def handle_order(data: dict):
    symbol = data.get("symbol")
    side = data.get("side")
    qty = data.get("qty")
    order_ref = data.get("order_ref")

    if not symbol or not isinstance(symbol, str):
        return {"success": False, "error": "invalid_symbol"}

    if side not in ("BUY", "SELL"):
        return {"success": False, "error": "invalid_side"}

    try:
        qty_val = float(qty)
        if qty_val <= 0:
            raise ValueError()
    except Exception:
        return {"success": False, "error": "invalid_qty"}

    request_id = data.get("request_id") or str(uuid.uuid4())

    store = load_store()

    if request_id in store:
        existing = store[request_id]
        existing_status = existing.get("status")
        created_at = float(existing.get("created_at", 0) or 0)
        age_seconds = time.time() - created_at if created_at else None

        if existing_status in ("completed", "failed", "PendingSubmit"):
            return {
                "success": False,
                "error": "duplicate_request_id",
                "existing": existing,
            }

        if existing_status == "in_progress":
            if age_seconds is not None and age_seconds <= 30:
                return {
                    "success": False,
                    "error": "duplicate_request_id",
                    "existing": existing,
                }

            store[request_id] = {
                **existing,
                "status": "recovered",
                "recovered_at": time.time(),
            }
            save_store(store)

    command = {
        "request_id": request_id,
        "symbol": symbol,
        "side": side,
        "qty": qty_val,
    }

    store[request_id] = {
        "status": "in_progress",
        "symbol": symbol,
        "side": side,
        "qty": qty_val,
        "order_ref": order_ref,
        "created_at": time.time(),
    }
    save_store(store)


    if order_ref is not None:
        command["order_ref"] = order_ref

    atomic_write_json(COMMAND_FILE, command)

    deadline = time.time() + 12

    while time.time() < deadline:
        if os.path.exists(RESULT_FILE):
            try:
                with open(RESULT_FILE, "r") as f:
                    result_payload = json.load(f)
            except Exception:
                time.sleep(0.05)
                continue

            if result_payload.get("request_id") == request_id:
                store[request_id] = {
                    **result_payload,
                    "status": "completed",
                    "broker_status": result_payload.get("status"),
                    "updated_at": time.time(),
                }
                save_store(store)

                safe_remove(RESULT_FILE)
                return result_payload

        time.sleep(0.05)

    timeout_payload = {
        "success": False,
        "error": "timeout_waiting_result",
        "request_id": request_id,
    }

    store[request_id] = {
        "status": "failed",
        "updated_at": time.time(),
        **timeout_payload,
    }
    save_store(store)

    return timeout_payload
