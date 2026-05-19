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

def test_validate_autopick_export_destination_accepts_disk_and_s3():
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        validate_autopick_export_destination,
    )

    assert validate_autopick_export_destination(
        destination_kind="disk",
        destination_path_or_uri="/data/autopick/export-1.jsonl",
    ) == {
        "destination_kind": "disk",
        "destination_path_or_uri": "/data/autopick/export-1.jsonl",
    }

    assert validate_autopick_export_destination(
        destination_kind="s3",
        destination_path_or_uri="s3://crypto-saas-data/autopick/export-1.jsonl",
    ) == {
        "destination_kind": "s3",
        "destination_path_or_uri": "s3://crypto-saas-data/autopick/export-1.jsonl",
    }


def test_validate_autopick_export_destination_rejects_unknown_kind():
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        validate_autopick_export_destination,
    )

    try:
        validate_autopick_export_destination(
            destination_kind="http",
            destination_path_or_uri="https://example.com/export-1.jsonl",
        )
    except ValueError as exc:
        assert "unsupported_export_destination_kind" in str(exc)
        return

    raise AssertionError("unknown destination kind must fail closed")

def test_get_autopick_export_storage_returns_disk_storage(tmp_path):
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        get_autopick_export_storage,
    )

    storage = get_autopick_export_storage(
        destination_kind="disk",
        export_root=tmp_path,
    )

    result = storage.write_text_artifact(
        export_id="export-1",
        suffix=".txt",
        content="hello\n",
    )

    path = Path(result["path"])

    assert path.exists()
    assert path.name == "export-1.txt"
    assert path.read_text(encoding="utf-8") == "hello\n"


class FakeS3Client:
    def __init__(self):
        self.objects = {}

    def put_object(self, **kwargs):
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs
        return {}

    def head_object(self, **kwargs):
        obj = self.objects[(kwargs["Bucket"], kwargs["Key"])]
        return {
            "ContentLength": len(obj["Body"]),
            "Metadata": obj["Metadata"],
        }


def test_get_autopick_export_storage_returns_s3_storage_with_valid_config(monkeypatch, tmp_path):
    from apps.api.app.core.config import settings
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        get_autopick_export_storage,
    )

    monkeypatch.setattr(settings, "AWS_REGION", "sa-east-1")
    monkeypatch.setattr(settings, "AUTO_PICK_EXPORT_S3_BUCKET", "crypto-saas-data-ap")
    monkeypatch.setattr(settings, "AUTO_PICK_EXPORT_S3_PREFIX", "autopick/exports")
    monkeypatch.setattr(settings, "AUTO_PICK_EXPORT_S3_ENCRYPTION", "AES256")

    fake = FakeS3Client()

    storage = get_autopick_export_storage(
        destination_kind="s3",
        export_root=tmp_path,
        client=fake,
    )

    result = storage.write_text_artifact(
        export_id="export-1",
        suffix=".jsonl",
        content="hello\n",
    )

    assert result["path"] == "s3://crypto-saas-data-ap/autopick/exports/export-1.jsonl"
    assert result["bucket"] == "crypto-saas-data-ap"
    assert result["key"] == "autopick/exports/export-1.jsonl"
    assert result["bytes"] == 6

def test_run_autopick_export_batch_writes_artifact_and_manifest_to_s3(monkeypatch, tmp_path):
    from apps.api.app.core.config import settings
    from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
        AutopickObservationExport,
    )
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        run_autopick_export_batch,
    )

    monkeypatch.setattr(settings, "AWS_REGION", "sa-east-1")
    monkeypatch.setattr(settings, "AUTO_PICK_EXPORT_S3_BUCKET", "crypto-saas-data-ap")
    monkeypatch.setattr(settings, "AUTO_PICK_EXPORT_S3_PREFIX", "autopick/exports")
    monkeypatch.setattr(settings, "AUTO_PICK_EXPORT_S3_ENCRYPTION", "AES256")

    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)

    DataBase.metadata.create_all(bind=engine)

    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    fake = FakeS3Client()

    with TestingSessionLocal() as db:
        db.add(
            AutopickObservationSnapshot(
                snapshot_id="snapshot-s3-1",
                snapshot_hash="hash-s3-1",
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
                snapshot_id="snapshot-s3-1",
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
            export_id="export-s3-1",
            from_created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            to_created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            destination_kind="s3",
            storage_client=fake,
        )
        db.commit()

    assert result["status"] == "EXPORTED"
    assert result["path"] == "s3://crypto-saas-data-ap/autopick/exports/export-s3-1.jsonl"
    assert result["manifest_path"] == "s3://crypto-saas-data-ap/autopick/exports/export-s3-1.manifest.json"
    assert result["line_count"] == 2

    assert ("crypto-saas-data-ap", "autopick/exports/export-s3-1.jsonl") in fake.objects
    assert ("crypto-saas-data-ap", "autopick/exports/export-s3-1.manifest.json") in fake.objects

    with TestingSessionLocal() as db:
        row = db.query(AutopickObservationExport).filter_by(export_id="export-s3-1").one()

    assert row.status == "EXPORTED"
    assert row.destination_kind == "s3"
    assert row.destination_path_or_uri == result["path"]
    assert row.checksum == result["checksum"]

def test_verify_remote_autopick_export_artifact_accepts_matching_s3_head():
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        verify_remote_autopick_export_artifact,
    )

    fake = FakeS3Client()
    fake.put_object(
        Bucket="crypto-saas-data-ap",
        Key="autopick/exports/export-verify-1.jsonl",
        Body=b"hello\n",
        ServerSideEncryption="AES256",
        Metadata={
            "sha256": "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03",
        },
    )

    result = verify_remote_autopick_export_artifact(
        client=fake,
        bucket="crypto-saas-data-ap",
        key="autopick/exports/export-verify-1.jsonl",
        expected_checksum="5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03",
        expected_bytes=6,
    )

    assert result == {
        "bucket": "crypto-saas-data-ap",
        "key": "autopick/exports/export-verify-1.jsonl",
        "checksum": "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03",
        "bytes": 6,
    }


def test_verify_remote_autopick_export_artifact_rejects_checksum_mismatch():
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        verify_remote_autopick_export_artifact,
    )

    fake = FakeS3Client()
    fake.put_object(
        Bucket="crypto-saas-data-ap",
        Key="autopick/exports/export-verify-2.jsonl",
        Body=b"hello\n",
        ServerSideEncryption="AES256",
        Metadata={"sha256": "remote-checksum"},
    )

    try:
        verify_remote_autopick_export_artifact(
            client=fake,
            bucket="crypto-saas-data-ap",
            key="autopick/exports/export-verify-2.jsonl",
            expected_checksum="expected-checksum",
            expected_bytes=6,
        )
    except ValueError as exc:
        assert "s3_export_remote_checksum_mismatch" in str(exc)
        return

    raise AssertionError("checksum mismatch must fail closed")


def test_verify_remote_autopick_export_artifact_rejects_missing_checksum_metadata():
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        verify_remote_autopick_export_artifact,
    )

    fake = FakeS3Client()
    fake.put_object(
        Bucket="crypto-saas-data-ap",
        Key="autopick/exports/export-verify-3.jsonl",
        Body=b"hello\n",
        ServerSideEncryption="AES256",
        Metadata={},
    )

    try:
        verify_remote_autopick_export_artifact(
            client=fake,
            bucket="crypto-saas-data-ap",
            key="autopick/exports/export-verify-3.jsonl",
            expected_checksum="expected-checksum",
            expected_bytes=6,
        )
    except ValueError as exc:
        assert "s3_export_remote_checksum_missing" in str(exc)
        return

    raise AssertionError("missing checksum metadata must fail closed")

def test_validate_s3_export_configuration_accepts_expected_prod_contract():
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        validate_s3_export_configuration,
    )

    assert validate_s3_export_configuration(
        bucket="crypto-saas-data-ap",
        prefix="autopick/exports",
        region="sa-east-1",
        encryption="AES256",
    ) == {
        "bucket": "crypto-saas-data-ap",
        "prefix": "autopick/exports",
        "region": "sa-east-1",
        "encryption": "AES256",
    }


def test_validate_s3_export_configuration_rejects_missing_bucket():
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        validate_s3_export_configuration,
    )

    try:
        validate_s3_export_configuration(
            bucket="",
            prefix="autopick/exports",
            region="sa-east-1",
            encryption="AES256",
        )
    except ValueError as exc:
        assert "s3_export_bucket_required" in str(exc)
        return

    raise AssertionError("missing S3 bucket must fail closed")


def test_validate_s3_export_configuration_rejects_missing_region():
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        validate_s3_export_configuration,
    )

    try:
        validate_s3_export_configuration(
            bucket="crypto-saas-data-ap",
            prefix="autopick/exports",
            region="",
            encryption="AES256",
        )
    except ValueError as exc:
        assert "s3_export_region_required" in str(exc)
        return

    raise AssertionError("missing S3 region must fail closed")


def test_validate_s3_export_configuration_rejects_missing_prefix():
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        validate_s3_export_configuration,
    )

    try:
        validate_s3_export_configuration(
            bucket="crypto-saas-data-ap",
            prefix="",
            region="sa-east-1",
            encryption="AES256",
        )
    except ValueError as exc:
        assert "s3_export_prefix_required" in str(exc)
        return

    raise AssertionError("missing S3 prefix must fail closed")


def test_validate_s3_export_configuration_rejects_unsupported_encryption():
    from apps.api.app.data_runtime.services.autopick_export_runner import (
        validate_s3_export_configuration,
    )

    try:
        validate_s3_export_configuration(
            bucket="crypto-saas-data-ap",
            prefix="autopick/exports",
            region="sa-east-1",
            encryption="aws:kms",
        )
    except ValueError as exc:
        assert "unsupported_s3_export_encryption" in str(exc)
        return

    raise AssertionError("unsupported S3 encryption must fail closed")
