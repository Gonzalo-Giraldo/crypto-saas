import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
    AutopickObservationSnapshot,
)
from apps.api.app.data_runtime.session import DataBase
from apps.api.app.services.auto_pick.binance.observation_contracts import (
    BinanceMarketObservationSnapshot,
    BinanceMarketReadResult,
)
from apps.api.app.services.auto_pick.binance.snapshot_runtime import (
    run_binance_auto_pick_observation_from_snapshot,
)
from apps.api.app.data_runtime.services.autopick_snapshot_persistence import (
    persist_autopick_observation_snapshot,
)


def _ticker(symbol: str, quote_volume: str = "1000000"):
    return {
        "symbol": symbol,
        "quoteVolume": quote_volume,
        "priceChangePercent": "5",
        "lastPrice": "100",
    }


def _klines():
    return [
        ["0", "100", "110", "95", "108", "1000"],
        ["1", "108", "115", "107", "114", "1500"],
    ]


def test_persist_autopick_observation_snapshot_append_only():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)

    DataBase.metadata.create_all(bind=engine)

    snapshot = BinanceMarketObservationSnapshot(
        snapshot_id="snapshot-1",
        broker="BINANCE",
        market="FUTURES",
        reads=(
            BinanceMarketReadResult(
                source_type="ticker_24h",
                symbol=None,
                interval=None,
                status="OK",
                rows=[
                    _ticker("BTCUSDT"),
                ],
                error_code=None,
                latency_ms=10,
            ),
            BinanceMarketReadResult(
                source_type="klines",
                symbol="BTCUSDT",
                interval="1h",
                status="OK",
                rows=_klines(),
                error_code=None,
                latency_ms=10,
            ),
            BinanceMarketReadResult(
                source_type="klines",
                symbol="BTCUSDT",
                interval="15m",
                status="OK",
                rows=_klines(),
                error_code=None,
                latency_ms=10,
            ),
        ),
    )

    report = run_binance_auto_pick_observation_from_snapshot(
        snapshot,
        top_n=5,
    )

    with TestingSessionLocal() as db:
        persist_autopick_observation_snapshot(
            db=db,
            snapshot=snapshot,
            report=report,
        )
        db.commit()

    with TestingSessionLocal() as db:
        rows = db.execute(
            select(AutopickObservationSnapshot)
        ).scalars().all()

    assert len(rows) == 1

    row = rows[0]

    assert row.snapshot_id == "snapshot-1"
    assert row.snapshot_hash == snapshot.snapshot_hash
    assert row.broker == "BINANCE"
    assert row.market == "FUTURES"
    assert row.decision_status == report.decision_status
    assert row.selected_symbol == report.selected_symbol
    assert row.partial_failure_count == snapshot.partial_failure_count

    rejected = json.loads(row.rejected_candidates_json)

    assert rejected == report.rejected_candidates


def test_duplicate_snapshot_id_fails_closed():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)

    DataBase.metadata.create_all(bind=engine)

    snapshot = BinanceMarketObservationSnapshot(
        snapshot_id="duplicate-snapshot",
        broker="BINANCE",
        market="FUTURES",
        reads=(),
    )

    report = run_binance_auto_pick_observation_from_snapshot(
        snapshot,
        top_n=5,
    )

    with TestingSessionLocal() as db:
        persist_autopick_observation_snapshot(
            db=db,
            snapshot=snapshot,
            report=report,
        )
        db.commit()

    with TestingSessionLocal() as db:
        persist_autopick_observation_snapshot(
            db=db,
            snapshot=snapshot,
            report=report,
        )

        try:
            db.commit()
        except Exception:
            db.rollback()
            return

    raise AssertionError("duplicate snapshot_id must fail closed")
