from datetime import datetime, timezone

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
    AutopickObservationCandidate,
    AutopickObservationSnapshot,
)
from apps.api.app.data_runtime.session import DataBase
from apps.api.app.data_runtime.services.autopick_export_runner import (
    build_autopick_export_lines,
    compute_autopick_export_checksum,
)

def test_build_autopick_export_lines_is_deterministic_and_compact():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)

    DataBase.metadata.create_all(bind=engine)

    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with TestingSessionLocal() as db:
        db.add(
            AutopickObservationSnapshot(
                snapshot_id="snapshot-1",
                snapshot_hash="hash-1",
                broker="BINANCE",
                market="FUTURES",
                decision_status="SELECTED",
                model_version="autopick-v1",
                selected_symbol="BTCUSDT",
                selected_side="BUY",
                selected_rank=1,
                selected_score=0.9,
                selected_reason="ok",
                ranked_count=1,
                partial_failure_count=0,
                rejected_candidates_json="[]",
                created_at=created_at,
            )
        )
        db.add(
            AutopickObservationCandidate(
                snapshot_id="snapshot-1",
                rank=1,
                symbol="BTCUSDT",
                side="BUY",
                valid=True,
                reason="ok",
                final_score=0.9,
                selected=True,
                entry_price_reference=100.0,
                features_json='{"momentum":0.5}',
                created_at=created_at,
            )
        )
        db.commit()

        lines = build_autopick_export_lines(
            db=db,
            from_created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            to_created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )

    assert lines == [
        '{"record_type":"snapshot","snapshot_id":"snapshot-1","snapshot_hash":"hash-1","broker":"BINANCE","market":"FUTURES","decision_status":"SELECTED","model_version":"autopick-v1","selected_symbol":"BTCUSDT","selected_side":"BUY","selected_rank":1,"selected_score":0.9,"selected_reason":"ok","ranked_count":1,"partial_failure_count":0,"rejected_candidates":[],"created_at":"2026-01-01T00:00:00+00:00"}',
        '{"record_type":"candidate","snapshot_id":"snapshot-1","rank":1,"symbol":"BTCUSDT","side":"BUY","valid":true,"reason":"ok","final_score":0.9,"selected":true,"entry_price_reference":100.0,"features":{"momentum":0.5},"created_at":"2026-01-01T00:00:00+00:00"}',
    ]


def test_compute_autopick_export_checksum_is_deterministic():
    lines = [
        '{"record_type":"snapshot","snapshot_id":"snapshot-1"}',
        '{"record_type":"candidate","snapshot_id":"snapshot-1"}',
    ]

    first = compute_autopick_export_checksum(lines)
    second = compute_autopick_export_checksum(lines)

    assert first == second
    assert len(first) == 64

def test_write_autopick_export_artifact_writes_jsonl_atomically(tmp_path):
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        write_autopick_export_artifact,
    )

    lines = [
        '{"record_type":"snapshot","snapshot_id":"snapshot-1"}',
        '{"record_type":"candidate","snapshot_id":"snapshot-1"}',
    ]

    result = write_autopick_export_artifact(
        export_root=tmp_path,
        export_id="export-1",
        lines=lines,
    )

    path = Path(result["path"])

    assert path.exists()
    assert path.name == "export-1.jsonl"
    assert path.read_text(encoding="utf-8") == (
        '{"record_type":"snapshot","snapshot_id":"snapshot-1"}\n'
        '{"record_type":"candidate","snapshot_id":"snapshot-1"}\n'
    )
    assert result["line_count"] == 2
    assert len(result["checksum"]) == 64
    assert not path.with_suffix(".jsonl.tmp").exists()

def test_run_autopick_export_batch_creates_exporting_then_exported_record(tmp_path):
    from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
        AutopickObservationExport,
    )
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        run_autopick_export_batch,
    )

    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)

    DataBase.metadata.create_all(bind=engine)

    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with TestingSessionLocal() as db:
        db.add(
            AutopickObservationSnapshot(
                snapshot_id="snapshot-1",
                snapshot_hash="hash-1",
                broker="BINANCE",
                market="FUTURES",
                decision_status="SELECTED",
                model_version="autopick-v1",
                selected_symbol="BTCUSDT",
                selected_side="BUY",
                selected_rank=1,
                selected_score=0.9,
                selected_reason="ok",
                ranked_count=1,
                partial_failure_count=0,
                rejected_candidates_json="[]",
                created_at=created_at,
            )
        )
        db.add(
            AutopickObservationCandidate(
                snapshot_id="snapshot-1",
                rank=1,
                symbol="BTCUSDT",
                side="BUY",
                valid=True,
                reason="ok",
                final_score=0.9,
                selected=True,
                entry_price_reference=100.0,
                features_json='{"momentum":0.5}',
                created_at=created_at,
            )
        )
        db.commit()

        result = run_autopick_export_batch(
            db=db,
            export_root=tmp_path,
            export_id="export-1",
            from_created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            to_created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        db.commit()

    path = Path(result["path"])

    assert path.exists()
    assert result["status"] == "EXPORTED"
    assert result["line_count"] == 2
    assert len(result["checksum"]) == 64

    with TestingSessionLocal() as db:
        row = db.query(AutopickObservationExport).filter_by(export_id="export-1").one()

    assert row.status == "EXPORTED"
    assert row.snapshot_count == 1
    assert row.candidate_count == 1
    assert row.destination_kind == "disk"
    assert row.destination_path_or_uri == str(path)
    assert row.checksum == result["checksum"]
    assert row.finished_at is not None
    assert row.purged_at is None

def test_verify_autopick_export_artifact_marks_export_verified(tmp_path):
    from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
        AutopickObservationExport,
    )
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        run_autopick_export_batch,
        verify_autopick_export_artifact,
    )

    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)

    DataBase.metadata.create_all(bind=engine)

    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with TestingSessionLocal() as db:
        db.add(
            AutopickObservationSnapshot(
                snapshot_id="snapshot-1",
                snapshot_hash="hash-1",
                broker="BINANCE",
                market="FUTURES",
                decision_status="SELECTED",
                model_version="autopick-v1",
                selected_symbol="BTCUSDT",
                selected_side="BUY",
                selected_rank=1,
                selected_score=0.9,
                selected_reason="ok",
                ranked_count=1,
                partial_failure_count=0,
                rejected_candidates_json="[]",
                created_at=created_at,
            )
        )
        db.add(
            AutopickObservationCandidate(
                snapshot_id="snapshot-1",
                rank=1,
                symbol="BTCUSDT",
                side="BUY",
                valid=True,
                reason="ok",
                final_score=0.9,
                selected=True,
                entry_price_reference=100.0,
                features_json='{"momentum":0.5}',
                created_at=created_at,
            )
        )
        db.commit()

        exported = run_autopick_export_batch(
            db=db,
            export_root=tmp_path,
            export_id="export-verify-1",
            from_created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            to_created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        db.commit()

        row = db.query(AutopickObservationExport).filter_by(
            export_id="export-verify-1"
        ).one()

        result = verify_autopick_export_artifact(
            row=row,
            expected_line_count=exported["line_count"],
        )
        db.commit()

    assert result["status"] == "VERIFIED"
    assert result["checksum"] == exported["checksum"]
    assert result["line_count"] == 2

    with TestingSessionLocal() as db:
        row = db.query(AutopickObservationExport).filter_by(
            export_id="export-verify-1"
        ).one()

    assert row.status == "VERIFIED"
    assert row.purged_at is None

def test_verify_autopick_export_artifact_marks_failed_on_checksum_mismatch(tmp_path):
    from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
        AutopickObservationExport,
    )
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        run_autopick_export_batch,
        verify_autopick_export_artifact,
    )

    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)

    DataBase.metadata.create_all(bind=engine)

    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with TestingSessionLocal() as db:
        db.add(
            AutopickObservationSnapshot(
                snapshot_id="snapshot-1",
                snapshot_hash="hash-1",
                broker="BINANCE",
                market="FUTURES",
                decision_status="SELECTED",
                model_version="autopick-v1",
                selected_symbol="BTCUSDT",
                selected_side="BUY",
                selected_rank=1,
                selected_score=0.9,
                selected_reason="ok",
                ranked_count=1,
                partial_failure_count=0,
                rejected_candidates_json="[]",
                created_at=created_at,
            )
        )
        db.add(
            AutopickObservationCandidate(
                snapshot_id="snapshot-1",
                rank=1,
                symbol="BTCUSDT",
                side="BUY",
                valid=True,
                reason="ok",
                final_score=0.9,
                selected=True,
                entry_price_reference=100.0,
                features_json='{"momentum":0.5}',
                created_at=created_at,
            )
        )
        db.commit()

        exported = run_autopick_export_batch(
            db=db,
            export_root=tmp_path,
            export_id="export-corrupt-1",
            from_created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            to_created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        db.commit()

        path = Path(exported["path"])
        path.write_text("corrupted\n", encoding="utf-8")

        row = db.query(AutopickObservationExport).filter_by(
            export_id="export-corrupt-1"
        ).one()

        try:
            verify_autopick_export_artifact(
                row=row,
                expected_line_count=exported["line_count"],
            )
        except ValueError as exc:
            db.commit()
            assert (
                "export_artifact_checksum_mismatch" in str(exc)
                or "export_artifact_line_count_mismatch" in str(exc)
            )
        else:
            raise AssertionError("checksum mismatch must fail closed")

    with TestingSessionLocal() as db:
        row = db.query(AutopickObservationExport).filter_by(
            export_id="export-corrupt-1"
        ).one()

    assert row.status == "FAILED"
    assert (
        "export_artifact_checksum_mismatch" in row.error_message
        or "export_artifact_line_count_mismatch" in row.error_message
    )
    assert row.purged_at is None

def test_build_autopick_export_manifest_is_deterministic():
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        build_autopick_export_manifest,
    )

    manifest = build_autopick_export_manifest(
        export_id="export-1",
        status="VERIFIED",
        artifact_path="/data/autopick/export-1.jsonl",
        checksum="a" * 64,
        line_count=2,
        snapshot_count=1,
        candidate_count=1,
    )

    assert manifest == {
        "artifact_path": "/data/autopick/export-1.jsonl",
        "candidate_count": 1,
        "checksum": "a" * 64,
        "export_id": "export-1",
        "line_count": 2,
        "snapshot_count": 1,
        "status": "VERIFIED",
    }

def test_write_autopick_export_manifest_artifact_writes_json(tmp_path):
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        build_autopick_export_manifest,
        write_autopick_export_manifest_artifact,
    )

    manifest = build_autopick_export_manifest(
        export_id="export-1",
        status="VERIFIED",
        artifact_path=str(tmp_path / "export-1.jsonl"),
        checksum="a" * 64,
        line_count=2,
        snapshot_count=1,
        candidate_count=1,
    )

    result = write_autopick_export_manifest_artifact(
        export_root=tmp_path,
        export_id="export-1",
        manifest=manifest,
    )

    path = Path(result["path"])

    assert path.exists()
    assert path.name == "export-1.manifest.json"
    assert path.read_text(encoding="utf-8") == (
        '{"artifact_path":"'
        + str(tmp_path / "export-1.jsonl")
        + '","candidate_count":1,"checksum":"'
        + ("a" * 64)
        + '","export_id":"export-1","line_count":2,"snapshot_count":1,"status":"VERIFIED"}\n'
    )
    assert result["manifest_path"] == str(path)
