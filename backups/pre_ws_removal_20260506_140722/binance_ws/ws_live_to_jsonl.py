import json
from pathlib import Path
from datetime import datetime

OUTPUT_FILE = Path("apps/binance_ws/sample_events.jsonl")

def append_event(event: dict):
    with OUTPUT_FILE.open("a") as f:
        f.write(json.dumps(event) + "\n")

def run_capture(messages):
    saved = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue

        event = msg.get("event")
        if not isinstance(event, dict):
            continue

        if event.get("e") != "executionReport":
            continue

        append_event(msg)
        saved += 1

    return {
        "saved": saved,
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    raise RuntimeError("Este módulo no se ejecuta standalone. Debe recibir messages desde WS externo.")
