from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
    AutopickObservationCandidate,
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
        model_version=report.model_version,

        selected_symbol=report.selected_symbol,
        selected_side=report.selected.side if report.selected else None,
        selected_rank=report.selected_rank,
        selected_score=report.selected.final_score if report.selected else None,
        selected_reason=report.selected.reason if report.selected else None,
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



def persist_autopick_observation_candidates(
    *,
    db: Session,
    snapshot_id: str,
    candidates: list,
) -> list[AutopickObservationCandidate]:
    """
    Persist ranked Auto-pick candidates into the isolated data DB.

    Data-plane only:
    - no runtime DB access
    - no Risk/Intent/Execution
    - no broker mutation
    - append-only rows
    """

    rows: list[AutopickObservationCandidate] = []

    for candidate in candidates:
        row = AutopickObservationCandidate(
            snapshot_id=snapshot_id,
            rank=int(candidate.rank),
            symbol=candidate.symbol,
            side=candidate.side,
            valid=bool(candidate.valid),
            reason=candidate.reason,
            final_score=candidate.final_score,
            selected=bool(candidate.selected),
            entry_price_reference=candidate.entry_price_reference,
            features_json=json.dumps(
                dict(candidate.features),
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ),
        )
        db.add(row)
        rows.append(row)

    return rows


def persist_autopick_rejected_candidates(
    *,
    db: Session,
    snapshot_id: str,
    rejected_candidates: list,
) -> list[AutopickObservationCandidate]:
    rows: list[AutopickObservationCandidate] = []

    for idx, candidate in enumerate(rejected_candidates, start=1):
        row = AutopickObservationCandidate(
            snapshot_id=snapshot_id,
            rank=idx,
            symbol=candidate.get("symbol"),
            side=None,
            valid=False,
            reason=candidate.get("reason"),
            final_score=None,
            selected=False,
            entry_price_reference=None,
            features_json=json.dumps(
                dict(candidate.get("details") or {}),
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ),
        )
        db.add(row)
        rows.append(row)

    return rows
