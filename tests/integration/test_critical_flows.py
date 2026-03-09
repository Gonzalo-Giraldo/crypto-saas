import pyotp
from typing import Optional
from datetime import datetime, timedelta, timezone
import hashlib
import json
import uuid


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


def test_binance_gateway_account_status_uses_spot_base(client, monkeypatch):
    _ = client
    import apps.binance_gateway.main as gw
    from fastapi.testclient import TestClient as GatewayClient

    monkeypatch.setattr(gw, "INTERNAL_TOKEN", "gw-token")
    monkeypatch.setattr(gw, "BINANCE_SPOT_BASE", "https://spot.example.test")
    monkeypatch.setattr(gw, "RATE_LIMIT_PER_MIN", 9999)

    observed = {"url": None}

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"canTrade": True, "balances": []}

    def _fake_request(method: str, url: str, **kwargs):
        observed["url"] = url
        return _Resp()

    monkeypatch.setattr(gw.requests, "request", _fake_request)

    with GatewayClient(gw.app) as gc:
        resp = gc.post(
            "/binance/account-status",
            headers={"X-Internal-Token": "gw-token"},
            json={"api_key": "k", "api_secret": "s"},
        )
    assert resp.status_code == 200, resp.text
    assert observed["url"] is not None
    assert str(observed["url"]).startswith("https://spot.example.test/api/v3/account?")


def test_binance_gateway_returns_502_on_upstream_unreachable(client, monkeypatch):
    _ = client
    import apps.binance_gateway.main as gw
    from fastapi.testclient import TestClient as GatewayClient

    monkeypatch.setattr(gw, "INTERNAL_TOKEN", "gw-token")
    monkeypatch.setattr(gw, "RATE_LIMIT_PER_MIN", 9999)

    def _fake_request(method: str, url: str, **kwargs):
        raise gw.requests.RequestException("network down")

    monkeypatch.setattr(gw.requests, "request", _fake_request)

    with GatewayClient(gw.app) as gc:
        resp = gc.post(
            "/binance/account-status",
            headers={"X-Internal-Token": "gw-token"},
            json={"api_key": "k", "api_secret": "s"},
        )
    assert resp.status_code == 502
    assert resp.json()["detail"] == "binance_upstream_unreachable"


def test_binance_runtime_gateway_error_is_sanitized(client, monkeypatch):
    _ = client
    import apps.worker.app.engine.execution_runtime as runtime

    class _Resp:
        status_code = 502
        text = '{"code":-1021,"msg":"timestamp outside recvWindow api_secret=supersecret"}'

    monkeypatch.setattr(runtime.settings, "BINANCE_GATEWAY_BASE_URL", "https://gw.example.test")
    monkeypatch.setattr(runtime.settings, "BINANCE_GATEWAY_TOKEN", "tok")
    monkeypatch.setattr(runtime.requests, "post", lambda *args, **kwargs: _Resp())

    try:
        runtime._get_binance_account_status_via_gateway(api_key="k", api_secret="s")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        msg = str(exc)
        assert "gateway_upstream_error status=502" in msg
        assert "code=-1021" in msg
        assert "supersecret" not in msg


def test_binance_client_gateway_error_is_sanitized(client, monkeypatch):
    _ = client
    import apps.worker.app.engine.binance_client as bclient

    class _Resp:
        status_code = 503
        text = '{"code":-1003,"msg":"too many requests secret=abc"}'

        @staticmethod
        def json():
            return {"code": -1003}

    monkeypatch.setattr(bclient.settings, "BINANCE_GATEWAY_ENABLED", True)
    monkeypatch.setattr(bclient.settings, "BINANCE_GATEWAY_BASE_URL", "https://gw.example.test")
    monkeypatch.setattr(bclient.requests, "post", lambda *args, **kwargs: _Resp())

    try:
        bclient._post_gateway("/binance/ticker-price", {"symbol": "BTCUSDT"}, timeout=3)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        msg = str(exc)
        assert "gateway_upstream_error status=503" in msg
        assert "code=-1003" in msg
        assert "secret=abc" not in msg


def test_ibkr_client_bridge_error_is_sanitized(client, monkeypatch):
    _ = client
    import apps.worker.app.engine.ibkr_client as iclient

    class _Resp:
        status_code = 502
        text = '{"code":"BRIDGE_DOWN","msg":"secret=xyz"}'

        @staticmethod
        def json():
            return {}

    monkeypatch.setattr(iclient.settings, "IBKR_BRIDGE_BASE_URL", "https://ibkr-bridge.example.test")
    monkeypatch.setattr(iclient.requests, "post", lambda *args, **kwargs: _Resp())

    try:
        iclient.send_ibkr_test_order(
            api_key="12345678",
            api_secret="abcdefgh",
            symbol="AAPL",
            side="BUY",
            quantity=1,
        )
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        msg = str(exc)
        assert "ibkr_upstream_error status=502" in msg
        assert "code=BRIDGE_DOWN" in msg
        assert "secret=xyz" not in msg


def test_ibkr_client_bridge_unreachable_is_sanitized(client, monkeypatch):
    _ = client
    import apps.worker.app.engine.ibkr_client as iclient

    monkeypatch.setattr(iclient.settings, "IBKR_BRIDGE_BASE_URL", "https://ibkr-bridge.example.test")

    def _boom(*args, **kwargs):
        raise iclient.requests.RequestException("network down")

    monkeypatch.setattr(iclient.requests, "post", _boom)

    try:
        iclient.get_ibkr_account_status(api_key="12345678", api_secret="abcdefgh")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert str(exc) == "ibkr_upstream_unreachable"


def test_ibkr_runtime_error_detail_is_sanitized(client, monkeypatch):
    _ = client
    import apps.worker.app.engine.execution_runtime as runtime

    monkeypatch.setattr(runtime, "get_decrypted_exchange_secret", lambda **kwargs: {"api_key": "12345678", "api_secret": "abcdefgh"})
    monkeypatch.setattr(runtime, "get_ibkr_account_status", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("raw secret=zzz")))

    try:
        runtime.get_ibkr_account_status_for_user("user-1")
        assert False, "expected HTTPException"
    except runtime.HTTPException as exc:
        assert exc.status_code == 502
        assert exc.detail == "ibkr_runtime_error"


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


def test_auth_totp_window_clamps_to_safe_range(client, monkeypatch):
    _ = client
    import apps.api.app.routes.auth as auth_routes

    monkeypatch.setattr(auth_routes.settings, "AUTH_TOTP_VALID_WINDOW", -10)
    assert auth_routes._totp_valid_window() == 0

    monkeypatch.setattr(auth_routes.settings, "AUTH_TOTP_VALID_WINDOW", 2)
    assert auth_routes._totp_valid_window() == 2

    monkeypatch.setattr(auth_routes.settings, "AUTH_TOTP_VALID_WINDOW", 99)
    assert auth_routes._totp_valid_window() == 3


def test_auth_normalize_otp_keeps_only_digits(client):
    _ = client
    import apps.api.app.routes.auth as auth_routes

    assert auth_routes._normalize_otp(" 123 456 ") == "123456"
    assert auth_routes._normalize_otp("123-456") == "123456"
    assert auth_routes._normalize_otp("abc12 3x4-56") == "123456"


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


def test_pretrade_scan_idempotency_replay_and_payload_conflict(client):
    token = _token(client, "trader@test.com", "TraderPass123!")
    saved = client.post(
        "/users/exchange-secrets",
        headers=_auth(token),
        json={"exchange": "BINANCE", "api_key": "k1", "api_secret": "s1"},
    )
    assert saved.status_code == 201, saved.text

    headers = {**_auth(token), "X-Idempotency-Key": "scan-idem-1"}
    payload = {
        "top_n": 3,
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
            }
        ],
    }
    first = client.post(
        "/ops/execution/pretrade/binance/scan",
        headers=headers,
        json=payload,
    )
    second = client.post(
        "/ops/execution/pretrade/binance/scan",
        headers=headers,
        json=payload,
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == second.json()

    conflict = client.post(
        "/ops/execution/pretrade/binance/scan",
        headers=headers,
        json={**payload, "top_n": 2},
    )
    assert conflict.status_code == 409
    assert "different payload" in conflict.json()["detail"]


def test_pretrade_scan_blocks_when_exchange_disabled_for_user(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    disabled = client.post(
        "/ops/strategy/assign",
        headers=_auth(admin_token),
        json={
            "user_email": "trader@test.com",
            "exchange": "BINANCE",
            "strategy_id": "SWING_V1",
            "enabled": False,
        },
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["enabled"] is False

    blocked = client.post(
        "/ops/execution/pretrade/binance/scan",
        headers=_auth(trader_token),
        json={
            "top_n": 1,
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
                }
            ],
        },
    )
    assert blocked.status_code == 403
    assert "disabled for this user" in blocked.json()["detail"]


def test_pretrade_auto_pick_dry_run_and_execute(client, monkeypatch):
    token = _token(client, "trader@test.com", "TraderPass123!")
    saved = client.post(
        "/users/exchange-secrets",
        headers=_auth(token),
        json={"exchange": "BINANCE", "api_key": "k1", "api_secret": "s1"},
    )
    assert saved.status_code == 201, saved.text

    dry_run_pick = client.post(
        "/ops/execution/pretrade/binance/auto-pick",
        headers=_auth(token),
        json={
            "top_n": 10,
            "dry_run": True,
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
                }
            ],
        },
    )
    assert dry_run_pick.status_code == 200, dry_run_pick.text
    dry_data = dry_run_pick.json()
    assert dry_data["selected"] is True
    assert dry_data["decision"] == "dry_run_selected"
    assert dry_data["execution"] is None

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
    execute_pick = client.post(
        "/ops/execution/pretrade/binance/auto-pick",
        headers=_auth(token),
        json={
            "top_n": 10,
            "dry_run": False,
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
                }
            ],
        },
    )
    assert execute_pick.status_code == 200, execute_pick.text
    exec_data = execute_pick.json()
    assert exec_data["selected"] is True
    assert exec_data["decision"] == "executed_test_order"
    assert exec_data["execution"]["sent"] is True


def test_pretrade_auto_pick_idempotency_deduplicates_processing(client, monkeypatch):
    token = _token(client, "trader@test.com", "TraderPass123!")
    saved = client.post(
        "/users/exchange-secrets",
        headers=_auth(token),
        json={"exchange": "BINANCE", "api_key": "k1", "api_secret": "s1"},
    )
    assert saved.status_code == 201, saved.text

    import apps.api.app.api.ops as ops_api

    calls = {"count": 0}

    def _fake_auto_pick_from_scan(**kwargs):
        calls["count"] += 1
        return {
            "exchange": "BINANCE",
            "dry_run": False,
            "requested_direction": "LONG",
            "selected": True,
            "selected_symbol": "BTCUSDT",
            "selected_side": "BUY",
            "selected_qty": 0.01,
            "selected_score": 88.5,
            "selected_score_rules": 85.0,
            "selected_score_market": 91.0,
            "selected_trend_score": 0.7,
            "selected_trend_score_1d": 0.7,
            "selected_trend_score_4h": 0.65,
            "selected_trend_score_1h": 0.62,
            "selected_micro_trend_15m": 0.2,
            "selected_market_regime": "bull",
            "selected_liquidity_state": "green",
            "selected_size_multiplier": 1.0,
            "top_candidate_symbol": "BTCUSDT",
            "top_candidate_score": 88.5,
            "top_candidate_score_rules": 85.0,
            "top_candidate_score_market": 91.0,
            "top_candidate_trend_score": 0.7,
            "top_candidate_trend_score_1d": 0.7,
            "top_candidate_trend_score_4h": 0.65,
            "top_candidate_trend_score_1h": 0.62,
            "top_candidate_micro_trend_15m": 0.2,
            "avg_score": 80.0,
            "avg_score_rules": 77.0,
            "avg_score_market": 83.0,
            "decision": "executed_test_order",
            "top_failed_checks": [],
            "execution": {"sent": True, "exchange": "BINANCE"},
            "scan": {
                "exchange": "BINANCE",
                "scanned_assets": 1,
                "returned_assets": 1,
                "passed_assets": 1,
                "blocked_assets": 0,
                "duration_ms_total": 1.0,
                "duration_ms_avg": 1.0,
                "assets": [],
            },
        }

    monkeypatch.setattr(ops_api, "_auto_pick_from_scan", _fake_auto_pick_from_scan)

    payload = {"top_n": 10, "dry_run": False, "direction": "LONG", "candidates": []}
    headers = {**_auth(token), "X-Idempotency-Key": "autopick-idem-1"}
    first = client.post(
        "/ops/execution/pretrade/binance/auto-pick",
        headers=headers,
        json=payload,
    )
    second = client.post(
        "/ops/execution/pretrade/binance/auto-pick",
        headers=headers,
        json=payload,
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == second.json()
    assert calls["count"] == 1


def test_auto_pick_report_last_2_hours(client, monkeypatch):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")
    saved = client.post(
        "/users/exchange-secrets",
        headers=_auth(trader_token),
        json={"exchange": "BINANCE", "api_key": "k1", "api_secret": "s1"},
    )
    assert saved.status_code == 201, saved.text

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
    picked = client.post(
        "/ops/execution/pretrade/binance/auto-pick",
        headers=_auth(trader_token),
        json={
            "top_n": 5,
            "dry_run": False,
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
                }
            ],
        },
    )
    assert picked.status_code == 200, picked.text

    report = client.get("/ops/admin/auto-pick/report?hours=2&limit=200&interval_minutes=5", headers=_auth(admin_token))
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["hours"] == 2
    assert data["interval_minutes"] == 5
    assert len(data["rows"]) >= 1
    row = data["rows"][0]
    assert "decision" in row
    assert "bought" in row
    assert "reason" in row


def test_admin_exit_tick_idempotency_deduplicates_processing(client, monkeypatch):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    import apps.api.app.api.ops as ops_api

    calls = {"count": 0}

    def _fake_run_exit_tick_for_tenant(**kwargs):
        calls["count"] += 1
        return {
            "dry_run": True,
            "paused": False,
            "scanned_positions": 0,
            "exit_candidates": 0,
            "closed_positions": 0,
            "skipped_no_price": 0,
            "skipped_by_policy": 0,
            "errors": 0,
            "results": [],
        }

    monkeypatch.setattr(ops_api, "run_exit_tick_for_tenant", _fake_run_exit_tick_for_tenant)

    headers = {**_auth(admin_token), "X-Idempotency-Key": "exit-tick-idem-1"}
    first = client.post(
        "/ops/admin/exit/tick?dry_run=true&real_only=true&max_positions=10",
        headers=headers,
    )
    second = client.post(
        "/ops/admin/exit/tick?dry_run=true&real_only=true&max_positions=10",
        headers=headers,
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == second.json()
    assert calls["count"] == 1


def test_auto_exit_policy_skip_when_paused(client, monkeypatch):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    from apps.api.app.db.session import SessionLocal
    from apps.api.app.models.user import User
    from apps.api.app.models.position import Position
    import apps.api.app.api.ops as ops_api

    db = SessionLocal()
    try:
        trader = db.query(User).filter(User.email == "trader@test.com").first()
        assert trader is not None
        db.add(
            Position(
                user_id=trader.id,
                signal_id=str(uuid.uuid4()),
                symbol="BTCUSDT",
                side="LONG",
                qty=0.01,
                entry_price=100.0,
                stop_loss=90.0,
                take_profit=120.0,
                status="OPEN",
                opened_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            )
        )
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(ops_api.settings, "AUTO_EXIT_INTERNAL_PAUSE", True)
    monkeypatch.setattr(ops_api.settings, "AUTO_EXIT_INTERNAL_MAX_CLOSES_PER_TICK", 5)
    monkeypatch.setattr(ops_api.settings, "AUTO_EXIT_INTERNAL_SYMBOL_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(ops_api, "_fetch_binance_price_map", lambda symbols: {"BTCUSDT": 101.0})
    monkeypatch.setattr(
        ops_api,
        "_build_exit_checks",
        lambda **kwargs: (
            [{"name": "trend_break", "passed": False, "detail": "forced"}],
            ["trend_break"],
        ),
    )

    out = client.post(
        "/ops/admin/exit/tick?dry_run=false&real_only=true&max_positions=10&user_email=trader@test.com",
        headers=_auth(admin_token),
    )
    assert out.status_code == 200, out.text
    data = out.json()
    assert data["paused"] is True
    assert data["skipped_by_policy"] >= 1
    assert any("policy_skipped:paused" in str(r.get("reason")) for r in data["results"])


def test_auto_exit_policy_respects_max_closes_per_tick(client, monkeypatch):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")
    from apps.api.app.db.session import SessionLocal
    from apps.api.app.models.user import User
    from apps.api.app.models.position import Position
    import apps.api.app.api.ops as ops_api

    db = SessionLocal()
    try:
        trader = db.query(User).filter(User.email == "trader@test.com").first()
        assert trader is not None
        db.add(
            Position(
                user_id=trader.id,
                signal_id=str(uuid.uuid4()),
                symbol="BTCUSDT",
                side="LONG",
                qty=0.01,
                entry_price=100.0,
                stop_loss=90.0,
                take_profit=120.0,
                status="OPEN",
                opened_at=datetime.now(timezone.utc) - timedelta(minutes=40),
            )
        )
        db.add(
            Position(
                user_id=trader.id,
                signal_id=str(uuid.uuid4()),
                symbol="ETHUSDT",
                side="LONG",
                qty=0.01,
                entry_price=100.0,
                stop_loss=90.0,
                take_profit=120.0,
                status="OPEN",
                opened_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            )
        )
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(ops_api.settings, "AUTO_EXIT_INTERNAL_PAUSE", False)
    monkeypatch.setattr(ops_api.settings, "AUTO_EXIT_INTERNAL_MAX_CLOSES_PER_TICK", 1)
    monkeypatch.setattr(ops_api.settings, "AUTO_EXIT_INTERNAL_SYMBOL_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(ops_api.settings, "AUTO_EXIT_INTERNAL_MAX_ERRORS_PER_TICK", 3)
    monkeypatch.setattr(
        ops_api,
        "_fetch_binance_price_map",
        lambda symbols: {"BTCUSDT": 101.0, "ETHUSDT": 102.0},
    )
    monkeypatch.setattr(
        ops_api,
        "_build_exit_checks",
        lambda **kwargs: (
            [{"name": "trend_break", "passed": False, "detail": "forced"}],
            ["trend_break"],
        ),
    )
    monkeypatch.setattr(ops_api, "_close_position_internal", lambda **kwargs: 1.23)

    out = client.post(
        "/ops/admin/exit/tick?dry_run=false&real_only=true&max_positions=10&user_email=trader@test.com",
        headers=_auth(admin_token),
    )
    assert out.status_code == 200, out.text
    data = out.json()
    assert data["closed_positions"] == 1
    assert data["skipped_by_policy"] >= 1
    assert any("policy_skipped:max_closes_reached" in str(r.get("reason")) for r in data["results"])


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


def test_admin_kill_switch_requires_reason_when_disabling(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")

    missing_reason = client.post(
        "/ops/admin/trading-control",
        headers=_auth(admin_token),
        json={"trading_enabled": False, "reason": ""},
    )
    assert missing_reason.status_code == 400
    assert "reason is required" in missing_reason.json()["detail"]

    short_reason = client.post(
        "/ops/admin/trading-control",
        headers=_auth(admin_token),
        json={"trading_enabled": False, "reason": "short"},
    )
    assert short_reason.status_code == 400
    assert "reason is required" in short_reason.json()["detail"]


def test_pretrade_rejects_non_numeric_and_overflow_like_qty(client):
    token = _token(client, "trader@test.com", "TraderPass123!")
    saved = client.post(
        "/users/exchange-secrets",
        headers=_auth(token),
        json={"exchange": "BINANCE", "api_key": "k1", "api_secret": "s1"},
    )
    assert saved.status_code == 201, saved.text

    base_payload = {
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

    non_numeric_qty = client.post(
        "/ops/execution/pretrade/binance/check",
        headers=_auth(token),
        json={**base_payload, "qty": "abc"},
    )
    assert non_numeric_qty.status_code == 422

    overflow_like_qty = client.post(
        "/ops/execution/pretrade/binance/check",
        headers=_auth(token),
        json={**base_payload, "qty": 1_000_001},
    )
    assert overflow_like_qty.status_code == 422


def test_pretrade_scan_rejects_excessive_candidates(client):
    token = _token(client, "trader@test.com", "TraderPass123!")
    saved = client.post(
        "/users/exchange-secrets",
        headers=_auth(token),
        json={"exchange": "BINANCE", "api_key": "k1", "api_secret": "s1"},
    )
    assert saved.status_code == 201, saved.text

    candidates = [
        {
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
        for _ in range(501)
    ]
    too_many = client.post(
        "/ops/execution/pretrade/binance/scan",
        headers=_auth(token),
        json={"top_n": 5, "include_blocked": True, "candidates": candidates},
    )
    assert too_many.status_code == 422


def test_exit_check_rejects_opened_minutes_over_limit(client):
    token = _token(client, "trader@test.com", "TraderPass123!")
    saved = client.post(
        "/users/exchange-secrets",
        headers=_auth(token),
        json={"exchange": "BINANCE", "api_key": "k1", "api_secret": "s1"},
    )
    assert saved.status_code == 201, saved.text

    payload = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "entry_price": 50000,
        "current_price": 50500,
        "stop_loss": 49000,
        "take_profit": 52000,
        "opened_minutes": 10081,
        "trend_break": False,
        "signal_reverse": False,
        "macro_event_block": False,
        "earnings_within_24h": False,
        "market_trend_score": 0.6,
        "atr_pct": 2.0,
        "momentum_score": 0.4,
    }
    resp = client.post(
        "/ops/execution/exit/binance/check",
        headers=_auth(token),
        json=payload,
    )
    assert resp.status_code == 422


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
    assert "id=\"loginScreen\"" in res.text
    assert "id=\"menuScreen\"" in res.text
    assert "id=\"moduleScreen\"" in res.text
    assert "Volver al menu" in res.text
    assert "Salir" in res.text
    assert "sessionStorage" in res.text


def test_ops_console_login_fields_disable_autofill(client):
    res = client.get("/ops/console")
    assert res.status_code == 200
    assert 'id="loginEmail"' in res.text
    assert 'autocomplete="off"' in res.text
    assert 'name="ops_email"' in res.text


def test_ops_dashboard_page_serves_same_console_shell(client):
    res = client.get("/ops/dashboard")
    assert res.status_code == 200
    assert "Ops Console v1" in res.text
    assert "id=\"loginScreen\"" in res.text
    assert "id=\"menuScreen\"" in res.text
    assert "id=\"moduleScreen\"" in res.text


def test_superuser_email_bypasses_admin_role_checks(client, monkeypatch):
    import apps.api.app.api.deps as deps_mod

    monkeypatch.setattr(deps_mod.settings, "SUPERUSER_EMAILS", "trader@test.com")
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    trading_control = client.get("/ops/admin/trading-control", headers=_auth(trader_token))
    assert trading_control.status_code == 200, trading_control.text

    users = client.get("/users", headers=_auth(trader_token))
    assert users.status_code == 200, users.text


def test_admin_can_reset_user_2fa(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")

    users = client.get("/users", headers=_auth(admin_token))
    assert users.status_code == 200, users.text
    trader = next((u for u in users.json() if u["email"] == "trader@test.com"), None)
    assert trader is not None

    reset = client.post(
        f"/users/{trader['id']}/2fa/reset?reason=admin%20recovery%20flow",
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


def test_learning_status_exposes_quality_rates(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")

    status = client.get("/ops/admin/learning/status", headers=_auth(admin_token))
    assert status.status_code == 200, status.text
    data = status.json()
    assert "pending_rate_pct" in data
    assert "labeled_rate_pct" in data
    assert "expired_rate_pct" in data
    assert "no_price_rate_pct" in data


def test_learning_endpoints_reject_invalid_ranges(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")

    bad_label = client.post(
        "/ops/admin/learning/label?dry_run=true&horizon_minutes=1&limit=0",
        headers=_auth(admin_token),
    )
    assert bad_label.status_code == 400
    assert "must be between" in bad_label.json()["detail"]

    bad_rollup_refresh = client.post(
        "/ops/admin/learning/rollup/refresh?hours=0&dry_run=true",
        headers=_auth(admin_token),
    )
    assert bad_rollup_refresh.status_code == 400
    assert "hours must be between" in bad_rollup_refresh.json()["detail"]


def test_learning_endpoints_reject_invalid_filters(client):
    admin_token = _token(client, "admin@test.com", "AdminPass123!")

    bad_dataset = client.get(
        "/ops/admin/learning/dataset?hours=24&limit=100&exchange=BADX",
        headers=_auth(admin_token),
    )
    assert bad_dataset.status_code == 400
    assert "exchange must be one of" in bad_dataset.json()["detail"]

    bad_report = client.get(
        "/ops/admin/learning/suggestion-report?hours=24&limit=100&outcome_status=WRONG",
        headers=_auth(admin_token),
    )
    assert bad_report.status_code == 400
    assert "outcome_status must be one of" in bad_report.json()["detail"]


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


def test_signals_claim_limit_bounds(client):
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    low = client.post("/signals/claim?limit=0", headers=_auth(trader_token))
    assert low.status_code == 400
    assert "limit must be between 1 and 100" in low.json()["detail"]

    high = client.post("/signals/claim?limit=101", headers=_auth(trader_token))
    assert high.status_code == 400
    assert "limit must be between 1 and 100" in high.json()["detail"]


def test_signal_create_rejects_invalid_price_structure(client):
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    invalid = client.post(
        "/signals",
        headers=_auth(trader_token),
        json={
            "symbol": "BTCUSDT",
            "module": "SWING_V1",
            "base_risk_percent": 0.5,
            "entry_price": 100.0,
            "stop_loss": 110.0,
            "take_profit": 120.0,
        },
    )
    assert invalid.status_code == 422


def test_close_position_idempotency_and_non_finite_guard(client):
    trader_token = _token(client, "trader@test.com", "TraderPass123!")

    created = client.post(
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
    assert created.status_code == 200, created.text
    signal_id = created.json()["id"]

    claim = client.post("/signals/claim", headers=_auth(trader_token))
    assert claim.status_code == 200, claim.text

    opened = client.post(
        "/positions/open_from_signal",
        headers=_auth(trader_token),
        params={"signal_id": signal_id, "qty": 0.01},
    )
    assert opened.status_code == 200, opened.text
    position_id = opened.json()["id"]

    non_finite = client.post(
        "/positions/close",
        headers=_auth(trader_token),
        params={"position_id": position_id, "exit_price": "nan", "fees": 0.0},
    )
    assert non_finite.status_code == 400
    assert "exit_price must be finite and > 0" in non_finite.json()["detail"]

    idem_headers = {**_auth(trader_token), "X-Idempotency-Key": "close-position-key-1"}
    first = client.post(
        "/positions/close",
        headers=idem_headers,
        params={"position_id": position_id, "exit_price": 101.0, "fees": 0.1},
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/positions/close",
        headers=idem_headers,
        params={"position_id": position_id, "exit_price": 101.0, "fees": 0.1},
    )
    assert second.status_code == 200, second.text
    assert first.json() == second.json()


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
