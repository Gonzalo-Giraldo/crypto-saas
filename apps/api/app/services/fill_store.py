import os
import json
import threading
from typing import Any

# Simple thread-safe file-based fill store (idempotent by tradeId)
class FillStore:
    _lock = threading.Lock()
    _store_path = os.path.join(os.path.dirname(__file__), "binance_fills_store.json")

    @classmethod
    def _load_store(cls) -> dict:
        if not os.path.isfile(cls._store_path):
            return {}
        with open(cls._store_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}

    @classmethod
    def _save_store(cls, store: dict) -> None:
        with open(cls._store_path, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, ensure_ascii=False)

    @classmethod
    def persist_binance_fills(
        cls,
        user_id: str,
        account_id: str,
        matched_trades: list[dict],
        trades_contains_unmatched: bool,
    ) -> dict[str, Any]:
        if trades_contains_unmatched:
            return {"persisted_count": 0, "skipped_count": 0, "rejected": True}
        key_prefix = f"{user_id}::{account_id}::binance"
        with cls._lock:
            store = cls._load_store()
            if key_prefix not in store:
                store[key_prefix] = {}
            fills = store[key_prefix]
            persisted = 0
            skipped = 0
            for trade in matched_trades:
                trade_id = trade.get("id") or trade.get("tradeId")
                if not trade_id:
                    continue
                if str(trade_id) in fills:
                    skipped += 1
                    continue
                fills[str(trade_id)] = trade
                persisted += 1
            store[key_prefix] = fills
            cls._save_store(store)
        return {"persisted_count": persisted, "skipped_count": skipped, "rejected": False}
