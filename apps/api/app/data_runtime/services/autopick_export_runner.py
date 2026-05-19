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
    destination_kind: str = "disk",
    storage_client=None,
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

    export_lines = [str(line) for line in lines]
    artifact_content = "".join(f"{line}\n" for line in export_lines)
    checksum = compute_autopick_export_checksum(export_lines)

    storage = get_autopick_export_storage(
        destination_kind=destination_kind,
        export_root=export_root,
        client=storage_client,
    )

    artifact = storage.write_text_artifact(
        export_id=export_id,
        suffix=".jsonl",
        content=artifact_content,
    )
    artifact["checksum"] = checksum
    artifact["line_count"] = len(export_lines)

    row = create_autopick_export_batch(
        db=db,
        export_id=export_id,
        from_created_at=from_created_at,
        to_created_at=to_created_at,
        snapshot_count=snapshot_count,
        candidate_count=candidate_count,
        destination_kind=str(destination_kind or "").strip().lower(),
        destination_path_or_uri=artifact["path"],
        checksum=artifact["checksum"],
    )

    apply_export_transition(row, "EXPORTING")
    row.finished_at = datetime.now(timezone.utc)
    apply_export_transition(row, "EXPORTED")

    manifest = build_autopick_export_manifest(
        export_id=export_id,
        status=row.status,
        artifact_path=artifact["path"],
        checksum=artifact["checksum"],
        line_count=artifact["line_count"],
        snapshot_count=snapshot_count,
        candidate_count=candidate_count,
    )

    manifest_artifact = storage.write_text_artifact(
        export_id=export_id,
        suffix=".manifest.json",
        content=json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ) + "\n",
    )

    db.flush()

    return {
        "export_id": export_id,
        "status": row.status,
        "path": artifact["path"],
        "checksum": artifact["checksum"],
        "line_count": artifact["line_count"],
        "snapshot_count": snapshot_count,
        "candidate_count": candidate_count,
        "manifest_path": manifest_artifact["path"],
    }

def _fail_export_verification(row, reason: str) -> None:
    row.error_message = str(reason)
    apply_export_transition(row, "FAILED")

def verify_autopick_export_artifact(
    *,
    row,
    expected_line_count: int,
) -> dict:
    """
    Verify local Auto-pick DATA export artifact integrity.

    DATA-plane only:
    - no runtime DB access
    - no broker access
    - no purge
    """

    path_value = str(getattr(row, "destination_path_or_uri", "") or "").strip()

    if not path_value:
        reason = "export_verification_requires_destination"
        _fail_export_verification(row, reason)
        raise ValueError(reason)

    path = Path(path_value)

    if not path.exists() or not path.is_file():
        reason = "export_artifact_not_found"
        _fail_export_verification(row, reason)
        raise ValueError(reason)

    lines = path.read_text(encoding="utf-8").splitlines()
    line_count = len(lines)

    if line_count != int(expected_line_count):
        reason = "export_artifact_line_count_mismatch"
        _fail_export_verification(row, reason)
        raise ValueError(reason)

    checksum = compute_autopick_export_checksum(lines)
    expected_checksum = str(getattr(row, "checksum", "") or "").strip()

    if not expected_checksum:
        reason = "export_verification_requires_checksum"
        _fail_export_verification(row, reason)
        raise ValueError(reason)

    if checksum != expected_checksum:
        reason = "export_artifact_checksum_mismatch"
        _fail_export_verification(row, reason)
        raise ValueError(reason)

    if getattr(row, "finished_at", None) is None:
        reason = "export_verification_requires_finished_at"
        _fail_export_verification(row, reason)
        raise ValueError(reason)

    apply_export_transition(row, "VERIFIED")

    return {
        "export_id": getattr(row, "export_id", None),
        "status": row.status,
        "path": str(path),
        "checksum": checksum,
        "line_count": line_count,
    }

def build_autopick_export_manifest(
    *,
    export_id: str,
    status: str,
    artifact_path: str,
    checksum: str,
    line_count: int,
    snapshot_count: int,
    candidate_count: int,
) -> dict:
    """
    Build deterministic Auto-pick DATA export manifest.

    DATA-plane contract only:
    - no runtime DB access
    - no broker access
    - no filesystem write
    - no lifecycle mutation
    """

    return {
        "artifact_path": str(artifact_path),
        "candidate_count": int(candidate_count),
        "checksum": str(checksum),
        "export_id": str(export_id),
        "line_count": int(line_count),
        "snapshot_count": int(snapshot_count),
        "status": str(status),
    }

def write_autopick_export_manifest_artifact(
    *,
    export_root,
    export_id: str,
    manifest: dict,
) -> dict:
    """
    Write deterministic Auto-pick DATA export manifest artifact atomically.

    DATA-plane contract only:
    - no runtime DB access
    - no broker access
    - no lifecycle mutation
    """

    safe_export_id = str(export_id).strip()

    if not safe_export_id:
        raise ValueError("export_id_required")

    if "/" in safe_export_id or "\\" in safe_export_id:
        raise ValueError("export_id_must_be_filename_safe")

    root = Path(export_root)
    root.mkdir(parents=True, exist_ok=True)

    final_path = root / f"{safe_export_id}.manifest.json"
    tmp_path = root / f"{safe_export_id}.manifest.json.tmp"

    payload = json.dumps(
        dict(manifest),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )

    with tmp_path.open("w", encoding="utf-8") as fh:
        fh.write(payload)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())

    os.replace(tmp_path, final_path)

    return {
        "manifest_path": str(final_path),
        "path": str(final_path),
    }

def validate_autopick_export_destination(
    *,
    destination_kind: str,
    destination_path_or_uri: str,
) -> dict:
    kind = str(destination_kind or "").strip().lower()
    uri = str(destination_path_or_uri or "").strip()

    if kind not in {"disk", "s3"}:
        raise ValueError("unsupported_export_destination_kind")

    if not uri:
        raise ValueError("export_destination_required")

    if kind == "s3" and not uri.startswith("s3://"):
        raise ValueError("s3_export_destination_requires_s3_uri")

    if kind == "disk" and uri.startswith("s3://"):
        raise ValueError("disk_export_destination_must_not_be_s3_uri")

    return {
        "destination_kind": kind,
        "destination_path_or_uri": uri,
    }

class DiskAutopickExportStorage:
    """
    Local disk Auto-pick export storage adapter.

    DATA-plane only:
    - no runtime DB access
    - no broker access
    - no AWS SDK
    """

    def __init__(self, *, export_root):
        self.export_root = Path(export_root)

    def write_text_artifact(
        self,
        *,
        export_id: str,
        suffix: str,
        content: str,
    ) -> dict:
        safe_export_id = str(export_id).strip()
        safe_suffix = str(suffix).strip()

        if not safe_export_id:
            raise ValueError("export_id_required")

        if "/" in safe_export_id or "\\" in safe_export_id:
            raise ValueError("export_id_must_be_filename_safe")

        if not safe_suffix.startswith("."):
            raise ValueError("artifact_suffix_must_start_with_dot")

        if "/" in safe_suffix or "\\" in safe_suffix:
            raise ValueError("artifact_suffix_must_be_filename_safe")

        self.export_root.mkdir(parents=True, exist_ok=True)

        final_path = self.export_root / f"{safe_export_id}{safe_suffix}"
        tmp_path = self.export_root / f"{safe_export_id}{safe_suffix}.tmp"

        with tmp_path.open("w", encoding="utf-8") as fh:
            fh.write(str(content))
            fh.flush()
            os.fsync(fh.fileno())

        os.replace(tmp_path, final_path)

        return {
            "path": str(final_path),
        }

def validate_s3_export_configuration(
    *,
    bucket: str,
    prefix: str,
    region: str,
    encryption: str,
) -> dict:
    bucket_value = str(bucket or "").strip()
    prefix_value = str(prefix or "").strip().strip("/")
    region_value = str(region or "").strip()
    encryption_value = str(encryption or "").strip()

    if not bucket_value:
        raise ValueError("s3_export_bucket_required")

    if not region_value:
        raise ValueError("s3_export_region_required")

    if not prefix_value:
        raise ValueError("s3_export_prefix_required")

    if encryption_value != "AES256":
        raise ValueError("unsupported_s3_export_encryption")

    return {
        "bucket": bucket_value,
        "prefix": prefix_value,
        "region": region_value,
        "encryption": encryption_value,
    }

class S3AutopickExportStorage:
    def __init__(
        self,
        *,
        bucket: str,
        prefix: str,
        region: str,
        encryption: str = "AES256",
        client=None,
    ):
        config = validate_s3_export_configuration(
            bucket=bucket,
            prefix=prefix,
            region=region,
            encryption=encryption,
        )

        self.bucket = config["bucket"]
        self.prefix = config["prefix"]
        self.region = config["region"]
        self.encryption = config["encryption"]
        self.client = client

        if self.client is None:
            import boto3
            self.client = boto3.client("s3", region_name=region)

    def _key(self, *, export_id: str, suffix: str) -> str:
        safe_export_id = str(export_id).strip()
        safe_suffix = str(suffix).strip()

        if not safe_export_id:
            raise ValueError("export_id_required")
        if "/" in safe_export_id or "\\" in safe_export_id:
            raise ValueError("export_id_must_be_filename_safe")
        if not safe_suffix.startswith("."):
            raise ValueError("artifact_suffix_must_start_with_dot")

        return f"{self.prefix}/{safe_export_id}{safe_suffix}"

    def write_text_artifact(self, *, export_id: str, suffix: str, content: str) -> dict:
        body = str(content).encode("utf-8")
        checksum = hashlib.sha256(body).hexdigest()
        key = self._key(export_id=export_id, suffix=suffix)

        metadata = {
            "sha256": checksum,
            "export-id": str(export_id),
            "content-bytes": str(len(body)),
        }

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ServerSideEncryption=self.encryption,
            Metadata=metadata,
        )

        verify_remote_autopick_export_artifact(
            client=self.client,
            bucket=self.bucket,
            key=key,
            expected_checksum=checksum,
            expected_bytes=len(body),
        )

        return {
            "path": f"s3://{self.bucket}/{key}",
            "bucket": self.bucket,
            "key": key,
            "checksum": checksum,
            "bytes": len(body),
        }

def verify_remote_autopick_export_artifact(
    *,
    client,
    bucket: str,
    key: str,
    expected_checksum: str,
    expected_bytes: int | None = None,
) -> dict:
    bucket_value = str(bucket or "").strip()
    key_value = str(key or "").strip()
    checksum_value = str(expected_checksum or "").strip()

    if not bucket_value:
        raise ValueError("s3_export_bucket_required")

    if not key_value:
        raise ValueError("s3_export_key_required")

    if not checksum_value:
        raise ValueError("s3_export_expected_checksum_required")

    head = client.head_object(Bucket=bucket_value, Key=key_value)

    remote_size = int(head.get("ContentLength", -1))
    remote_metadata = head.get("Metadata") or {}
    remote_checksum = str(remote_metadata.get("sha256") or "").strip()

    if expected_bytes is not None and remote_size != int(expected_bytes):
        raise ValueError("s3_export_remote_size_mismatch")

    if not remote_checksum:
        raise ValueError("s3_export_remote_checksum_missing")

    if remote_checksum != checksum_value:
        raise ValueError("s3_export_remote_checksum_mismatch")

    return {
        "bucket": bucket_value,
        "key": key_value,
        "checksum": remote_checksum,
        "bytes": remote_size,
    }

def get_autopick_export_storage(
    *,
    destination_kind: str,
    export_root,
    client=None,
):
    kind = str(destination_kind or "").strip().lower()

    if kind == "disk":
        return DiskAutopickExportStorage(export_root=export_root)

    if kind == "s3":
        from apps.api.app.core.config import settings

        return S3AutopickExportStorage(
            bucket=settings.AUTO_PICK_EXPORT_S3_BUCKET,
            prefix=settings.AUTO_PICK_EXPORT_S3_PREFIX,
            region=settings.AWS_REGION,
            encryption=settings.AUTO_PICK_EXPORT_S3_ENCRYPTION,
            client=client,
        )

    raise ValueError("unsupported_export_destination_kind")
