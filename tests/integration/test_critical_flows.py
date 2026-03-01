import pyotp


def _login(client, username: str, password: str, otp: str | None = None):
    data = {"username": username, "password": password}
    if otp:
        data["otp"] = otp
    return client.post("/auth/login", data=data)


def _token(client, username: str, password: str, otp: str | None = None) -> str:
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
