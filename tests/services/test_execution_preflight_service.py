import pytest

from types import SimpleNamespace

from apps.api.app.services.execution_preflight_service import run_execution_preflight


class DummyDB:
    pass


def _intent(status: str):
    return SimpleNamespace(
        lifecycle_status=status,
        symbol="BTCUSDT",
        side="BUY",
        broker="BINANCE",
        asset_profile="CRYPTO",
    )


def test_intent_not_found(monkeypatch):
    def fake_get_intent(*, db, intent_id):
        return None

    monkeypatch.setattr(
        "apps.api.app.services.intent_service.get_intent",
        fake_get_intent,
    )

    with pytest.raises(ValueError, match="intent_not_found"):
        run_execution_preflight(db=DummyDB(), intent_id="x")


def test_reject_created(monkeypatch):
    def fake_get_intent(*, db, intent_id):
        return _intent("CREATED")

    monkeypatch.setattr(
        "apps.api.app.services.intent_service.get_intent",
        fake_get_intent,
    )

    with pytest.raises(ValueError, match="intent_not_ready_for_execution"):
        run_execution_preflight(db=DummyDB(), intent_id="x")


def test_reject_cancelled(monkeypatch):
    def fake_get_intent(*, db, intent_id):
        return _intent("CANCELLED")

    monkeypatch.setattr(
        "apps.api.app.services.intent_service.get_intent",
        fake_get_intent,
    )

    with pytest.raises(ValueError, match="intent_not_ready_for_execution"):
        run_execution_preflight(db=DummyDB(), intent_id="x")


def test_accept_consumed(monkeypatch):
    def fake_get_intent(*, db, intent_id):
        return _intent("CONSUMED")

    monkeypatch.setattr(
        "apps.api.app.services.intent_service.get_intent",
        fake_get_intent,
    )

    out = run_execution_preflight(db=DummyDB(), intent_id="x")

    assert out["intent_id"] == "x"
    assert out["symbol"] == "BTCUSDT"
    assert out["side"] == "BUY"
    assert out["broker"] == "BINANCE"
    assert out["asset_profile"] == "CRYPTO"
    assert out["lifecycle_status"] == "CONSUMED"
