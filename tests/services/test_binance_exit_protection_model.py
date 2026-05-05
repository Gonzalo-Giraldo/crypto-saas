from apps.api.app.models.binance_exit_protection import BinanceExitProtection


def test_binance_exit_protection_table_name():
    assert BinanceExitProtection.__tablename__ == "binance_exit_protections"


def test_binance_exit_protection_required_columns_exist():
    columns = BinanceExitProtection.__table__.columns

    expected = {
        "id",
        "exit_key",
        "intent_id",
        "entry_execution_ref",
        "symbol",
        "market",
        "direction",
        "filled_qty",
        "avg_entry_price",
        "sl_client_algo_id",
        "tp_client_algo_id",
        "sl_algo_id",
        "tp_algo_id",
        "sl_status",
        "tp_status",
        "protection_status",
        "attempt_count",
        "last_error",
        "created_at",
        "updated_at",
    }

    assert expected.issubset(set(columns.keys()))


def test_binance_exit_protection_does_not_reuse_execution_ref_as_exit_ref():
    columns = BinanceExitProtection.__table__.columns

    assert "execution_ref" not in columns
    assert "entry_execution_ref" in columns
    assert "sl_client_algo_id" in columns
    assert "tp_client_algo_id" in columns


def test_binance_exit_protection_has_exit_key_unique_constraint():
    constraints = BinanceExitProtection.__table__.constraints
    names = {constraint.name for constraint in constraints}

    assert "uq_binance_exit_protections_exit_key" in names


def test_binance_exit_protection_has_money_safety_constraints():
    names = {constraint.name for constraint in BinanceExitProtection.__table__.constraints}

    assert "ck_binance_exit_protections_market_futures" in names
    assert "ck_binance_exit_protections_direction" in names
    assert "ck_binance_exit_protections_filled_qty_positive" in names
    assert "ck_binance_exit_protections_avg_entry_price_positive" in names
    assert "ck_binance_exit_protections_protection_status" in names
