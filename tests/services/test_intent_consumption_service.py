import pytest

from apps.api.app.services.intent_consumption_service import _build_consumer, consume_intent


class FakeIntent:
    def __init__(self, lifecycle_status="CREATED"):
        self.lifecycle_status = lifecycle_status


class FakeResult:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class FakeDB:
    def __init__(self, existing=None):
        self.existing = existing
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((str(sql), params))
        if "SELECT 1" in str(sql):
            return FakeResult(self.existing)
        return FakeResult(None)


def test_build_consumer_uses_account_id():
    assert _build_consumer("u1", "BINANCE", "default") == "u1:BINANCE:default"


def test_build_consumer_uses_no_account_when_missing():
    assert _build_consumer("u1", "BINANCE", None) == "u1:BINANCE:no-account"


def test_consume_intent_inserts_consumption_and_marks_consumed(monkeypatch):
    db = FakeDB(existing=None)

    monkeypatch.setattr(
        "apps.api.app.services.intent_consumption_service.get_intent",
        lambda db_arg, intent_id: FakeIntent("CREATED"),
    )

    monkeypatch.setattr(
        "apps.api.app.services.intent_consumption_service.mark_intent_consumed",
        lambda db_arg, intent_id: FakeIntent("CONSUMED"),
    )

    result = consume_intent(
        db=db,
        intent_id="intent-1",
        user_id="u1",
        broker="BINANCE",
        account_id="default",
    )

    assert result["intent_id"] == "intent-1"
    assert result["consumer"] == "u1:BINANCE:default"
    assert result["lifecycle_status"] == "CONSUMED"
    assert result["already_consumed"] is False
    assert any("INSERT INTO intent_consumptions" in sql for sql, _ in db.executed)


def test_consume_intent_existing_consumption_marks_consumed_without_insert(monkeypatch):
    db = FakeDB(existing=(1,))

    monkeypatch.setattr(
        "apps.api.app.services.intent_consumption_service.get_intent",
        lambda db_arg, intent_id: FakeIntent("CREATED"),
    )

    monkeypatch.setattr(
        "apps.api.app.services.intent_consumption_service.mark_intent_consumed",
        lambda db_arg, intent_id: FakeIntent("CONSUMED"),
    )

    result = consume_intent(
        db=db,
        intent_id="intent-1",
        user_id="u1",
        broker="BINANCE",
        account_id="default",
    )

    assert result["lifecycle_status"] == "CONSUMED"
    assert result["already_consumed"] is True
    assert not any("INSERT INTO intent_consumptions" in sql for sql, _ in db.executed)


def test_consume_intent_rejects_non_created(monkeypatch):
    db = FakeDB(existing=None)

    monkeypatch.setattr(
        "apps.api.app.services.intent_consumption_service.get_intent",
        lambda db_arg, intent_id: FakeIntent("CANCELLED"),
    )

    with pytest.raises(ValueError, match="invalid_state_for_consumption:CANCELLED"):
        consume_intent(
            db=db,
            intent_id="intent-1",
            user_id="u1",
            broker="BINANCE",
            account_id="default",
        )


def test_consume_intent_rejects_missing_intent(monkeypatch):
    db = FakeDB(existing=None)

    monkeypatch.setattr(
        "apps.api.app.services.intent_consumption_service.get_intent",
        lambda db_arg, intent_id: None,
    )

    with pytest.raises(ValueError, match="intent_not_found"):
        consume_intent(
            db=db,
            intent_id="intent-1",
            user_id="u1",
            broker="BINANCE",
            account_id="default",
        )
