import json
from typing import Any

from .status import build_worker_status


def main() -> dict[str, Any]:
    status = build_worker_status()
    print("BINANCE_WS_WORKER_STATUS")
    print(json.dumps(status, indent=2, sort_keys=True))
    return status


if __name__ == "__main__":
    main()
