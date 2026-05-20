import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
    AutopickObservationCandidate,
)
from apps.api.app.data_runtime.session import DataBase
from apps.api.app.services.auto_pick.contracts import AutoPickCandidateProjection
from apps.api.app.data_runtime.services.autopick_snapshot_persistence import (
    persist_autopick_observation_candidates,
)


def test_persist_autopick_observation_candidates_append_only():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)

    DataBase.metadata.create_all(bind=engine)

    candidates = [
        AutoPickCandidateProjection(
            rank=1,
            symbol="BTCUSDT",
            side="BUY",
            valid=True,
            reason="ok",
            final_score=0.9,
            selected=True,
            entry_price_reference=100.0,
            features={"momentum": 0.5},
        ),
        AutoPickCandidateProjection(
            rank=2,
            symbol="ETHUSDT",
            side="BUY",
            valid=True,
            reason="ok",
            final_score=0.8,
            selected=False,
            entry_price_reference=90.0,
            features={"momentum": 0.4},
        ),
    ]

    with TestingSessionLocal() as db:
        persist_autopick_observation_candidates(
            db=db,
            snapshot_id="snapshot-1",
            candidates=candidates,
        )
        db.commit()

    with TestingSessionLocal() as db:
        rows = db.execute(
            select(AutopickObservationCandidate).order_by(AutopickObservationCandidate.rank)
        ).scalars().all()

    assert len(rows) == 2
    assert rows[0].snapshot_id == "snapshot-1"
    assert rows[0].rank == 1
    assert rows[0].symbol == "BTCUSDT"
    assert rows[0].selected is True
    assert rows[0].final_score == 0.9
    assert json.loads(rows[0].features_json) == {"momentum": 0.5}


def test_persist_rejected_candidates_as_data_candidates():
    from apps.api.app.data_runtime.services.autopick_snapshot_persistence import (
        persist_autopick_rejected_candidates,
    )

    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)
    DataBase.metadata.create_all(bind=engine)

    rejected = [
        {"symbol": "BTCUSDT", "reason": "missing_1h_klines"},
        {"symbol": "ETHUSDT", "reason": "invalid_score"},
    ]

    with TestingSessionLocal() as db:
        rows = persist_autopick_rejected_candidates(
            db=db,
            snapshot_id="snapshot-rejected-1",
            rejected_candidates=rejected,
        )
        db.flush()

        assert len(rows) == 2
    assert rows[0].snapshot_id == "snapshot-rejected-1"
    assert rows[0].symbol == "BTCUSDT"
    assert rows[0].valid is False
    assert rows[0].selected is False
    assert rows[0].reason == "missing_1h_klines"
