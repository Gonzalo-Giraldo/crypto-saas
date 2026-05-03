from typing import Any, Dict


class InMemoryFillStore:
    def __init__(self):
        self.trade_ids = set()

    def exists(self, trade_id: str) -> bool:
        return trade_id in self.trade_ids

    def insert(self, trade_id: str):
        self.trade_ids.add(trade_id)


def safe_simulated_db_persistence_callable(store: InMemoryFillStore):
    def _callable(**kwargs) -> Dict[str, int]:
        fills = kwargs.get("fills") or []

        inserted = 0
        skipped = 0

        for f in fills:
            trade_id = f.get("tradeId")
            order_id = f.get("orderId")
            if not trade_id:
                raise ValueError("tradeId required")
            if not order_id:
                raise ValueError("orderId required")

            if store.exists(trade_id):
                skipped += 1
                continue

            store.insert(trade_id)
            inserted += 1

        return {"inserted": inserted, "skipped": skipped}

    return _callable
