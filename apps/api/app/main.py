from apps.api.app.api.binance_portfolio import router as binance_portfolio_router
from apps.api.app.api.signals import router as signals_router
from apps.api.app.api.binance_execution import router as binance_execution_router
from apps.api.app.api.positions import router as positions_router
from apps.api.app.routes.auth import router as auth_router
from contextlib import asynccontextmanager
from apps.api.app.api.ops_ibkr import router as ops_ibkr_router
from apps.api.app.api.binance_ping import router as binance_ping_router
from apps.api.app.api.binance_positions import router as binance_positions_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


 

import apps.api.app.models.signal
import apps.api.app.models.position
import apps.api.app.models.daily_risk
import apps.api.app.models.user_2fa
import apps.api.app.models.audit_log
import apps.api.app.models.exchange_secret
import apps.api.app.models.strategy_assignment
import apps.api.app.models.user_risk_profile
import apps.api.app.models.revoked_token
import apps.api.app.models.session_revocation
import apps.api.app.models.runtime_setting
import apps.api.app.models.idempotency_key
import apps.api.app.models.risk_profile_config
import apps.api.app.models.user_risk_settings
import apps.api.app.models.strategy_runtime_policy
import apps.api.app.models.market_trend_snapshot
import apps.api.app.models.learning_decision
import apps.api.app.models.learning_outcome
import apps.api.app.models.learning_rollup_hourly

import threading
import time

from apps.api.app.api.users import router as users_router
from apps.api.app.api.admin_recovery import router as admin_recovery_router
from apps.api.app.api.trading_control import router as trading_control_router

from apps.api.app.db.session import engine, Base, SessionLocal
from sqlalchemy import inspect, text
from apps.api.app.core.config import settings
from apps.api.app.services.global_orchestrator import run_global_shadow_cycle


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _safe_startup_schema_ensures()
    _start_auto_pick_scheduler()
    try:
        yield
    finally:
        _stop_auto_pick_scheduler()


app = FastAPI(title="crypto-saas API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

# OJO: users_router ya importa el modelo User, así que el modelo ya queda registrado.
# Base.metadata.create_all(bind=engine)


def _ensure_runtime_policy_columns():
    insp = inspect(engine)
    try:
        cols = {c["name"] for c in insp.get_columns("strategy_runtime_policy")}
    except Exception:
        return
    with engine.begin() as conn:
        if "min_score_pct" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE strategy_runtime_policy "
                    "ADD COLUMN IF NOT EXISTS min_score_pct DOUBLE PRECISION NOT NULL DEFAULT 78.0"
                )
            )
        if "score_weight_rules" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE strategy_runtime_policy "
                    "ADD COLUMN IF NOT EXISTS score_weight_rules DOUBLE PRECISION NOT NULL DEFAULT 0.4"
                )
            )
        if "score_weight_market" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE strategy_runtime_policy "
                    "ADD COLUMN IF NOT EXISTS score_weight_market DOUBLE PRECISION NOT NULL DEFAULT 0.6"
                )
            )




def _ensure_exchange_secret_columns():
    insp = inspect(engine)
    try:
        cols = {c["name"] for c in insp.get_columns("exchange_secret")}
    except Exception:
        return
    with engine.begin() as conn:
        if "key_version" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE exchange_secret "
                    "ADD COLUMN IF NOT EXISTS key_version VARCHAR NOT NULL DEFAULT 'v1'"
                )
            )

def _ensure_ibkr_fills_columns():
    insp = inspect(engine)
    try:
        tables = set(insp.get_table_names())
        if "ibkr_fills" not in tables:
            return
        cols = {c["name"] for c in insp.get_columns("ibkr_fills")}
    except Exception:
        return
    with engine.begin() as conn:
        if "account_id" not in cols:
            conn.execute(text("ALTER TABLE ibkr_fills ADD COLUMN IF NOT EXISTS account_id VARCHAR"))
        if "side" not in cols:
            conn.execute(text("ALTER TABLE ibkr_fills ADD COLUMN IF NOT EXISTS side VARCHAR"))
        if "order_id" not in cols:
            conn.execute(text("ALTER TABLE ibkr_fills ADD COLUMN IF NOT EXISTS order_id VARCHAR"))
        if "perm_id" not in cols:
            conn.execute(text("ALTER TABLE ibkr_fills ADD COLUMN IF NOT EXISTS perm_id VARCHAR"))
        if "client_id" not in cols:
            conn.execute(text("ALTER TABLE ibkr_fills ADD COLUMN IF NOT EXISTS client_id VARCHAR"))
        if "order_ref" not in cols:
            conn.execute(text("ALTER TABLE ibkr_fills ADD COLUMN IF NOT EXISTS order_ref VARCHAR"))
        if "cum_qty" not in cols:
            conn.execute(text("ALTER TABLE ibkr_fills ADD COLUMN IF NOT EXISTS cum_qty DOUBLE PRECISION"))
        if "avg_price" not in cols:
            conn.execute(text("ALTER TABLE ibkr_fills ADD COLUMN IF NOT EXISTS avg_price DOUBLE PRECISION"))


def _safe_startup_schema_ensures():
    for ensure_func in (
        _ensure_runtime_policy_columns,
        _ensure_exchange_secret_columns,
        _ensure_ibkr_fills_columns,
    ):
        try:
            ensure_func()
        except Exception as exc:
            print(f"WARNING startup schema ensure failed: {ensure_func.__name__}: {exc}")


app.include_router(users_router)
app.include_router(signals_router)
app.include_router(positions_router)
app.include_router(ops_ibkr_router)
app.include_router(binance_ping_router)
app.include_router(binance_positions_router)
app.include_router(binance_portfolio_router)
app.include_router(binance_execution_router)
app.include_router(admin_recovery_router)
app.include_router(trading_control_router)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"app": "crypto-saas", "docs": "/docs"}

app.include_router(auth_router)

_scheduler_stop_event = threading.Event()
_scheduler_thread: threading.Thread | None = None
_AUTO_PICK_LOCK_KEY = 887731


def _legacy_exit_tick_disabled(**_kwargs):
    return {
        "status": "disabled",
        "reason": "ops_py_detached",
        "scanned_positions": 0,
        "exit_candidates": 0,
        "closed_positions": 0,
        "skipped_no_price": 0,
        "skipped_by_policy": 0,
        "errors": 0,
        "paused": True,
        "dry_run": True,
    }


def _legacy_market_monitor_tick_disabled(**_kwargs):
    return {
        "status": "disabled",
        "reason": "ops_py_detached",
        "inserted": 0,
        "legacy_enabled": False,
    }


def _legacy_auto_pick_tick_disabled(**_kwargs):
    return {
        "status": "disabled",
        "reason": "ops_py_detached",
        "persisted": False,
        "executed": False,
    }


def _legacy_learning_tick_disabled(**_kwargs):
    return {
        "status": "disabled",
        "reason": "ops_py_detached",
    }


def _global_shadow_tick_once(*, db) -> dict | None:
    if not bool(settings.AUTO_PICK_GLOBAL_SHADOW_ENABLED):
        return None
    try:
        return run_global_shadow_cycle(
            db=db,
            account_id="default",
        )
    except Exception as shadow_exc:
        return {
            "status": "shadow_error",
            "error": str(shadow_exc),
        }


def _auto_pick_tick_once() -> None:
    db = SessionLocal()
    try:
        exit_out = {
            "scanned_positions": 0,
            "exit_candidates": 0,
            "closed_positions": 0,
            "skipped_no_price": 0,
            "skipped_by_policy": 0,
            "errors": 0,
            "paused": False,
            "dry_run": True,
        }
        if bool(settings.AUTO_EXIT_INTERNAL_ENABLED):
            exit_out = _legacy_exit_tick_disabled(
                db=db,
                tenant_id=settings.AUTO_PICK_INTERNAL_TENANT_ID or "default",
                dry_run=bool(settings.AUTO_EXIT_INTERNAL_DRY_RUN),
                real_only=bool(settings.AUTO_EXIT_INTERNAL_REAL_ONLY),
                include_service_users=bool(settings.AUTO_EXIT_INTERNAL_INCLUDE_SERVICE_USERS),
                max_positions=int(settings.AUTO_EXIT_INTERNAL_MAX_POSITIONS or 500),
            )
        monitor = {"inserted": 0, "legacy_enabled": False}
        if bool(settings.AUTO_PICK_LEGACY_MARKET_MONITOR_ENABLED):
            monitor = _legacy_market_monitor_tick_disabled(
                db=db,
                tenant_id=settings.AUTO_PICK_INTERNAL_TENANT_ID or "default",
            )
            monitor["legacy_enabled"] = True
        out = {
            "executed_count": 0,
            "dry_run": bool(settings.AUTO_PICK_INTERNAL_SCHEDULER_DRY_RUN),
            "top_n": int(settings.AUTO_PICK_INTERNAL_SCHEDULER_TOP_N),
            "legacy_enabled": False,
        }
        if bool(settings.AUTO_PICK_LEGACY_TICK_ENABLED):
            out = _legacy_auto_pick_tick_disabled(
                db=db,
                tenant_id=settings.AUTO_PICK_INTERNAL_TENANT_ID or "default",
                dry_run=bool(settings.AUTO_PICK_INTERNAL_SCHEDULER_DRY_RUN),
                top_n=int(settings.AUTO_PICK_INTERNAL_SCHEDULER_TOP_N),
                real_only=bool(settings.AUTO_PICK_INTERNAL_REAL_ONLY),
                include_service_users=bool(settings.AUTO_PICK_INTERNAL_INCLUDE_SERVICE_USERS),
            )
            out["legacy_enabled"] = True
        _legacy_learning_tick_disabled(
            db=db,
            tenant_id=settings.AUTO_PICK_INTERNAL_TENANT_ID or "default",
        )
        shadow_out = _global_shadow_tick_once(db=db)
        print(
            "[auto-pick-scheduler] tick ok",
            {
                "monitor_inserted": monitor.get("inserted", 0),
                "executed_count": out.get("executed_count", 0),
                "dry_run": out.get("dry_run", True),
                "top_n": out.get("top_n", 10),
                "exit_scanned_positions": exit_out.get("scanned_positions", 0),
                "exit_candidates": exit_out.get("exit_candidates", 0),
                "exit_closed_positions": exit_out.get("closed_positions", 0),
                "exit_skipped_no_price": exit_out.get("skipped_no_price", 0),
                "exit_skipped_by_policy": exit_out.get("skipped_by_policy", 0),
                "exit_errors": exit_out.get("errors", 0),
                "exit_paused": exit_out.get("paused", False),
                "exit_dry_run": exit_out.get("dry_run", True),
                "shadow_status": (shadow_out or {}).get("status"),
                "shadow_symbol": (shadow_out or {}).get("symbol"),
                "shadow_persisted": (shadow_out or {}).get("persisted"),
                "shadow_executed": (shadow_out or {}).get("executed"),
            },
            flush=True,
        )
    except Exception as exc:
        print(f"[auto-pick-scheduler] tick error: {exc}", flush=True)
    finally:
        db.close()


def _auto_pick_tick_once_with_lock() -> None:
    if settings.DATABASE_URL.startswith("sqlite"):
        _auto_pick_tick_once()
        return
    with engine.begin() as conn:
        got_lock = bool(
            conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": _AUTO_PICK_LOCK_KEY}).scalar()
        )
    if not got_lock:
        return
    try:
        _auto_pick_tick_once()
    finally:
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _AUTO_PICK_LOCK_KEY})


def _scheduler_loop() -> None:
    interval_minutes = max(1, int(settings.AUTO_PICK_INTERNAL_SCHEDULER_INTERVAL_MINUTES))
    interval_seconds = interval_minutes * 60
    while not _scheduler_stop_event.is_set():
        now = time.time()
        wait_seconds = interval_seconds - (now % interval_seconds)
        if _scheduler_stop_event.wait(timeout=wait_seconds):
            break
        _auto_pick_tick_once_with_lock()


def _start_auto_pick_scheduler() -> None:
    global _scheduler_thread
    if not settings.AUTO_PICK_INTERNAL_SCHEDULER_ENABLED:
        return
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _scheduler_stop_event.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, name="auto-pick-scheduler", daemon=True)
    _scheduler_thread.start()
    print("[auto-pick-scheduler] started", flush=True)


def _stop_auto_pick_scheduler() -> None:
    _scheduler_stop_event.set()
