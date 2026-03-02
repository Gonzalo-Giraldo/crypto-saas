import pyotp
from typing import Optional
from datetime import datetime, timedelta, timezone
import hashlib
import json


def _login(client, username: str, password: str, otp: Optional[str] = None):
    data = {"username": username, "password": password}
    if otp:
        data["otp"] = otp
    return client.post("/auth/login", data=data)


def _token(client, username: str, password: str, otp: Optional[str] = None) -> str:
    resp = _login(client, username, password, otp)
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_auth_and_2fa_flow(client):
    token = _token(client, "trader@test.com", "TraderPass123!")

    setup = client.post("/auth/2fa/setup", headers=_auth(token))
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]

    otp = pyotp.TOTP(secret).now()
    verify = client.post(
        "/auth/2fa/verify-enable",
        headers=_auth(token),
        json={"otp": otp},
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["message"] == "2FA enabled"

    no_otp = _login(client, "trader@test.com", "TraderPass123!")
    assert no_otp.status_code == 401
    assert no_otp.json()["detail"] == "OTP required"

    with_otp = _login(
        client,
        "trader@test.com",
        "TraderPass123!",
        otp=pyotp.TOTP(secret).now(),
    )
    assert with_otp.status_code == 200
    assert "access_token" in with_otp.json()


def test_exchange_secrets_pretrade_and_test_orders(client, monkeypatch):
    token = _token(client, "trader@test.com", "TraderPass123!")

    save_binance = client.post(
        "/users/exchange-secrets",
        headers=_auth(token),
        json={"exchange": "BINANCE", "api_key": "k1", "api_secret": "s1"},
    )
    assert save_binance.status_code == 201, save_binance.text

    save_ibkr = client.post(
        "/users/exchange-secrets",
        headers=_auth(token),
        json={"exchange": "IBKR", "api_key": "k2", "api_secret": "s2"},
    )
    assert save_ibkr.status_code == 201, save_ibkr.text

    listed = client.get("/users/exchange-secrets", headers=_auth(token))
    assert listed.status_code == 200
    exchanges = {x["exchange"] for x in listed.json()}
    assert exchanges == {"BINANCE", "IBKR"}

    pretrade = client.post(
        "/ops/execution/pretrade/binance/check",
        headers=_auth(token),
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 0.01,
            "rr_estimate": 1.6,
            "trend_tf": "4H",
            "signal_tf": "1H",
            "timing_tf": "15M",
            "spread_bps": 7,
            "slippage_bps": 10,
            "volume_24h_usdt": 90000000,
        },
    )
    assert pretrade.status_code == 200, pretrade.text
    assert pretrade.json()["passed"] is True

    import apps.api.app.api.ops as ops_api

    monkeypatch.setattr(
        ops_api,
        "execute_binance_test_order_for_user",
        lambda user_id, symbol, side, qty: {
            "exchange": "BINANCE",
            "mode": "testnet_order_test",
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "sent": True,
        },
    )
    monkeypatch.setattr(
        ops_api,
        "execute_ibkr_test_order_for_user",
        lambda user_id, symbol, side, qty: {
            "exchange": "IBKR",
            "mode": "paper_simulated_test",
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "sent": True,
            "order_ref": "TEST-1",
        },
    )

    binance_order = client.post(
        "/ops/execution/binance/test-order",
        headers=_auth(token),
        json={"symbol": "BTCUSDT", "side": "BUY", "qty": 0.01},
    )
    assert binance_order.status_code == 200, binance_order.text
    assert binance_order.json()["sent"] is True

    ibkr_order = client.post(
        "/ops/execution/ibkr/test-order",
        headers=_auth(token),
        json={"symbol": "AAPL", "side": "BUY", "qty": 1},
    )
    assert ibkr_order.status_code == 200, ibkr_order.text
    assert ibkr_order.json()["sent"] is True

    deleted = client.delete("/users/exchange-secrets/BINANCE", headers=_auth(token))
    assert deleted.status_code == 200, deleted.text


def test_pretrade_scan_ranking_and_timing(client):
    token = _token(client, "trader@test.com", "TraderPass123!")
    saved = client.post(
        "/users/exchange-secrets",
        headers=_auth(token),
        json={"exchange": "BINANCE", "api_key": "k1", "api_secret": "s1"},
    )
    assert saved.status_code == 201, saved.text

    scan = client.post(
        "/ops/execution/pretrade/binance/scan",
        headers=_auth(token),
        json={
            "top_n": 5,
            "include_blocked": True,
            "candidates": [
                {
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "qty": 0.01,
                    "rr_estimate": 1.7,
                    "trend_tf": "4H",
                    "signal_tf": "1H",
                    "timing_tf": "15M",
                    "spread_bps": 6,
                    "slippage_bps": 9,
                    "volume_24h_usdt": 95000000,
                    "market_trend_score": 0.6,
                    "atr_pct": 3.0,
                    "momentum_score": 0.4,
                },
                {
                    "symbol": "ETHUSDT",
                    "side": "BUY",
                    "qty": 0.01,
                    "rr_estimate": 2.2,
                    "trend_tf": "4H",
                    "signal_tf": "1H",
                    "timing_tf": "15M",
                    "spread_bps": 6,
                    "slippage_bps": 9,
                    "volume_24h_usdt": 95000000,
                    "market_trend_score": 0.0,
                    "atr_pct": 8.0,
                    "momentum_score": 0.0,
                },
            ],
        },
    )
    assert scan.status_code == 200, scan.text
    data = scan.json()
    assert data["exchange"] == "BINANCE"
    assert data["scanned_assets"] == 2
    assert data["returned_assets"] == 2
    assert data["duration_ms_total"] >= 0
    assert data["duration_ms_avg"] >= 0
    assert len(data["assets"]) == 2
    assert data["assets"][0]["score"] >= data["assets"][1]["score"]
    assert data["assets"][0]["duration_ms"] >= 0
    assert data["assets"][0]["total_checks"] >= data["assets"][0]["passed_checks"]

    scan_only_passed = client.post(
        "/ops/execution/pretrade/binance/scan",
        headers=_auth(token),
        json={
            "top_n": 5,
            "include_blocked": False,
            "candidates": [
                {
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "qty": 0.01,
                    "rr_estimate": 1.7,
                    "trend_tf": "4H",
                    "signal_tf": "1H",
                    "timing_tf": "15M",
                    "spread_bps": 6,
                    "slippage_bps": 9,
                    "volume_24h_usdt": 95000000,
                    "market_trend_score": 0.6,
                    "atr_pct": 3.0,
                    "momentum_score": 0.4,
                },
                {
                    "symbol": "ETHUSDT",
                    "side": "BUY",
                    "qty": 0.01,
                    "rr_estimate": 2.2,
                    "trend_tf": "4H",
                    "signal_tf": "1H",
                    "timing_tf": "15M",
                    "spread_bps": 6,
                    "slippage_bps": 9,
                    "volume_24h_usdt": 95000000,
                    "market_trend_score": 0.0,
                    "atr_pct": 8.0,
                    "momentum_score": 0.0,
                },
            ],
        },
    )
    assert scan_only_passed.status_code == 200, scan_only_passed.text
    only_passed = scan_only_passed.json()
    assert only_passed["returned_assets"] >= 1
    assert all(asset["passed"] for asset in only_passed["assets"])


def test_security_posture_admin_only(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    blocked = client.get("/ops/security/posture", headers=_auth(trader_token))
    assert blocked.status_code == 403

    ok = client.get(
        "/ops/security/posture?real_only=true&max_secret_age_days=30",
        headers=_auth(admin_token),
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()
    assert "summary" in data
    assert "users" in data
    assert data["summary"]["total_users"] >= 1


def test_refresh_token_rotation_and_logout_revocation(client):
    login = _login(client, "trader@test.com", "TraderPass123!")
    assert login.status_code == 200, login.text
    login_data = login.json()
    access = login_data["access_token"]
    refresh = login_data["refresh_token"]

    refreshed = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert refreshed.status_code == 200, refreshed.text
    refreshed_data = refreshed.json()
    new_access = refreshed_data["access_token"]
    new_refresh = refreshed_data["refresh_token"]
    assert new_access != access
    assert new_refresh != refresh

    # Old refresh token must be revoked after rotation.
    old_refresh_reuse = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert old_refresh_reuse.status_code == 401

    # Logout revokes active access + refresh.
    logout = client.post(
        "/auth/logout",
        headers=_auth(new_access),
        json={"refresh_token": new_refresh},
    )
    assert logout.status_code == 200, logout.text

    me_after_logout = client.get("/users/me", headers=_auth(new_access))
    assert me_after_logout.status_code == 401


def test_revoke_all_invalidates_previous_sessions(client):
    login1 = _login(client, "admin@test.com", "AdminPass123!")
    assert login1.status_code == 200, login1.text
    old_access = login1.json()["access_token"]
    old_refresh = login1.json()["refresh_token"]

    revoke_all = client.post("/auth/revoke-all", headers=_auth(old_access))
    assert revoke_all.status_code == 200, revoke_all.text

    me_old = client.get("/users/me", headers=_auth(old_access))
    assert me_old.status_code == 401

    refresh_old = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh_old.status_code == 401

    login2 = _login(client, "admin@test.com", "AdminPass123!")
    assert login2.status_code == 200, login2.text
    me_new = client.get("/users/me", headers=_auth(login2.json()["access_token"]))
    assert me_new.status_code == 200


def test_password_max_age_enforcement(client, monkeypatch):
    import apps.api.app.routes.auth as auth_api
    from apps.api.app.db.session import SessionLocal
    from apps.api.app.models.user import User

    monkeypatch.setattr(auth_api.settings, "ENFORCE_PASSWORD_MAX_AGE", True)
    monkeypatch.setattr(auth_api.settings, "PASSWORD_MAX_AGE_DAYS", 30)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "trader@test.com").first()
        assert user is not None
        user.password_changed_at = datetime.now(timezone.utc) - timedelta(days=45)
        db.commit()
    finally:
        db.close()

    expired_login = _login(client, "trader@test.com", "TraderPass123!")
    assert expired_login.status_code == 401
    assert "Password expired" in expired_login.json()["detail"]


def test_admin_kill_switch_blocks_trading_paths(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    save_binance = client.post(
        "/users/exchange-secrets",
        headers=_auth(trader_token),
        json={"exchange": "BINANCE", "api_key": "k1", "api_secret": "s1"},
    )
    assert save_binance.status_code == 201, save_binance.text

    disable = client.post(
        "/ops/admin/trading-control",
        headers=_auth(admin_token),
        json={"trading_enabled": False, "reason": "maintenance"},
    )
    assert disable.status_code == 200, disable.text
    assert disable.json()["trading_enabled"] is False

    blocked_pretrade = client.post(
        "/ops/execution/pretrade/binance/check",
        headers=_auth(trader_token),
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 0.01,
            "rr_estimate": 1.6,
            "trend_tf": "4H",
            "signal_tf": "1H",
            "timing_tf": "15M",
            "spread_bps": 7,
            "slippage_bps": 10,
            "volume_24h_usdt": 90000000,
        },
    )
    assert blocked_pretrade.status_code == 409
    assert "globally disabled" in blocked_pretrade.json()["detail"]

    reenable = client.post(
        "/ops/admin/trading-control",
        headers=_auth(admin_token),
        json={"trading_enabled": True, "reason": "resume"},
    )
    assert reenable.status_code == 200, reenable.text
    assert reenable.json()["trading_enabled"] is True


def test_idempotency_replay_and_payload_conflict(client):
    token = _token(client, "trader@test.com", "TraderPass123!")

    save_binance = client.post(
        "/users/exchange-secrets",
        headers=_auth(token),
        json={"exchange": "BINANCE", "api_key": "k1", "api_secret": "s1"},
    )
    assert save_binance.status_code == 201, save_binance.text

    headers = {
        **_auth(token),
        "X-Idempotency-Key": "same-pretrade-key-1",
    }
    payload = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "qty": 0.01,
        "rr_estimate": 1.6,
        "trend_tf": "4H",
        "signal_tf": "1H",
        "timing_tf": "15M",
        "spread_bps": 7,
        "slippage_bps": 10,
        "volume_24h_usdt": 90000000,
    }
    first = client.post(
        "/ops/execution/pretrade/binance/check",
        headers=headers,
        json=payload,
    )
    second = client.post(
        "/ops/execution/pretrade/binance/check",
        headers=headers,
        json=payload,
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == second.json()

    conflict = client.post(
        "/ops/execution/pretrade/binance/check",
        headers=headers,
        json={**payload, "qty": 0.02},
    )
    assert conflict.status_code == 409
    assert "different payload" in conflict.json()["detail"]


def test_exposure_limit_per_symbol_blocks_pretrade(client, monkeypatch):
    import apps.api.app.services.trading_controls as controls

    monkeypatch.setattr(controls.settings, "MAX_OPEN_QTY_PER_SYMBOL", 0.005)

    token = _token(client, "trader@test.com", "TraderPass123!")
    save_binance = client.post(
        "/users/exchange-secrets",
        headers=_auth(token),
        json={"exchange": "BINANCE", "api_key": "k1", "api_secret": "s1"},
    )
    assert save_binance.status_code == 201, save_binance.text

    blocked = client.post(
        "/ops/execution/pretrade/binance/check",
        headers=_auth(token),
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 0.01,
            "rr_estimate": 1.6,
            "trend_tf": "4H",
            "signal_tf": "1H",
            "timing_tf": "15M",
            "spread_bps": 7,
            "slippage_bps": 10,
            "volume_24h_usdt": 90000000,
        },
    )
    assert blocked.status_code == 409
    assert "symbol exposure exceeded" in blocked.json()["detail"]


def test_idempotency_admin_stats_and_cleanup_admin_only(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    save_binance = client.post(
        "/users/exchange-secrets",
        headers=_auth(trader_token),
        json={"exchange": "BINANCE", "api_key": "k1", "api_secret": "s1"},
    )
    assert save_binance.status_code == 201, save_binance.text

    key_headers = {**_auth(trader_token), "X-Idempotency-Key": "stats-key-1"}
    pretrade = client.post(
        "/ops/execution/pretrade/binance/check",
        headers=key_headers,
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 0.01,
            "rr_estimate": 1.6,
            "trend_tf": "4H",
            "signal_tf": "1H",
            "timing_tf": "15M",
            "spread_bps": 7,
            "slippage_bps": 10,
            "volume_24h_usdt": 90000000,
        },
    )
    assert pretrade.status_code == 200, pretrade.text

    blocked_stats = client.get("/ops/admin/idempotency/stats", headers=_auth(trader_token))
    assert blocked_stats.status_code == 403

    stats = client.get("/ops/admin/idempotency/stats", headers=_auth(admin_token))
    assert stats.status_code == 200, stats.text
    assert stats.json()["records_total"] >= 1

    blocked_cleanup = client.post("/ops/admin/idempotency/cleanup", headers=_auth(trader_token))
    assert blocked_cleanup.status_code == 403

    cleaned = client.post("/ops/admin/idempotency/cleanup", headers=_auth(admin_token))
    assert cleaned.status_code == 200, cleaned.text
    assert "deleted" in cleaned.json()


def test_backoffice_rbac_viewer_readonly(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    viewer_token = _token(client, "viewer@test.com", "ViewerPass123!")

    summary = client.get("/ops/backoffice/summary", headers=_auth(viewer_token))
    assert summary.status_code == 200, summary.text
    assert summary.json()["tenant_id"] == "default"
    assert summary.json()["viewers"] >= 1

    users = client.get("/ops/backoffice/users", headers=_auth(viewer_token))
    assert users.status_code == 200, users.text
    assert any(row["email"] == "viewer@test.com" for row in users.json())

    blocked_admin_control = client.get("/ops/admin/trading-control", headers=_auth(viewer_token))
    assert blocked_admin_control.status_code == 403

    # Admin still has access to sensitive admin endpoint.
    allowed_admin_control = client.get("/ops/admin/trading-control", headers=_auth(admin_token))
    assert allowed_admin_control.status_code == 200


def test_audit_export_hash_and_signature_admin_only(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    # Create some audit activity.
    _ = client.get("/ops/audit/me?limit=5", headers=_auth(trader_token))

    blocked = client.get("/ops/admin/audit/export", headers=_auth(trader_token))
    assert blocked.status_code == 403

    exported = client.get("/ops/admin/audit/export?limit=50", headers=_auth(admin_token))
    assert exported.status_code == 200, exported.text
    data = exported.json()
    assert "meta" in data and "records" in data
    assert data["meta"]["tenant_id"] == "default"
    assert data["meta"]["records_count"] == len(data["records"])
    assert len(data["payload_sha256"]) == 64
    assert len(data["signature_hmac_sha256"]) == 64

    canonical_payload = {
        "meta": data["meta"],
        "records": data["records"],
    }
    canonical_json = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    expected_sha = hashlib.sha256(canonical_json).hexdigest()
    assert expected_sha == data["payload_sha256"]


def test_ops_console_page_served(client):
    res = client.get("/ops/console")
    assert res.status_code == 200
    assert "Ops Console v1" in res.text


def test_admin_can_reset_user_2fa(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")

    users = client.get("/users", headers=_auth(admin_token))
    assert users.status_code == 200, users.text
    trader = next((u for u in users.json() if u["email"] == "trader@test.com"), None)
    assert trader is not None

    reset = client.post(
        f"/users/{trader['id']}/2fa/reset",
        headers=_auth(admin_token),
    )
    assert reset.status_code == 200, reset.text
    payload = reset.json()
    assert payload["enabled"] is True
    assert payload["email"] == "trader@test.com"
    assert payload["secret"]
    assert "otpauth://" in payload["otpauth_uri"]

    no_otp = _login(client, "trader@test.com", "TraderPass123!")
    assert no_otp.status_code == 401
    assert no_otp.json()["detail"] == "OTP required"

    with_otp = _login(
        client,
        "trader@test.com",
        "TraderPass123!",
        otp=pyotp.TOTP(payload["secret"]).now(),
    )
    assert with_otp.status_code == 200, with_otp.text


def test_admin_daily_snapshot_admin_only(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    blocked = client.get("/ops/admin/snapshot/daily", headers=_auth(trader_token))
    assert blocked.status_code == 403

    ok = client.get(
        "/ops/admin/snapshot/daily?real_only=true&max_secret_age_days=30&recent_hours=24",
        headers=_auth(admin_token),
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()
    assert "dashboard" in data
    assert "backoffice_summary" in data
    assert "backoffice_users" in data
    assert "security_posture" in data
    assert "risk_daily_compare" in data


def test_admin_readiness_report_admin_only(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    blocked = client.get("/users/readiness/report", headers=_auth(trader_token))
    assert blocked.status_code == 403

    ok = client.get(
        "/users/readiness/report?real_only=true&include_service_users=false",
        headers=_auth(admin_token),
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()
    assert "summary" in data
    assert "users" in data
    assert "ready_users" in data["summary"]
    assert "missing_users" in data["summary"]


def test_admin_daily_gate_admin_only(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    blocked = client.get("/ops/admin/readiness/daily-gate", headers=_auth(trader_token))
    assert blocked.status_code == 403

    ok = client.get(
        "/ops/admin/readiness/daily-gate?real_only=true&include_service_users=false&max_secret_age_days=30",
        headers=_auth(admin_token),
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()
    assert "passed" in data
    assert "checks" in data
    assert "security_summary" in data
    assert "readiness_summary" in data


def test_admin_can_update_dynamic_risk_profile_and_affects_limits(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    blocked = client.put(
        "/ops/admin/risk/profiles/model2_conservador_productivo",
        headers=_auth(trader_token),
        json={
            "max_risk_per_trade_pct": 0.5,
            "max_daily_loss_pct": 1.5,
            "max_trades_per_day": 2,
            "max_open_positions": 2,
            "cooldown_between_trades_minutes": 30,
            "max_leverage": 1.0,
            "stop_loss_required": True,
            "min_rr": 1.5,
        },
    )
    assert blocked.status_code == 403

    updated = client.put(
        "/ops/admin/risk/profiles/model2_conservador_productivo",
        headers=_auth(admin_token),
        json={
            "max_risk_per_trade_pct": 0.4,
            "max_daily_loss_pct": 1.2,
            "max_trades_per_day": 2,
            "max_open_positions": 2,
            "cooldown_between_trades_minutes": 25,
            "max_leverage": 1.0,
            "stop_loss_required": True,
            "min_rr": 1.6,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["max_trades_per_day"] == 2
    assert abs(updated.json()["max_daily_loss_pct"] - 1.2) < 1e-9

    profiles = client.get("/ops/admin/risk/profiles", headers=_auth(admin_token))
    assert profiles.status_code == 200, profiles.text
    assert any(p["profile_name"] == "model2_conservador_productivo" for p in profiles.json())

    compare = client.get("/ops/risk/daily-compare?real_only=true", headers=_auth(admin_token))
    assert compare.status_code == 200, compare.text
    users = compare.json()["users"]
    admin_row = next((u for u in users if u["email"] == "admin@test.com"), None)
    assert admin_row is not None
    assert admin_row["limits"]["max_trades_per_day"] == 2
    assert abs(admin_row["limits"]["max_daily_loss_pct"] - 1.2) < 1e-9


def test_user_risk_settings_admin_only(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    users = client.get("/users", headers=_auth(admin_token))
    assert users.status_code == 200, users.text
    trader = next((u for u in users.json() if u["email"] == "trader@test.com"), None)
    assert trader is not None

    blocked = client.put(
        f"/users/{trader['id']}/risk-settings",
        headers=_auth(trader_token),
        json={"capital_base_usd": 2500.0},
    )
    assert blocked.status_code == 403

    updated = client.put(
        f"/users/{trader['id']}/risk-settings",
        headers=_auth(admin_token),
        json={"capital_base_usd": 2500.0},
    )
    assert updated.status_code == 200, updated.text
    assert abs(updated.json()["capital_base_usd"] - 2500.0) < 1e-9

    fetched = client.get(
        f"/users/{trader['id']}/risk-settings",
        headers=_auth(admin_token),
    )
    assert fetched.status_code == 200, fetched.text
    assert abs(fetched.json()["capital_base_usd"] - 2500.0) < 1e-9


def test_open_position_blocks_when_risk_per_trade_exceeded(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    users = client.get("/users", headers=_auth(admin_token))
    assert users.status_code == 200, users.text
    trader = next((u for u in users.json() if u["email"] == "trader@test.com"), None)
    assert trader is not None

    # Keep the test deterministic using a known capital base for the trader.
    set_capital = client.put(
        f"/users/{trader['id']}/risk-settings",
        headers=_auth(admin_token),
        json={"capital_base_usd": 1000.0},
    )
    assert set_capital.status_code == 200, set_capital.text

    risk_today = client.get("/positions/risk/today", headers=_auth(trader_token))
    assert risk_today.status_code == 200, risk_today.text
    max_risk_amount_usd = float(risk_today.json()["max_risk_amount_usd"])
    assert max_risk_amount_usd > 0

    create_1 = client.post(
        "/signals",
        headers=_auth(trader_token),
        json={
            "symbol": "BTCUSDT",
            "module": "SWING_V1",
            "base_risk_percent": 0.5,
            "entry_price": 100.0,
            "stop_loss": 90.0,
            "take_profit": 120.0,
        },
    )
    assert create_1.status_code == 200, create_1.text
    signal_1 = create_1.json()
    claim_1 = client.post("/signals/claim", headers=_auth(trader_token))
    assert claim_1.status_code == 200, claim_1.text

    # risk_per_unit = 10.0; force requested risk > max_risk_amount_usd
    blocked_qty = (max_risk_amount_usd / 10.0) + 1.0
    blocked_open = client.post(
        "/positions/open_from_signal",
        headers=_auth(trader_token),
        params={"signal_id": signal_1["id"], "qty": blocked_qty},
    )
    assert blocked_open.status_code == 409, blocked_open.text
    assert "risk per trade exceeded" in blocked_open.json()["detail"]

    create_2 = client.post(
        "/signals",
        headers=_auth(trader_token),
        json={
            "symbol": "BTCUSDT",
            "module": "SWING_V1",
            "base_risk_percent": 0.5,
            "entry_price": 100.0,
            "stop_loss": 90.0,
            "take_profit": 120.0,
        },
    )
    assert create_2.status_code == 200, create_2.text
    signal_2 = create_2.json()
    claim_2 = client.post("/signals/claim", headers=_auth(trader_token))
    assert claim_2.status_code == 200, claim_2.text

    allowed_qty = max((max_risk_amount_usd / 10.0) * 0.8, 0.01)
    allowed_open = client.post(
        "/positions/open_from_signal",
        headers=_auth(trader_token),
        params={"signal_id": signal_2["id"], "qty": allowed_qty},
    )
    assert allowed_open.status_code == 200, allowed_open.text


def test_strategy_runtime_policy_admin_only(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    blocked = client.get("/ops/admin/strategy-runtime-policies", headers=_auth(trader_token))
    assert blocked.status_code == 403

    listed = client.get("/ops/admin/strategy-runtime-policies", headers=_auth(admin_token))
    assert listed.status_code == 200, listed.text
    assert any(p["strategy_id"] == "SWING_V1" and p["exchange"] == "BINANCE" for p in listed.json())

    updated = client.put(
        "/ops/admin/strategy-runtime-policies/SWING_V1/BINANCE",
        headers=_auth(admin_token),
        json={
            "allow_bull": True,
            "allow_bear": True,
            "allow_range": True,
            "rr_min_bull": 1.5,
            "rr_min_bear": 1.6,
            "rr_min_range": 2.2,
            "min_volume_24h_usdt_bull": 50000000.0,
            "min_volume_24h_usdt_bear": 70000000.0,
            "min_volume_24h_usdt_range": 90000000.0,
            "max_spread_bps_bull": 10.0,
            "max_spread_bps_bear": 8.0,
            "max_spread_bps_range": 7.0,
            "max_slippage_bps_bull": 15.0,
            "max_slippage_bps_bear": 12.0,
            "max_slippage_bps_range": 10.0,
            "max_hold_minutes_bull": 720.0,
            "max_hold_minutes_bear": 480.0,
            "max_hold_minutes_range": 180.0,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["allow_range"] is True
    assert abs(updated.json()["rr_min_range"] - 2.2) < 1e-9


def test_pretrade_auto_regime_and_policy_gating(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    save_binance = client.post(
        "/users/exchange-secrets",
        headers=_auth(trader_token),
        json={"exchange": "BINANCE", "api_key": "k1", "api_secret": "s1"},
    )
    assert save_binance.status_code == 201, save_binance.text

    # Range enabled but with stricter RR in range regime.
    policy = client.put(
        "/ops/admin/strategy-runtime-policies/SWING_V1/BINANCE",
        headers=_auth(admin_token),
        json={
            "allow_bull": True,
            "allow_bear": True,
            "allow_range": True,
            "rr_min_bull": 1.5,
            "rr_min_bear": 1.6,
            "rr_min_range": 2.2,
            "min_volume_24h_usdt_bull": 50000000.0,
            "min_volume_24h_usdt_bear": 70000000.0,
            "min_volume_24h_usdt_range": 90000000.0,
            "max_spread_bps_bull": 10.0,
            "max_spread_bps_bear": 8.0,
            "max_spread_bps_range": 7.0,
            "max_slippage_bps_bull": 15.0,
            "max_slippage_bps_bear": 12.0,
            "max_slippage_bps_range": 10.0,
            "max_hold_minutes_bull": 720.0,
            "max_hold_minutes_bear": 480.0,
            "max_hold_minutes_range": 180.0,
        },
    )
    assert policy.status_code == 200, policy.text

    blocked = client.post(
        "/ops/execution/pretrade/binance/check",
        headers=_auth(trader_token),
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 0.01,
            "rr_estimate": 2.0,
            "trend_tf": "4H",
            "signal_tf": "1H",
            "timing_tf": "15M",
            "spread_bps": 6,
            "slippage_bps": 9,
            "volume_24h_usdt": 95000000,
            "market_trend_score": 0.0,
            "atr_pct": 8.0,
            "momentum_score": 0.0,
        },
    )
    assert blocked.status_code == 200, blocked.text
    body_blocked = blocked.json()
    assert body_blocked["market_regime"] == "range"
    assert body_blocked["passed"] is False
    rr_check = next((c for c in body_blocked["checks"] if c["name"] == "strategy_rr_min"), None)
    assert rr_check is not None and rr_check["passed"] is False

    allowed = client.post(
        "/ops/execution/pretrade/binance/check",
        headers=_auth(trader_token),
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 0.01,
            "rr_estimate": 2.3,
            "trend_tf": "4H",
            "signal_tf": "1H",
            "timing_tf": "15M",
            "spread_bps": 6,
            "slippage_bps": 9,
            "volume_24h_usdt": 95000000,
            "market_trend_score": 0.0,
            "atr_pct": 8.0,
            "momentum_score": 0.0,
        },
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["market_regime"] == "range"
    assert allowed.json()["passed"] is True


def test_exit_uses_regime_specific_time_limit(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    policy = client.put(
        "/ops/admin/strategy-runtime-policies/SWING_V1/IBKR",
        headers=_auth(admin_token),
        json={
            "allow_bull": True,
            "allow_bear": True,
            "allow_range": True,
            "rr_min_bull": 1.4,
            "rr_min_bear": 1.5,
            "rr_min_range": 1.8,
            "min_volume_24h_usdt_bull": 0.0,
            "min_volume_24h_usdt_bear": 0.0,
            "min_volume_24h_usdt_range": 0.0,
            "max_spread_bps_bull": 12.0,
            "max_spread_bps_bear": 10.0,
            "max_spread_bps_range": 8.0,
            "max_slippage_bps_bull": 15.0,
            "max_slippage_bps_bear": 12.0,
            "max_slippage_bps_range": 10.0,
            "max_hold_minutes_bull": 720.0,
            "max_hold_minutes_bear": 480.0,
            "max_hold_minutes_range": 100.0,
        },
    )
    assert policy.status_code == 200, policy.text

    check = client.post(
        "/ops/execution/exit/ibkr/check",
        headers=_auth(trader_token),
        json={
            "symbol": "AAPL",
            "side": "BUY",
            "entry_price": 180,
            "current_price": 181,
            "stop_loss": 178,
            "take_profit": 185,
            "opened_minutes": 120,
            "trend_break": False,
            "signal_reverse": False,
            "macro_event_block": False,
            "earnings_within_24h": False,
            "market_trend_score": 0.0,
            "atr_pct": 9.0,
            "momentum_score": 0.0,
        },
    )
    assert check.status_code == 200, check.text
    body = check.json()
    assert body["market_regime"] == "range"
    assert body["should_exit"] is True
    assert "time_limit_reached" in body["reasons"]
