from __future__ import annotations

from typing import Any

from apps.worker.app.engine.binance_algo_order_classifier import (
    classify_algo_order_evidence,
)
from apps.worker.app.engine.binance_algo_order_evidence import (
    extract_algo_order_evidence,
)


def build_exit_protection_evidence_view(
    *,
    sl_payload: dict[str, Any] | None,
    tp_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    sl_evidence = extract_algo_order_evidence(sl_payload)
    tp_evidence = extract_algo_order_evidence(tp_payload)

    sl_classification = classify_algo_order_evidence(sl_evidence)
    tp_classification = classify_algo_order_evidence(tp_evidence)

    classifications = {sl_classification, tp_classification}

    both_active_evidence_present = (
        sl_classification == "ACTIVE_EVIDENCE_PRESENT"
        and tp_classification == "ACTIVE_EVIDENCE_PRESENT"
    )

    return {
        "sl_evidence": sl_evidence,
        "tp_evidence": tp_evidence,
        "sl_classification": sl_classification,
        "tp_classification": tp_classification,
        "both_active_evidence_present": both_active_evidence_present,
        "active_protection_verifiable": False,
        "has_unknown": "UNKNOWN" in classifications,
        "has_inconsistent": "INCONSISTENT" in classifications,
    }
