from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from apps.api.app.data_runtime.session import get_data_session_local
from apps.api.app.data_runtime.services.autopick_snapshot_persistence import (
    persist_autopick_observation_candidates,
    persist_autopick_observation_snapshot,
    persist_autopick_rejected_candidates,
)
from apps.api.app.services.auto_pick.binance.observation_contracts import (
    BinanceMarketObservationSnapshot,
)


def _stable_snapshot_id(observation_report) -> str:
    raw = "|".join(
        [
            str(getattr(observation_report, "started_at", "") or ""),
            str(getattr(observation_report, "finished_at", "") or ""),
            str(getattr(observation_report, "decision_status", "") or ""),
            str(getattr(observation_report, "selected_symbol", "") or ""),
            str(getattr(observation_report, "ranked_count", "") or ""),
        ]
    )
    return "autopick-" + sha256(raw.encode("utf-8")).hexdigest()[:24]


def persist_autopick_observation_report_to_data_db(observation_report) -> dict:
    """
    Persist Auto-pick observation report to isolated DATA DB only.

    DATA-plane only:
    - no runtime authority DB
    - no Risk/Intent/Execution
    - no broker mutation
    """

    snapshot = BinanceMarketObservationSnapshot(
        snapshot_id=_stable_snapshot_id(observation_report),
        broker="BINANCE",
        market="FUTURES",
        reads=(),
    )

    SessionLocal = get_data_session_local()

    with SessionLocal() as data_db:
        persist_autopick_observation_snapshot(
            db=data_db,
            snapshot=snapshot,
            report=observation_report,
        )
        candidates = persist_autopick_observation_candidates(
            db=data_db,
            snapshot_id=snapshot.snapshot_id,
            candidates=list(getattr(observation_report, "candidates", []) or []),
        )
        rejected = persist_autopick_rejected_candidates(
            db=data_db,
            snapshot_id=snapshot.snapshot_id,
            rejected_candidates=list(getattr(observation_report, "rejected_candidates", []) or [])[:10],
        )
        data_db.commit()

    return {
        "persisted": True,
        "snapshot_id": snapshot.snapshot_id,
        "candidate_count": len(candidates) + len(rejected),
        "persisted_at": datetime.now(timezone.utc).isoformat(),
    }
