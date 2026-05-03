import json
from pathlib import Path

# ⚠️ INPUT MANUAL: pega aquí eventos reales capturados (uno a uno)
# Este módulo NO abre WS, solo guarda eventos que tú pegues

OUTPUT_FILE = Path("apps/binance_ws/sample_events.jsonl")


def append_event(event: dict):
    with OUTPUT_FILE.open("a") as f:
        f.write(json.dumps(event) + "\n")


def main():
    print("Pega un JSON executionReport y presiona ENTER (Ctrl+C para salir):")

    raw = input("> ").strip()
    if not raw:
        print("EMPTY_INPUT")
        return
    event = json.loads(raw)
    append_event(event)
    print("EVENT_SAVED")


if __name__ == "__main__":
    main()
