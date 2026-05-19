from datetime import datetime, timezone

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
