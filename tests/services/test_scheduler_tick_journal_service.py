from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.app.db.session import Base
from apps.api.app.services.scheduler_runtime_state_service import AUTO_PICK_SCHEDULER_NAME
from apps.api.app.services.scheduler_tick_journal_service import (
    load_recent_scheduler_tick_journal,
    record_scheduler_tick_journal,
)


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_record_scheduler_tick_journal_persists_operational_facts():
    db = _db()
    started_at = datetime.now(timezone.utc)
    finished_at = started_at + timedelta(milliseconds=25)

    row = record_scheduler_tick_journal(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        started_at=started_at,
        finished_at=finished_at,
        status="OK",
        dry_run=True,
        trading_enabled=False,
        candidate_symbol="BTCUSDT",
        candidate_score="91.2",
        execution_mode="dry_run",
        mutation_attempted=False,
        mutation_executed=False,
    )
    db.commit()

    loaded = load_recent_scheduler_tick_journal(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        limit=5,
    )

    assert row.tick_id
    assert len(loaded) == 1
    assert loaded[0].status == "OK"
    assert loaded[0].duration_ms == 25
    assert loaded[0].candidate_symbol == "BTCUSDT"
    assert loaded[0].candidate_score == "91.2"
    assert loaded[0].mutation_attempted is False
    assert loaded[0].mutation_executed is False


def test_load_recent_scheduler_tick_journal_orders_newest_first_and_limits():
    db = _db()
    base = datetime.now(timezone.utc)

    for idx in range(3):
        record_scheduler_tick_journal(
            db,
            scheduler_name=AUTO_PICK_SCHEDULER_NAME,
            started_at=base + timedelta(seconds=idx),
            finished_at=base + timedelta(seconds=idx, milliseconds=10),
            duration_ms=10,
            status="OK",
            dry_run=True,
            trading_enabled=False,
        )
    db.commit()

    rows = load_recent_scheduler_tick_journal(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        limit=2,
    )

    assert len(rows) == 2
    assert rows[0].started_at >= rows[1].started_at



def test_record_scheduler_tick_journal_persists_autopick_observation_projection():
    import json

    db = _db()
    started_at = datetime.now(timezone.utc)
    finished_at = started_at + timedelta(milliseconds=50)

    row = record_scheduler_tick_journal(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        started_at=started_at,
        finished_at=finished_at,
        status="OK",
        dry_run=True,
        trading_enabled=False,
        candidate_symbol="BTCUSDT",
        candidate_score="0.91",
        execution_mode="dry_run",
        decision_status="SELECTED",
        selected_rank=1,
        ranked_count=7,
        top_n=10,
        observation_payload={
            "decision_status": "SELECTED",
            "selected_symbol": "BTCUSDT",
            "production_priority": True,
        },
        analytics_exported=False,
        mutation_attempted=False,
        mutation_executed=False,
    )
    db.commit()

    loaded = load_recent_scheduler_tick_journal(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        limit=1,
    )[0]

    assert row.tick_id
    assert loaded.decision_status == "SELECTED"
    assert loaded.selected_rank == 1
    assert loaded.ranked_count == 7
    assert loaded.top_n == 10
    assert loaded.analytics_exported is False
    payload = json.loads(loaded.observation_payload_json)
    assert payload["selected_symbol"] == "BTCUSDT"
    assert payload["production_priority"] is True
