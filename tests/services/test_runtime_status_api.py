def test_runtime_status_projection_counts_protection_states(monkeypatch):
    from fastapi.testclient import TestClient

    from apps.api.app.main import app
    from apps.api.app.db.session import Base, get_db
    from apps.api.app.models.binance_exit_protection import BinanceExitProtection
    from datetime import datetime, timezone

    from apps.api.app.services.scheduler_runtime_state_service import (
        AUTO_PICK_SCHEDULER_NAME,
        upsert_scheduler_runtime_state,
    )
    from apps.api.app.services.scheduler_tick_journal_service import (
        record_scheduler_tick_journal,
    )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    db.add(
        BinanceExitProtection(
            exit_key="active-protected",
            intent_id="intent-active",
            entry_execution_ref="exec-active",
            symbol="BTCUSDT",
            market="FUTURES",
            direction="LONG",
            filled_qty=1,
            avg_entry_price=100,
            sl_client_algo_id="sl-active",
            tp_client_algo_id="tp-active",
            sl_status="SUBMITTED",
            tp_status="SUBMITTED",
            protection_status="PROTECTED",
        )
    )
    db.add(
        BinanceExitProtection(
            exit_key="pending-cleanup",
            intent_id="intent-cleanup",
            entry_execution_ref="exec-cleanup",
            symbol="ETHUSDT",
            market="FUTURES",
            direction="LONG",
            filled_qty=1,
            avg_entry_price=100,
            sl_client_algo_id="sl-cleanup",
            tp_client_algo_id="tp-cleanup",
            sl_status="UNKNOWN",
            tp_status="SUBMITTED",
            protection_status="UNKNOWN",
            last_error="replacement_pending_cleanup:old_sl_cancel_failed",
        )
    )
    upsert_scheduler_runtime_state(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        last_tick_status="OK",
        last_tick_duration_ms=456,
        dry_run=True,
        trading_enabled=False,
        overlap_blocked=False,
        runtime_locked=False,
        last_candidate_symbol="BTCUSDT",
        last_candidate_score="88.1",
        last_execution_mode="dry_run",
    )
    now = datetime.now(timezone.utc)
    record_scheduler_tick_journal(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        started_at=now,
        finished_at=now,
        duration_ms=456,
        status="OK",
        dry_run=True,
        trading_enabled=False,
        candidate_symbol="BTCUSDT",
        candidate_score="88.1",
        execution_mode="dry_run",
        mutation_attempted=False,
        mutation_executed=False,
    )
    db.commit()
    db.close()

    def override_get_db():
        test_db = TestingSessionLocal()
        try:
            yield test_db
        finally:
            test_db.close()

    app.dependency_overrides[get_db] = override_get_db

    from apps.api.app.api import runtime_status as module

    monkeypatch.setattr(module, "get_trading_enabled", lambda db: False)

    client = TestClient(app)
    response = client.get("/api/runtime/status")

    app.dependency_overrides.clear()

    assert response.status_code in {200, 401, 403}
    if response.status_code != 200:
        return

    payload = response.json()

    assert payload["runtime"]["trading_enabled"] is False
    assert payload["protections"]["active_protected_positions"] == 1
    assert payload["protections"]["unknown_positions"] == 1
    assert payload["protections"]["pending_cleanup_positions"] == 1
    assert payload["autopick"]["last_tick_status"] == "OK"
    assert payload["autopick"]["last_tick_duration_ms"] == 456
    assert payload["autopick"]["overlap_blocked"] is False
    assert payload["autopick"]["runtime_locked"] is False
    assert payload["autopick"]["last_candidate_symbol"] == "BTCUSDT"
    assert payload["autopick"]["last_candidate_score"] == "88.1"
    assert payload["autopick"]["last_execution_mode"] == "dry_run"
    assert payload["autopick"]["scheduler_stale"] is False
    assert payload["autopick"]["operator_attention_required"] is False
    assert payload["autopick"]["stale_reason"] is None
    assert payload["autopick"]["ownership_lifecycle_state"] == "INIT"
    assert payload["autopick"]["ownership_valid"] is True
    assert payload["autopick"]["ownership_stale"] is False
    assert payload["autopick"]["ownership_operator_attention_required"] is False
    assert payload["autopick"]["ownership_reason"] == "ownership_not_present"
    assert payload["autopick"]["local_runtime_owner_id"] == "auto_pick_internal-runtime"
    assert isinstance(payload["autopick"]["local_runtime_instance_id"], str)
    assert payload["autopick"]["local_runtime_instance_id"].startswith("auto_pick_internal:")
    assert payload["autopick"]["session_authority_valid"] is False
    assert payload["autopick"]["session_authority_reason"] == "ownership_row_not_present"
    assert isinstance(payload["autopick"]["stale_duration_seconds"], int)
    assert len(payload["scheduler_tick_journal"]) == 1
    assert payload["scheduler_tick_journal"][0]["status"] == "OK"
    assert payload["scheduler_tick_journal"][0]["candidate_symbol"] == "BTCUSDT"
    assert payload["scheduler_tick_journal"][0]["mutation_attempted"] is False
    assert payload["scheduler_tick_journal"][0]["mutation_executed"] is False
    assert payload["mutations"] == []


def test_runtime_status_marks_scheduler_stale_when_no_tick_exists(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from apps.api.app.main import app
    from apps.api.app.db.session import Base, get_db

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        test_db = TestingSessionLocal()
        try:
            yield test_db
        finally:
            test_db.close()

    app.dependency_overrides[get_db] = override_get_db

    from apps.api.app.api import runtime_status as module

    monkeypatch.setattr(module, "get_trading_enabled", lambda db: False)

    client = TestClient(app)
    response = client.get("/api/runtime/status")

    app.dependency_overrides.clear()

    assert response.status_code in {200, 401, 403}
    if response.status_code != 200:
        return

    payload = response.json()

    assert payload["autopick"]["last_tick_status"] == "UNKNOWN"
    assert payload["autopick"]["source"] == "not_yet_instrumented"
    assert payload["autopick"]["scheduler_stale"] is True
    assert payload["autopick"]["stale_duration_seconds"] is None
    assert payload["autopick"]["operator_attention_required"] is True
    assert payload["autopick"]["stale_reason"] == "no_tick_recorded"
