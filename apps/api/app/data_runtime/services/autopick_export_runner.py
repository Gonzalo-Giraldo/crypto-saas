from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
    AutopickObservationCandidate,
    AutopickObservationSnapshot,
)
from datetime import datetime, timezone

def _iso(value) -> str | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    return str(value)

def _json_loads(value: str, fallback):
    try:
        return json.loads(value or "")
    except Exception:
        return fallback


def _dump(record: dict) -> str:
    return json.dumps(
        record,
        sort_keys=False,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def build_autopick_export_lines(
    *,
    db: Session,
    from_created_at: datetime,
    to_created_at: datetime,
) -> list[str]:
    """
    Build deterministic JSONL lines for Auto-pick DATA export.

    DATA-plane only:
    - no runtime DB access
    - no broker access
    - no purge
    - no state mutation
    """

    snapshots = db.execute(
        select(AutopickObservationSnapshot)
        .where(AutopickObservationSnapshot.created_at >= from_created_at)
        .where(AutopickObservationSnapshot.created_at < to_created_at)
        .order_by(
            AutopickObservationSnapshot.created_at.asc(),
            AutopickObservationSnapshot.snapshot_id.asc(),
        )
    ).scalars().all()

    snapshot_ids = [row.snapshot_id for row in snapshots]

    candidates = []
    if snapshot_ids:
        candidates = db.execute(
            select(AutopickObservationCandidate)
            .where(AutopickObservationCandidate.snapshot_id.in_(snapshot_ids))
            .order_by(
                AutopickObservationCandidate.snapshot_id.asc(),
                AutopickObservationCandidate.rank.asc(),
                AutopickObservationCandidate.id.asc(),
            )
        ).scalars().all()

    lines: list[str] = []

    for row in snapshots:
        lines.append(
            _dump(
                {
                    "record_type": "snapshot",
                    "snapshot_id": row.snapshot_id,
                    "snapshot_hash": row.snapshot_hash,
                    "broker": row.broker,
                    "market": row.market,
                    "decision_status": row.decision_status,
                    "model_version": row.model_version,
                    "selected_symbol": row.selected_symbol,
                    "selected_side": row.selected_side,
                    "selected_rank": row.selected_rank,
                    "selected_score": row.selected_score,
                    "selected_reason": row.selected_reason,
                    "ranked_count": row.ranked_count,
                    "partial_failure_count": row.partial_failure_count,
                    "rejected_candidates": _json_loads(
                        row.rejected_candidates_json,
                        [],
                    ),
                    "created_at": _iso(row.created_at),
                }
            )
        )

    for row in candidates:
        lines.append(
            _dump(
                {
                    "record_type": "candidate",
                    "snapshot_id": row.snapshot_id,
                    "rank": row.rank,
                    "symbol": row.symbol,
                    "side": row.side,
                    "valid": row.valid,
                    "reason": row.reason,
                    "final_score": row.final_score,
                    "selected": row.selected,
                    "entry_price_reference": row.entry_price_reference,
                    "features": _json_loads(row.features_json, {}),
                    "created_at": _iso(row.created_at),
                }
            )
        )

    return lines


def compute_autopick_export_checksum(lines: Iterable[str]) -> str:
    digest = hashlib.sha256()

    for line in lines:
        digest.update(str(line).encode("utf-8"))
        digest.update(b"\n")

    return digest.hexdigest()
