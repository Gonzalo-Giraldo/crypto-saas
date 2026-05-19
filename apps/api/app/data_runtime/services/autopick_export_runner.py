from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
    AutopickObservationCandidate,
    AutopickObservationSnapshot,
)

from apps.api.app.data_runtime.services.autopick_export_service import (
    apply_export_transition,
    create_autopick_export_batch,
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

def write_autopick_export_artifact(
    *,
    export_root,
    export_id: str,
    lines: Iterable[str],
) -> dict:
    """
    Write deterministic Auto-pick DATA export JSONL artifact atomically.

    DATA-plane only:
    - no runtime DB access
    - no broker access
    - no purge
    - no lifecycle mutation
    """

    safe_export_id = str(export_id).strip()

    if not safe_export_id:
        raise ValueError("export_id_required")

    if "/" in safe_export_id or "\\" in safe_export_id:
        raise ValueError("export_id_must_be_filename_safe")

    export_lines = [str(line) for line in lines]
    checksum = compute_autopick_export_checksum(export_lines)

    root = Path(export_root)
    root.mkdir(parents=True, exist_ok=True)

    final_path = root / f"{safe_export_id}.jsonl"
    tmp_path = root / f"{safe_export_id}.jsonl.tmp"

    with tmp_path.open("w", encoding="utf-8") as fh:
        for line in export_lines:
            fh.write(line)
            fh.write("\n")

        fh.flush()
        os.fsync(fh.fileno())

    os.replace(tmp_path, final_path)

    return {
        "path": str(final_path),
        "checksum": checksum,
        "line_count": len(export_lines),
    }

def run_autopick_export_batch(
    *,
    db: Session,
    export_root,
    export_id: str,
    from_created_at: datetime,
    to_created_at: datetime,
) -> dict:
    """
    Execute minimal Auto-pick DATA export batch.

    DATA-plane only:
    - creates export lifecycle row
    - writes local JSONL artifact
    - marks EXPORTED
    - no runtime DB access
    - no broker access
    - no verification
    - no purge
    """

    lines = build_autopick_export_lines(
        db=db,
        from_created_at=from_created_at,
        to_created_at=to_created_at,
    )

    snapshot_count = sum(
        1 for line in lines if '"record_type":"snapshot"' in line
    )
    candidate_count = sum(
        1 for line in lines if '"record_type":"candidate"' in line
    )

    if snapshot_count <= 0 and candidate_count <= 0:
        raise ValueError("export_batch_requires_rows")

    artifact = write_autopick_export_artifact(
        export_root=export_root,
        export_id=export_id,
        lines=lines,
    )

    row = create_autopick_export_batch(
        db=db,
        export_id=export_id,
        from_created_at=from_created_at,
        to_created_at=to_created_at,
        snapshot_count=snapshot_count,
        candidate_count=candidate_count,
        destination_kind="disk",
        destination_path_or_uri=artifact["path"],
        checksum=artifact["checksum"],
    )

    apply_export_transition(row, "EXPORTING")
    row.finished_at = datetime.now(timezone.utc)
    apply_export_transition(row, "EXPORTED")

    db.flush()

    return {
        "export_id": export_id,
        "status": row.status,
        "path": artifact["path"],
        "checksum": artifact["checksum"],
        "line_count": artifact["line_count"],
        "snapshot_count": snapshot_count,
        "candidate_count": candidate_count,
    }
