from typing import Any, Dict


def safe_noop_persistence_callable(**kwargs) -> Dict[str, int]:
    """
    Wrapper seguro para integración futura.

    - NO escribe en DB
    - NO llama servicios externos
    - Solo valida contrato mínimo
    """

    fills = kwargs.get("fills") or []

    if not isinstance(fills, list):
        raise ValueError("fills must be list")

    for f in fills:
        if not f.get("tradeId"):
            raise ValueError("tradeId required")
        if not f.get("orderId"):
            raise ValueError("orderId required")

    return {"inserted": 0, "skipped": len(fills)}
