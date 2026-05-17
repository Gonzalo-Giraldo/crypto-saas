from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from apps.api.app.main import app
from apps.api.app.api import deps
from apps.api.app.db.session import SessionLocal, get_db
from apps.api.app.models.user import User
from apps.api.app.services.scheduler_lifecycle_state import SchedulerLifecycleState
from apps.api.app.services.scheduler_runtime_state_service import AUTO_PICK_SCHEDULER_NAME
from apps.api.app.services.scheduler_tick_journal_service import record_scheduler_tick_journal


class _Query:
    def filter(self, *args, **kwargs):
        return self

    def scalar(self):
        return 0


class _DB:
    def query(self, *args, **kwargs):
        return _Query()


def _admin_user():
    return User(id="admin-1", email="admin@test.com", role="admin")


def test_runtime_status_projects_scheduler_lifecycle_without_frontend_inference(monkeypatch):
    from apps.api.app.api import runtime_status as module

    monkeypatch.setattr(
        module,
        "get_scheduler_lifecycle_state",
        lambda: SchedulerLifecycleState.RUNNING,
    )
    monkeypatch.setattr(
        module,
        "get_effective_scheduler_lifecycle_state",
        lambda: SchedulerLifecycleState.STOPPED,
    )
    monkeypatch.setattr(module, "is_scheduler_thread_alive", lambda: False)
    monkeypatch.setattr(module, "get_trading_enabled", lambda db: False)
    monkeypatch.setattr(module, "get_scheduler_runtime_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "load_recent_scheduler_tick_journal", lambda *args, **kwargs: [])

    app.dependency_overrides[get_db] = lambda: _DB()
    app.dependency_overrides[deps.get_current_user] = _admin_user

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/runtime/status",
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["scheduler_lifecycle"] == {
        "desired_state": "RUNNING",
        "effective_state": "STOPPED",
        "thread_alive": False,
    }


def test_runtime_status_projects_autopick_observation_payload():
    db = SessionLocal()

    started_at = datetime.now(timezone.utc)
    finished_at = started_at + timedelta(milliseconds=50)

    record_scheduler_tick_journal(
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
            "candidates": [
                {
                    "symbol": "BTCUSDT",
                    "final_score": 0.91,
                }
            ],
        },
        analytics_exported=False,
        mutation_attempted=False,
        mutation_executed=False,
    )

    db.commit()
    db.close()

    app.dependency_overrides[deps.get_current_user] = _admin_user

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/runtime/status",
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text

    payload = response.json()
    ticks = payload["scheduler_tick_journal"]
    assert len(ticks) >= 1

    row = ticks[0]

    assert row["decision_status"] == "SELECTED"
    assert row["selected_rank"] == 1
    assert row["ranked_count"] == 7
    assert row["top_n"] == 10
    assert row["analytics_exported"] is False

    observation_payload = row["observation_payload"]

    assert observation_payload["decision_status"] == "SELECTED"
    assert observation_payload["selected_symbol"] == "BTCUSDT"
    assert observation_payload["production_priority"] is True
    assert observation_payload["candidates"][0]["symbol"] == "BTCUSDT"
