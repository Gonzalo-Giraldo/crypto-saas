from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
    AutopickObservationSnapshot,
)
from apps.api.app.services.auto_pick.binance.observation_contracts import (
    BinanceMarketObservationSnapshot,
)
from apps.api.app.services.auto_pick.contracts import AutoPickObservationReport


def persist_autopick_observation_snapshot(
    *,
    db: Session,
    snapshot: BinanceMarketObservationSnapshot,
    report: AutoPickObservationReport,
) -> AutopickObservationSnapshot:
    """
    Persist compact Auto-pick observation metadata into the isolated data DB.

    Data-plane only:
    - no runtime DB access
    - no Risk/Intent/Execution
    - no broker mutation
    - no raw klines/ticker archives
    - append-only by snapshot_id uniqueness
    """

    row = AutopickObservationSnapshot(
        snapshot_id=snapshot.snapshot_id,
        snapshot_hash=snapshot.snapshot_hash,
        broker=snapshot.broker,
        market=snapshot.market,
        decision_status=report.decision_status,
        selected_symbol=report.selected_symbol,
        selected_rank=report.selected_rank,
        ranked_count=int(report.ranked_count),
        partial_failure_count=int(snapshot.partial_failure_count),
        rejected_candidates_json=json.dumps(
            list(report.rejected_candidates),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ),
    )

    db.add(row)
    return row
