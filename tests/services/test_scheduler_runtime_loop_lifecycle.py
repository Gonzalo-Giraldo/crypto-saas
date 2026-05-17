from apps.api.app.services import scheduler_runtime_loop as loop
from apps.api.app.services.scheduler_lifecycle_state import SchedulerLifecycleState


class _DeadThread:
    def is_alive(self):
        return False


class _LiveThread:
    def is_alive(self):
        return True


def test_effective_state_reports_stopped_when_stopping_thread_is_dead(monkeypatch):
    monkeypatch.setattr(loop, "_scheduler_lifecycle_state", SchedulerLifecycleState.STOPPING)
    monkeypatch.setattr(loop, "_scheduler_thread", _DeadThread())

    assert loop.get_scheduler_lifecycle_state() == SchedulerLifecycleState.STOPPING
    assert loop.get_effective_scheduler_lifecycle_state() == SchedulerLifecycleState.STOPPED


def test_effective_state_preserves_stopping_when_thread_is_alive(monkeypatch):
    monkeypatch.setattr(loop, "_scheduler_lifecycle_state", SchedulerLifecycleState.STOPPING)
    monkeypatch.setattr(loop, "_scheduler_thread", _LiveThread())

    assert loop.get_effective_scheduler_lifecycle_state() == SchedulerLifecycleState.STOPPING


def test_effective_state_reports_stopped_when_running_thread_is_dead(monkeypatch):
    monkeypatch.setattr(loop, "_scheduler_lifecycle_state", SchedulerLifecycleState.RUNNING)
    monkeypatch.setattr(loop, "_scheduler_thread", _DeadThread())

    assert loop.get_scheduler_lifecycle_state() == SchedulerLifecycleState.RUNNING
    assert loop.get_effective_scheduler_lifecycle_state() == SchedulerLifecycleState.STOPPED


def test_effective_state_preserves_running_when_thread_is_alive(monkeypatch):
    monkeypatch.setattr(loop, "_scheduler_lifecycle_state", SchedulerLifecycleState.RUNNING)
    monkeypatch.setattr(loop, "_scheduler_thread", _LiveThread())

    assert loop.get_effective_scheduler_lifecycle_state() == SchedulerLifecycleState.RUNNING


def test_effective_state_preserves_pause_requested_without_inventing_pause(monkeypatch):
    monkeypatch.setattr(loop, "_scheduler_lifecycle_state", SchedulerLifecycleState.PAUSE_REQUESTED)
    monkeypatch.setattr(loop, "_scheduler_thread", _LiveThread())

    assert loop.get_effective_scheduler_lifecycle_state() == SchedulerLifecycleState.PAUSE_REQUESTED
