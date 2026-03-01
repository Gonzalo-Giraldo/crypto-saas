import pyotp
from typing import Optional
from datetime import datetime, timedelta, timezone


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
