from pydantic import BaseModel

from apps.worker.app.engine.market_data_engine import MarketDataEngine
from apps.worker.app.engine.risk_engine import RiskEngine
from apps.worker.app.engine.binance_market_data_adapter import BinanceMarketDataAdapter
class ManualRiskEvalRequest(BaseModel):
    user_id: str
    symbol: str
    intent: dict  # Debe contener los campos requeridos por RiskIntent

class ManualRiskEvalResponse(BaseModel):
    price_update: dict
    risk_result: dict


@router.post("/manual-binance-risk-eval", response_model=ManualRiskEvalResponse)
def manual_binance_risk_eval(
    payload: ManualRiskEvalRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Endpoint manual: actualiza precio real Binance y evalúa riesgo para un intent dado.
    """
    # Instanciar/adquirir engines/adapters (en producción, usar singletons o DI)
    market_data_engine = MarketDataEngine()
    risk_engine = RiskEngine(market_data_engine=market_data_engine)
    binance_adapter = BinanceMarketDataAdapter()

    # 1. Actualizar precio real
    price_result = market_data_engine.update_binance_price(
        payload.user_id, payload.symbol, binance_adapter
    )
    price_update = {
        "symbol": payload.symbol,
        "user_id": payload.user_id,
        "price": getattr(price_result, "price", None) if price_result else None,
        "timestamp": getattr(price_result, "timestamp", None) if price_result else None,
        "ok": price_result is not None,
    }

    # 2. Evaluar riesgo
    # Construir RiskIntent desde el dict recibido
    intent_obj = RiskEngine.RiskIntent if hasattr(RiskEngine, "RiskIntent") else None
    if intent_obj is None:
        from apps.worker.app.engine.risk_engine import RiskIntent as intent_obj
    risk_intent = intent_obj(**payload.intent)
    risk_result = risk_engine.evaluate_intent(risk_intent)

    return ManualRiskEvalResponse(
        price_update=price_update,
        risk_result={
            k: getattr(risk_result, k, None) for k in ["approved", "reason", "adjusted_quantity"]
        },
    )

from apps.worker.app.engine.execution_runtime import cancel_broker_order

# Cancel Order API

class CancelOrderRequest(BaseModel):
    exchange: str
    symbol: str
    client_order_id: str
    market: str = "SPOT"

@router.post("/cancel-order")
def cancel_order_endpoint(
    payload: CancelOrderRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        response = cancel_broker_order(
            exchange=payload.exchange,
            symbol=payload.symbol,
            client_order_id=payload.client_order_id,
            market=payload.market,
            user_id=current_user.id,
        )
        return response
    except HTTPException as exc:
        raise exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cancel order failed: {exc}",
        )
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import random
import threading
import time
import uuid
from pathlib import Path
from typing import Optional
from urllib import error as urllib_error, parse as urllib_parse, request as urllib_request

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import and_, delete, func, or_, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from apps.api.app.api.deps import get_current_user, require_any_role, require_role
from apps.api.app.db.session import engine, get_db
from apps.api.app.models.audit_log import AuditLog
from apps.api.app.models.daily_risk import DailyRiskState
from apps.api.app.models.exchange_secret import ExchangeSecret
from apps.api.app.models.idempotency_key import IdempotencyKey
from apps.api.app.models.position import Position
from apps.api.app.models.market_trend_snapshot import MarketTrendSnapshot
from apps.api.app.models.learning_decision import LearningDecisionSnapshot
from apps.api.app.models.learning_outcome import LearningDecisionOutcome
from apps.api.app.models.learning_rollup_hourly import LearningRollupHourly
from apps.api.app.models.signal import Signal
from apps.api.app.models.strategy_assignment import StrategyAssignment
from apps.api.app.models.user_2fa import UserTwoFactor
from apps.api.app.schemas.execution import (
    AccountStatusOut,
    BinanceTestOrderOut,
    BinanceTestOrderRequest,
    IbkrTestOrderOut,
    IbkrTestOrderRequest,
    ExecutionPrepareOut,
    ExecutionPrepareRequest,
)
from apps.api.app.schemas.strategy import (
    ExitCheckOut,
    ExitCheckRequest,
    PretradeAutoPickOut,
    PretradeAutoPickRequest,
    PretradeCheckOut,
    PretradeCheckRequest,
    PretradeScanOut,
    PretradeScanRequest,
    StrategyAssignmentOut,
    StrategyAssignOut,
    StrategyAssignRequest,
)
from apps.api.app.schemas.security import (
    ReencryptSecretsOut,
    ReencryptSecretsRequest,
    CleanupSmokeUsersOut,
    CleanupSmokeUsersUserOut,
    DashboardSummaryOut,
    DashboardSecurityOut,
    DashboardOperationsOut,
    DashboardEventsOut,
    DashboardProfileProductivityOut,
    DashboardTrendDayOut,
    DashboardUserOut,
    SecurityPostureOut,
    SecurityPostureSummaryOut,
    SecurityPostureUserOut,
    TradingControlOut,
    TradingControlUpdateRequest,
    IdempotencyStatsOut,
    IdempotencyCleanupOut,
    BackofficeSummaryOut,
    BackofficeUserOut,
    RiskProfileConfigOut,
    RiskProfileConfigUpdateRequest,
    StrategyRuntimePolicyOut,
    StrategyRuntimePolicyUpdateRequest,
    AutoPickReportItemOut,
    AutoPickReportOut,
    AutoPickLiquidityEventOut,
    AutoPickLiquidityReportOut,
    MarketTrendSnapshotOut,
    MarketTrendMonitorOut,
    LearningDatasetOut,
    LearningDatasetRowOut,
    LearningLabelRunOut,
    LearningRetentionRunOut,
    LearningRollupOut,
    LearningRollupRowOut,
    LearningHealthOut,
    LearningHealthWindowOut,
    LearningExperienceOut,
    LearningStatusOut,
    LearningSuggestionReportOut,
    LearningSuggestionReportRowOut,
    AutoExitTickItemOut,
    AutoExitTickOut,
    CIWorkflowStatusOut,
    CIStatusOut,
    CILogHintOut,
)
from apps.api.app.core.config import settings
from apps.api.app.models.user import User
from apps.api.app.schemas.audit import AuditExportMetaOut, AuditExportOut, AuditOut
from apps.api.app.core.time import today_colombia
from apps.api.app.services.audit import log_audit_event
from apps.api.app.services.key_rotation import reencrypt_exchange_secrets
from apps.api.app.services.risk_profiles import (
    apply_profile_daily_limits,
    list_risk_profiles,
    resolve_risk_profile,
    upsert_risk_profile_config,
)
from apps.api.app.services.idempotency import (
    cleanup_old_idempotency_keys,
    consume_idempotent_response,
    reserve_idempotent_intent,
    finalize_idempotent_intent,
    store_idempotent_response,
)
from apps.api.app.services.decision_engine import (
    rank_scan_rows,
    score_threshold_for_side,
)
from apps.api.app.services.exit_policy_engine import (
    sort_exit_candidates,
    resolve_policy_skip_reason_basic,
)
from apps.api.app.services.learning_pipeline_engine import (
    compute_rate,
    validate_choice_param,
    validate_range_param,
)
from apps.api.app.services.trading_controls import (
    assert_exposure_limits,
    assert_trading_enabled,
    get_trading_enabled,
    infer_exchange_from_symbol,
    set_trading_enabled,
)
from apps.api.app.services.strategy_assignments import (
    is_exchange_enabled_for_user,
    resolve_strategy_for_user_exchange,
    upsert_strategy_assignment,
)
from apps.api.app.services.strategy_runtime_policy import (
    infer_market_regime,
    list_runtime_policies,
    resolve_runtime_policy,
    upsert_runtime_policy,
)
from apps.api.app.services.user_readiness import build_readiness_report
from apps.worker.app.engine.execution_runtime import (
    get_binance_account_status_for_user,
    get_binance_spot_usdt_free_for_user,
    get_ibkr_account_status_for_user,
    execute_binance_test_order_for_user,
    execute_ibkr_test_order_for_user,
    prepare_execution_for_user,
    resolve_execution_quantity_preview,
)

router = APIRouter(prefix="/ops", tags=["ops"])
_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


def _render_ops_template(filename: str) -> HTMLResponse:
    path = _TEMPLATES_DIR / filename
    html = path.read_text(encoding="utf-8")
    return HTMLResponse(html)


_CI_WORKFLOW_DEFS = [
    ("integration", "Integration Tests", "integration-tests.yml"),
    ("smoke", "Smoke Prod", "smoke-prod.yml"),
    ("dr_drill", "DR Drill Monthly", "dr-drill-monthly.yml"),
]


def _ci_state(status: str, conclusion: Optional[str]) -> str:
    if status == "completed":
        return "green" if conclusion == "success" else "red"
    if status in {"queued", "in_progress", "requested", "waiting"}:
        return "yellow"
    return "yellow"


def _github_api_json(path: str) -> dict:
    base = str(settings.GITHUB_API_BASE_URL or "https://api.github.com").rstrip("/")
    url = f"{base}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = str(settings.GITHUB_ACTIONS_READ_TOKEN or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib_request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib_request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        detail = "github_api_http_error"
        if exc.code == 401:
            detail = "github_api_unauthorized"
        elif exc.code == 403:
            detail = "github_api_forbidden_or_rate_limited"
        elif exc.code == 404:
            detail = "github_repo_or_workflow_not_found"
        raise HTTPException(status_code=502, detail=detail) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="github_api_unreachable") from exc
    try:
        return json.loads(body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="github_api_invalid_json") from exc


def _fetch_latest_workflow_run(*, owner: str, repo: str, branch: str, workflow_file: str) -> Optional[dict]:
    wf = urllib_parse.quote(workflow_file, safe="")
    b = urllib_parse.quote(branch, safe="")
    path = f"/repos/{owner}/{repo}/actions/workflows/{wf}/runs?per_page=1&branch={b}"
    data = _github_api_json(path)
    runs = data.get("workflow_runs") or []
    if not runs:
        return None
    return runs[0]


def _build_ci_status_snapshot() -> CIStatusOut:
    owner = str(settings.GITHUB_ACTIONS_OWNER or "").strip()
    repo = str(settings.GITHUB_ACTIONS_REPO or "").strip()
    branch = str(settings.GITHUB_ACTIONS_DEFAULT_BRANCH or "main").strip() or "main"
    now = datetime.now(timezone.utc).isoformat()
    workflows: list[CIWorkflowStatusOut] = []
    if not owner or not repo:
        for key, label, workflow_file in _CI_WORKFLOW_DEFS:
            workflows.append(
                CIWorkflowStatusOut(
                    key=key,
                    label=label,
                    workflow_file=workflow_file,
                    note="github_repo_not_configured",
                )
            )
        return CIStatusOut(generated_at=now, owner=owner, repo=repo, branch=branch, workflows=workflows)

    for key, label, workflow_file in _CI_WORKFLOW_DEFS:
        try:
            run = _fetch_latest_workflow_run(
                owner=owner,
                repo=repo,
                branch=branch,
                workflow_file=workflow_file,
            )
            if not run:
                workflows.append(
                    CIWorkflowStatusOut(
                        key=key,
                        label=label,
                        workflow_file=workflow_file,
                        note="no_runs_found",
                    )
                )
                continue
            status_v = str(run.get("status") or "unknown")
            conc = run.get("conclusion")
            workflows.append(
                CIWorkflowStatusOut(
                    key=key,
                    label=label,
                    workflow_file=workflow_file,
                    run_id=run.get("id"),
                    run_number=run.get("run_number"),
                    status=status_v,
                    conclusion=conc,
                    state=_ci_state(status_v, conc),
                    html_url=run.get("html_url"),
                    updated_at=run.get("updated_at"),
                    event=run.get("event"),
                    branch=run.get("head_branch"),
                )
            )
        except HTTPException as exc:
            workflows.append(
                CIWorkflowStatusOut(
                    key=key,
                    label=label,
                    workflow_file=workflow_file,
                    state="yellow",
                    note=str(exc.detail),
                )
            )
    return CIStatusOut(generated_at=now, owner=owner, repo=repo, branch=branch, workflows=workflows)


_binance_ticker_cache_lock = threading.Lock()
_binance_ticker_cache_rows: list[dict] = []
_binance_ticker_cache_expiry: float = 0.0
_binance_klines_cache_lock = threading.Lock()
_binance_klines_cache: dict[tuple[str, str], tuple[float, list[list]]] = {}


def _is_real_user_email(email: str) -> bool:
    e = (email or "").lower()
    if e.startswith("smoke.") or e.startswith("disabled_"):
        return False
    if e.endswith("@example.com") or e.endswith("@example.invalid"):
        return False
    return True


def _is_service_user_email(email: str) -> bool:
    return (email or "").lower().startswith("ops.bot.")


def _tenant_id(user: User) -> str:
    return (user.tenant_id or "default")


def _semantic_intent_lock_key(*, tenant_id: str, user_id: str, exchange: str, symbol: str, side: str) -> int:
    # Deterministic 64-bit advisory lock key for (tenant,user,exchange,symbol,side) intent.
    base = "|".join(
        [
            str(tenant_id or "default").strip().lower(),
            str(user_id or "").strip().lower(),
            str(exchange or "").strip().upper(),
            str(symbol or "").strip().upper(),
            str(side or "").strip().upper(),
        ]
    )
    unsigned = int(hashlib.sha256(base.encode("utf-8")).hexdigest()[:16], 16)
    if unsigned >= (1 << 63):
        return unsigned - (1 << 64)
    return unsigned


def _parse_symbol_allowlist(value: str) -> set[str]:
    raw = (value or "").strip()
    if not raw:
        return set()
    return {item.strip().upper() for item in raw.split(",") if item.strip()}


def _parse_csv_allowlist(value: str, *, upper: bool = False) -> set[str]:
    raw = (value or "").strip()
    if not raw:
        return set()
    out = set()
    for item in raw.split(","):
        token = item.strip()
        if not token:
            continue
        out.add(token.upper() if upper else token.lower())
    return out


def _resolve_auto_pick_execution_status(response: dict) -> str:
    decision = str(response.get("decision") or "").strip().lower()
    selected = bool(response.get("selected"))
    execution = response.get("execution")
    if str(response.get("dry_run") or "").lower() == "true":
        return "dry_run"
    if decision.startswith("executed_test_order"):
        return "executed"
    if isinstance(execution, dict) and execution.get("error"):
        return "execution_error"
    if selected:
        return "selected_not_executed"
    return "not_selected"


def _resolve_prediction_vs_real_state(
    *,
    predicted_positive: Optional[bool],
    outcome_status: Optional[str],
    realized_hit: Optional[bool],
) -> str:
    if predicted_positive is None:
        return "no_prediction"
    if str(outcome_status or "").lower() != "labeled" or realized_hit is None:
        return "pending"
    return "match" if bool(predicted_positive) == bool(realized_hit) else "mismatch"


def _attach_prediction_vs_real(
    *,
    db: Session,
    response: dict,
) -> None:
    predicted_hit_pct = response.get("selected_learning_prob_hit_pct")
    if predicted_hit_pct is None:
        predicted_hit_pct = response.get("top_candidate_learning_prob_hit_pct")

    predicted_positive: Optional[bool] = None
    if predicted_hit_pct is not None:
        try:
            predicted_positive = float(predicted_hit_pct) >= 50.0
            predicted_hit_pct = round(float(predicted_hit_pct), 2)
        except Exception:
            predicted_positive = None
            predicted_hit_pct = None

    outcome_status: Optional[str] = None
    realized_hit: Optional[bool] = None
    decision_id = str(response.get("learning_decision_id") or "").strip()
    if decision_id:
        outcomes = (
            db.execute(
                select(LearningDecisionOutcome)
                .where(LearningDecisionOutcome.decision_id == decision_id)
                .order_by(LearningDecisionOutcome.horizon_minutes.asc())
            )
            .scalars()
            .all()
        )
        chosen = None
        for o in outcomes:
            if chosen is None:
                chosen = o
            if str(o.outcome_status or "").lower() == "labeled":
                chosen = o
                break
        if chosen is not None:
            outcome_status = chosen.outcome_status
            if str(chosen.outcome_status or "").lower() == "labeled":
                realized_hit = chosen.hit

    response["predicted_hit_pct"] = predicted_hit_pct
    response["predicted_positive"] = predicted_positive
    response["outcome_status"] = outcome_status
    response["realized_hit"] = realized_hit
    response["prediction_vs_real"] = _resolve_prediction_vs_real_state(
        predicted_positive=predicted_positive,
        outcome_status=outcome_status,
        realized_hit=realized_hit,
    )


def _require_idempotency_for_auto_pick_execution(
    *,
    payload: PretradeAutoPickRequest,
    idempotency_key: Optional[str],
) -> None:
    if bool(payload.dry_run):
        return
    key = str(idempotency_key or "").strip()
    if key:
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="X-Idempotency-Key is required when dry_run=false",
    )


def _auto_pick_real_guard_reason(
    *,
    current_user: User,
    exchange: str,
    symbol: str,
) -> Optional[str]:
    if not bool(settings.AUTO_PICK_REAL_GUARD_ENABLED):
        return None

    user_email = (current_user.email or "").strip().lower()
    ex = (exchange or "").strip().upper()
    sym = (symbol or "").strip().upper()

    allowed_emails = _parse_csv_allowlist(settings.AUTO_PICK_REAL_ALLOWED_EMAILS, upper=False)
    if allowed_emails and user_email not in allowed_emails:
        return "real_guard_email_allowlist"

    allowed_exchanges = _parse_csv_allowlist(settings.AUTO_PICK_REAL_ALLOWED_EXCHANGES, upper=True)
    if allowed_exchanges and ex not in allowed_exchanges:
        return "real_guard_exchange_allowlist"

    allowed_symbols = _parse_symbol_allowlist(settings.AUTO_PICK_REAL_ALLOWED_SYMBOLS)
    if allowed_symbols and sym not in allowed_symbols:
        return "real_guard_symbol_allowlist"

    quote = str(settings.AUTO_PICK_REAL_BINANCE_QUOTE or "").strip().upper()
    if ex == "BINANCE" and quote and not sym.endswith(quote):
        return "real_guard_binance_quote"

    return None


def _build_auto_pick_exit_plan(
    *,
    exchange: str,
    symbol: str,
    side: str,
    rr_estimate: Optional[float],
    atr_pct: Optional[float],
) -> tuple[Optional[dict], Optional[str]]:
    rr = float(rr_estimate or 0.0)
    min_rr = max(0.5, float(settings.AUTO_PICK_REAL_EXIT_PLAN_MIN_RR or 1.2))
    if rr < min_rr:
        return None, "real_guard_exit_plan_rr_below_minimum"

    entry_price: Optional[float] = None
    if (exchange or "").upper() == "BINANCE":
        entry_price = _fetch_binance_price_map([symbol]).get(str(symbol).upper())
    if not entry_price or entry_price <= 0:
        return None, "real_guard_exit_plan_price_unavailable"

    atr = max(0.0, float(atr_pct or 0.0))
    risk_from_atr_pct = atr * float(settings.AUTO_PICK_REAL_EXIT_PLAN_ATR_MULTIPLIER or 0.8)
    min_risk_pct = max(0.05, float(settings.AUTO_PICK_REAL_EXIT_PLAN_MIN_RISK_PCT or 0.35))
    max_risk_pct = max(min_risk_pct, float(settings.AUTO_PICK_REAL_EXIT_PLAN_MAX_RISK_PCT or 3.0))
    risk_pct = max(min_risk_pct, min(max_risk_pct, risk_from_atr_pct))
    risk_frac = risk_pct / 100.0
    if risk_frac <= 0:
        return None, "real_guard_exit_plan_invalid_risk"

    side_u = str(side or "BUY").upper()
    risk_abs = float(entry_price) * risk_frac
    if side_u == "SELL":
        stop_loss = float(entry_price) + risk_abs
        take_profit = float(entry_price) - (risk_abs * rr)
    else:
        stop_loss = float(entry_price) - risk_abs
        take_profit = float(entry_price) + (risk_abs * rr)

    plan = {
        "active": True,
        "entry_price": round(float(entry_price), 8),
        "stop_loss": round(float(stop_loss), 8),
        "take_profit": round(float(take_profit), 8),
        "rr_estimate": round(rr, 4),
        "risk_pct": round(risk_pct, 4),
        "max_hold_minutes": int(max(5, settings.AUTO_PICK_REAL_EXIT_PLAN_MAX_HOLD_MINUTES or 240)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return plan, None


def _evaluate_real_execution_pre_dispatch_gate(
    *,
    current_user: User,
    exchange: str,
    symbol: str,
    side: str,
    candidate: Optional[PretradeCheckRequest],
    enforce_exit_plan: bool,
) -> tuple[Optional[str], Optional[str], Optional[dict]]:
    real_guard_reason = _auto_pick_real_guard_reason(
        current_user=current_user,
        exchange=exchange,
        symbol=symbol,
    )
    if real_guard_reason:
        return real_guard_reason, None, None
    exit_plan = None
    plan_reason = None
    if enforce_exit_plan:
        rr_estimate = float(candidate.rr_estimate) if candidate else None
        atr_pct = float(candidate.atr_pct) if candidate else None
        exit_plan, plan_reason = _build_auto_pick_exit_plan(
            exchange=exchange,
            symbol=symbol,
            side=side,
            rr_estimate=rr_estimate,
            atr_pct=atr_pct,
        )
    return None, plan_reason, exit_plan


def _evaluate_semantic_intent_lock_acquire(
    *,
    current_user: User,
    exchange: str,
    symbol: str,
    side: str,
) -> tuple[Optional[str], Optional[int], bool, Optional[Connection]]:
    intent_lock_reason = None
    intent_lock_key = None
    intent_lock_acquired = False
    intent_lock_conn = None

    if not str(settings.DATABASE_URL or "").lower().startswith("postgres"):
        return intent_lock_reason, intent_lock_key, intent_lock_acquired, intent_lock_conn

    lock_key = _semantic_intent_lock_key(
        tenant_id=_tenant_id(current_user),
        user_id=current_user.id,
        exchange=exchange,
        symbol=symbol,
        side=side,
    )
    try:
        intent_lock_conn = engine.connect()
        got_intent_lock = bool(
            intent_lock_conn.execute(
                text("SELECT pg_try_advisory_lock(:k)"),
                {"k": lock_key},
            ).scalar()
        )
    except Exception:
        got_intent_lock = False
    if got_intent_lock:
        intent_lock_key = lock_key
        intent_lock_acquired = True
    else:
        intent_lock_reason = "semantic_intent_lock_contention"
    return intent_lock_reason, intent_lock_key, intent_lock_acquired, intent_lock_conn


def _reserve_auto_pick_pre_dispatch_idempotency(
    *,
    db: Session,
    user_id: str,
    exchange: str,
    symbol: str,
    side: str,
    selected_qty: float,
    idempotency_key: Optional[str],
) -> tuple[Optional[dict], str, dict]:
    idempotency_endpoint = f"/ops/execution/pretrade/{exchange.lower()}/auto-pick"
    idempotency_request_payload = {
        "user_id": user_id,
        "endpoint": idempotency_endpoint,
        "exchange": str(exchange).upper(),
        "symbol": symbol,
        "side": side,
        "selected_qty_normalized": float(selected_qty),
    }
    cached_response = reserve_idempotent_intent(
        db=db,
        user_id=user_id,
        endpoint=idempotency_endpoint,
        idempotency_key=idempotency_key or "",
        request_payload=idempotency_request_payload,
    )
    return cached_response, idempotency_endpoint, idempotency_request_payload


def _finalize_auto_pick_idempotent_intent_best_effort(
    *,
    db: Session,
    user_id: str,
    endpoint: str,
    idempotency_key: Optional[str],
    request_payload: dict,
    response_payload: dict,
    status_code: int,
) -> None:
    try:
        finalize_idempotent_intent(
            db=db,
            user_id=user_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            response_payload=response_payload,
            status_code=status_code,
        )
    except Exception:
        pass


def _run_binance_auto_pick_live_flow(
    *,
    db: Session,
    current_user: User,
    exchange: str,
    payload: PretradeAutoPickRequest,
    idempotency_key: Optional[str],
    selected: dict,
    selected_symbol: str,
    selected_qty: float,
    selected_qty_requested: float,
    selected_qty_sized: float,
    selected_side: str,
    candidate,
    execution_preview: dict,
    liquidity_state: str,
    size_multiplier: float,
    top_candidate_symbol: Optional[str],
    top_candidate: Optional[dict],
    top_candidate_trend_score,
    top_candidate_trend_score_1d,
    top_candidate_trend_score_4h,
    top_candidate_trend_score_1h,
    top_candidate_micro_trend_15m,
    avg_score,
    avg_score_base,
    avg_score_rules,
    avg_score_market,
    scan: dict,
    enforce_exit_plan: bool,
    exit_plan,
    max_spread: float,
    max_slippage: float,
    _finalize,
) -> dict:
    execution = None
    decision = "dry_run_selected_gray" if liquidity_state == "gray" else "dry_run_selected"
    idempotency_reserved = False
    idempotency_finalized = False
    idempotency_endpoint = None
    idempotency_request_payload = None

    cached_response, idempotency_endpoint, idempotency_request_payload = _reserve_auto_pick_pre_dispatch_idempotency(
        db=db,
        user_id=current_user.id,
        exchange=exchange,
        symbol=selected_symbol,
        side=selected_side,
        selected_qty=selected_qty,
        idempotency_key=idempotency_key,
    )
    if cached_response is not None:
        return cached_response
    idempotency_reserved = True

    try:
        execution = execute_binance_test_order_for_user(
            user_id=current_user.id,
            symbol=selected["symbol"],
            side=selected["side"],
            qty=selected_qty,
        )
        decision = "executed_test_order_gray" if liquidity_state == "gray" else "executed_test_order"
        if enforce_exit_plan:
            execution = {**(execution or {}), "exit_plan": exit_plan}
    except HTTPException as exc:
        decision = "insufficient_resources_or_execution_error"
        execution = {"error": str(exc.detail)}
        if idempotency_reserved:
            _finalize_auto_pick_idempotent_intent_best_effort(
                db=db,
                user_id=current_user.id,
                endpoint=idempotency_endpoint,
                idempotency_key=idempotency_key,
                request_payload=idempotency_request_payload,
                response_payload={"decision": decision, "execution": execution},
                status_code=500,
            )
            idempotency_finalized = True

    (
        selected_trend_score,
        selected_trend_score_1d,
        selected_trend_score_4h,
        selected_trend_score_1h,
        selected_micro_trend_15m,
    ) = _resolve_auto_pick_mtf_trend_fields(selected_symbol, candidate, exchange)

    out = _finalize({
        "exchange": exchange,
        "dry_run": bool(payload.dry_run),
        "requested_direction": payload.direction,
        "selected": True,
        "selected_symbol": selected_symbol,
        "selected_side": selected["side"],
        "selected_qty_requested": round(selected_qty_requested, 8),
        "selected_qty_sized": round(selected_qty_sized, 8),
        "selected_qty_normalized": round(float(execution_preview.get("normalized_qty", 0.0)), 8),
        "selected_price_estimate": execution_preview.get("price_estimate"),
        "selected_estimated_notional": execution_preview.get("estimated_notional"),
        "selected_qty_normalization_source": execution_preview.get("normalization_source"),
        "selected_qty": round(selected_qty, 8),
        "selected_score": selected["score"],
        "selected_score_base": selected.get("score_base"),
        "selected_score_rules": selected["score_rules"],
        "selected_score_market": selected["score_market"],
        "selected_learning_prob_hit_pct": selected.get("learning_prob_hit_pct"),
        "selected_learning_samples": selected.get("learning_samples"),
        "selected_learning_score": selected.get("learning_score"),
        "selected_learning_delta_points": selected.get("learning_delta_points"),
        "selected_trend_score": selected_trend_score,
        "selected_trend_score_1d": selected_trend_score_1d,
        "selected_trend_score_4h": selected_trend_score_4h,
        "selected_trend_score_1h": selected_trend_score_1h,
        "selected_micro_trend_15m": selected_micro_trend_15m,
        "selected_market_regime": selected["market_regime"],
        "selected_liquidity_state": liquidity_state,
        "selected_size_multiplier": round(float(size_multiplier), 4),
        "top_candidate_symbol": top_candidate_symbol,
        "top_candidate_score": (top_candidate or {}).get("score"),
        "top_candidate_score_base": (top_candidate or {}).get("score_base"),
        "top_candidate_score_rules": (top_candidate or {}).get("score_rules"),
        "top_candidate_score_market": (top_candidate or {}).get("score_market"),
        "top_candidate_learning_prob_hit_pct": (top_candidate or {}).get("learning_prob_hit_pct"),
        "top_candidate_learning_samples": (top_candidate or {}).get("learning_samples"),
        "top_candidate_learning_score": (top_candidate or {}).get("learning_score"),
        "top_candidate_learning_delta_points": (top_candidate or {}).get("learning_delta_points"),
        "top_candidate_trend_score": top_candidate_trend_score,
        "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
        "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
        "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
        "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
        "avg_score": avg_score,
        "avg_score_base": avg_score_base,
        "avg_score_rules": avg_score_rules,
        "avg_score_market": avg_score_market,
        "decision": decision,
        "top_failed_checks": [],
        "execution": execution,
        "scan": scan,
    }, max_spread=max_spread, max_slippage=max_slippage)

    if idempotency_reserved:
        if not idempotency_finalized:
            # Keep the candidate result path operational; reservation finalization is best-effort.
            _finalize_auto_pick_idempotent_intent_best_effort(
                db=db,
                user_id=current_user.id,
                endpoint=idempotency_endpoint,
                idempotency_key=idempotency_key,
                request_payload=idempotency_request_payload,
                response_payload=out,
                status_code=200,
            )
        out["_idempotency_handled"] = True

    return out


def _evaluate_binance_spot_usdt_broker_guard(
    *,
    user_id: str,
    exchange: str,
    side: str,
    symbol: str,
    execution_preview: dict,
) -> tuple[Optional[str], Optional[float], Optional[float]]:
    guard_exchange = str(exchange or "").upper()
    guard_side = str(side or "").upper()
    guard_market = str(execution_preview.get("market") or "").upper()
    guard_symbol = str(symbol or "").upper()
    is_usdt_spot_symbol = guard_symbol.endswith("USDT") or "/USDT" in guard_symbol
    broker_guard_applies = (
        guard_exchange == "BINANCE"
        and guard_side == "BUY"
        and guard_market == "SPOT"
        and is_usdt_spot_symbol
    )

    if not broker_guard_applies:
        return None, None, None

    try:
        estimated_notional = float(execution_preview.get("estimated_notional") or 0.0)
    except Exception:
        estimated_notional = 0.0

    if estimated_notional <= 0.0:
        return "broker_notional_unavailable", None, None

    broker_guard_required_usdt = estimated_notional * 1.02
    try:
        broker_state = get_binance_spot_usdt_free_for_user(user_id)
    except Exception:
        if not str(settings.DATABASE_URL or "").lower().startswith("postgres"):
            return None, broker_guard_required_usdt, None
        return "broker_status_unavailable", broker_guard_required_usdt, None

    if not bool(broker_state.get("can_trade", True)):
        return "broker_trading_disabled", broker_guard_required_usdt, None

    try:
        broker_guard_usdt_free = float(broker_state.get("usdt_free"))
    except Exception:
        broker_guard_usdt_free = None

    if broker_guard_usdt_free is None or broker_guard_usdt_free < 0.0:
        return "broker_spot_usdt_unavailable", broker_guard_required_usdt, broker_guard_usdt_free
    if broker_guard_usdt_free < float(broker_guard_required_usdt):
        return "broker_spot_usdt_insufficient", broker_guard_required_usdt, broker_guard_usdt_free

    return None, broker_guard_required_usdt, broker_guard_usdt_free


def _binance_fallback_symbols() -> list[str]:
    return [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "ADAUSDT",
        "DOGEUSDT",
        "LTCUSDT",
    ]


def _is_binance_directional_symbol(symbol: str) -> bool:
    s = (symbol or "").upper().strip()
    if not s.endswith("USDT"):
        return False
    banned_suffixes = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")
    if s.endswith(banned_suffixes):
        return False
    non_directional = {
        "USDCUSDT",
        "BUSDUSDT",
        "FDUSDUSDT",
        "TUSDUSDT",
        "EURUSDT",
        "TRYUSDT",
        "BRLUSDT",
        "AUDUSDT",
        "GBPUSDT",
    }
    return s not in non_directional


def _binance_monitor_volume_floor() -> float:
    return 10_000_000.0


def _is_binance_monitor_row_allowed(symbol: str, volume_24h_usdt: float) -> bool:
    return _is_binance_directional_symbol(symbol) and float(volume_24h_usdt or 0.0) >= _binance_monitor_volume_floor()


def _ibkr_fallback_symbols() -> list[str]:
    return [
        "SPY",
        "QQQ",
        "IWM",
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "META",
        "TSLA",
    ]


def _fetch_binance_ticker_rows() -> list[dict]:
    cache_ttl = max(0, int(settings.BINANCE_TICKER_CACHE_SECONDS or 0))
    now_ts = time.time()
    if cache_ttl > 0:
        with _binance_ticker_cache_lock:
            if _binance_ticker_cache_rows and now_ts < _binance_ticker_cache_expiry:
                return list(_binance_ticker_cache_rows)

    def _update_cache(rows: list[dict]) -> list[dict]:
        if cache_ttl <= 0:
            return rows
        with _binance_ticker_cache_lock:
            global _binance_ticker_cache_rows, _binance_ticker_cache_expiry
            _binance_ticker_cache_rows = list(rows)
            _binance_ticker_cache_expiry = time.time() + cache_ttl
        return rows

    max_retries = max(0, int(settings.BINANCE_HTTP_MAX_RETRIES or 0))
    backoff_base = max(0.05, float(settings.BINANCE_HTTP_RETRY_BACKOFF_SECONDS or 0.6))

    def _should_retry_http_error(exc: Exception) -> bool:
        if isinstance(exc, urllib_error.HTTPError):
            code = int(getattr(exc, "code", 0) or 0)
            return code == 429 or code >= 500
        return isinstance(exc, urllib_error.URLError)

    def _run_request(req: urllib_request.Request, timeout: int) -> list[dict]:
        attempts = max_retries + 1
        for attempt in range(attempts):
            try:
                with urllib_request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                    payload = json.loads(resp.read().decode("utf-8"))
                if isinstance(payload, dict):
                    rows = payload.get("rows")
                    if isinstance(rows, list):
                        return [p for p in rows if isinstance(p, dict)]
                if isinstance(payload, list):
                    return [p for p in payload if isinstance(p, dict)]
                return []
            except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
                is_last = attempt >= attempts - 1
                if is_last or not _should_retry_http_error(exc):
                    break
                sleep_s = backoff_base * (2 ** attempt) + random.uniform(0.0, 0.25)
                time.sleep(sleep_s)
        return []

    gateway_enabled = bool(settings.BINANCE_GATEWAY_ENABLED and settings.BINANCE_GATEWAY_BASE_URL)
    if gateway_enabled:
        base = settings.BINANCE_GATEWAY_BASE_URL.rstrip("/")
        url = f"{base}/binance/ticker-24hr"
        body = json.dumps({"limit": 500}).encode("utf-8")
        req = urllib_request.Request(
            url,
            method="POST",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        if settings.BINANCE_GATEWAY_TOKEN:
            req.add_header("X-Internal-Token", settings.BINANCE_GATEWAY_TOKEN)
        rows = _run_request(req, timeout=max(3, int(settings.BINANCE_GATEWAY_TIMEOUT_SECONDS)))
        if rows:
            return _update_cache(rows)
        if not settings.BINANCE_GATEWAY_FALLBACK_DIRECT:
            with _binance_ticker_cache_lock:
                return list(_binance_ticker_cache_rows)

    base = (settings.BINANCE_TESTNET_BASE_URL or "https://testnet.binance.vision").rstrip("/")
    url = f"{base}/api/v3/ticker/24hr"
    req = urllib_request.Request(url, method="GET")
    rows = _run_request(req, timeout=6)
    if rows:
        return _update_cache(rows)
    with _binance_ticker_cache_lock:
        return list(_binance_ticker_cache_rows)


def _fetch_binance_klines(symbol: str, interval: str, limit: int) -> list[list]:
    sym = str(symbol or "").upper().strip()
    iv = str(interval or "1h").strip()
    if not sym:
        return []
    lim = max(30, min(int(limit), 500))
    cache_ttl = max(5, int(settings.BINANCE_MTF_CACHE_SECONDS or 60))
    now_ts = time.time()
    key = (sym, iv)
    with _binance_klines_cache_lock:
        cached = _binance_klines_cache.get(key)
        if cached and now_ts < cached[0]:
            return list(cached[1])

    rows: list[list] = []
    gateway_enabled = bool(settings.BINANCE_GATEWAY_ENABLED and settings.BINANCE_GATEWAY_BASE_URL)
    if gateway_enabled:
        try:
            base = settings.BINANCE_GATEWAY_BASE_URL.rstrip("/")
            url = f"{base}/binance/klines"
            body = json.dumps({"symbol": sym, "interval": iv, "limit": lim}).encode("utf-8")
            req = urllib_request.Request(
                url,
                method="POST",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            if settings.BINANCE_GATEWAY_TOKEN:
                req.add_header("X-Internal-Token", settings.BINANCE_GATEWAY_TOKEN)
            with urllib_request.urlopen(req, timeout=max(3, int(settings.BINANCE_GATEWAY_TIMEOUT_SECONDS))) as resp:  # noqa: S310
                payload = json.loads(resp.read().decode("utf-8"))
            got = payload.get("rows") if isinstance(payload, dict) else None
            if isinstance(got, list):
                rows = [row for row in got if isinstance(row, list) and len(row) >= 6]
        except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError, json.JSONDecodeError):
            if not settings.BINANCE_GATEWAY_FALLBACK_DIRECT:
                return []

    if not rows:
        base = (settings.BINANCE_TESTNET_BASE_URL or "https://testnet.binance.vision").rstrip("/")
        url = f"{base}/api/v3/klines?{urllib_parse.urlencode({'symbol': sym, 'interval': iv, 'limit': lim})}"
        try:
            req = urllib_request.Request(url, method="GET")
            with urllib_request.urlopen(req, timeout=6) as resp:  # noqa: S310
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        rows = [row for row in payload if isinstance(row, list) and len(row) >= 6]

    with _binance_klines_cache_lock:
        _binance_klines_cache[key] = (time.time() + cache_ttl, rows)
    return rows


def _fetch_binance_1h_klines(symbol: str, limit: int | None = None) -> list[list]:
    sym = str(symbol or "").upper().strip()
    if not sym:
        return []
    lim = max(30, min(int(limit or settings.BINANCE_MTF_KLINES_LIMIT or 120), 500))
    return _fetch_binance_klines(sym, "1h", lim)


def _fetch_binance_15m_klines(symbol: str, limit: int = 96) -> list[list]:
    sym = str(symbol or "").upper().strip()
    if not sym:
        return []
    lim = max(30, min(int(limit), 500))
    return _fetch_binance_klines(sym, "15m", lim)


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _norm_return(ret: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return _clip(ret / scale, -1.0, 1.0)


def _compute_binance_mtf_signal(symbol: str) -> dict | None:
    rows = _fetch_binance_1h_klines(symbol=symbol)
    if len(rows) < 30:
        return None
    closes: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    for row in rows:
        try:
            highs.append(float(row[2]))
            lows.append(float(row[3]))
            closes.append(float(row[4]))
        except (TypeError, ValueError):
            return None
    if len(closes) < 30 or closes[-1] <= 0:
        return None

    close_now = closes[-1]
    r_1h = (close_now - closes[-2]) / closes[-2] if closes[-2] > 0 else 0.0
    r_4h = (close_now - closes[-5]) / closes[-5] if closes[-5] > 0 else 0.0
    r_1d = (close_now - closes[-25]) / closes[-25] if closes[-25] > 0 else 0.0
    r_6h = (close_now - closes[-7]) / closes[-7] if closes[-7] > 0 else 0.0

    trend_score = (
        0.55 * _norm_return(r_1d, 0.03)
        + 0.30 * _norm_return(r_4h, 0.02)
        + 0.15 * _norm_return(r_1h, 0.01)
    )
    momentum_score = (
        0.60 * _norm_return(r_1h, 0.01)
        + 0.40 * _norm_return(r_6h, 0.015)
    )

    start_idx = max(1, len(closes) - 24)
    trs: list[float] = []
    for i in range(start_idx, len(closes)):
        prev_close = closes[i - 1]
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - prev_close),
            abs(lows[i] - prev_close),
        )
        trs.append(max(0.0, tr))
    atr = sum(trs) / len(trs) if trs else 0.0
    atr_pct = (atr / close_now) * 100.0 if close_now > 0 else 0.0

    micro_15m = None
    rows_15m = _fetch_binance_15m_klines(symbol=symbol, limit=96)
    if len(rows_15m) >= 7:
        closes_15m: list[float] = []
        for row in rows_15m:
            try:
                closes_15m.append(float(row[4]))
            except (TypeError, ValueError):
                closes_15m = []
                break
        if len(closes_15m) >= 7 and closes_15m[-1] > 0:
            c_now = closes_15m[-1]
            r15_1 = (c_now - closes_15m[-2]) / closes_15m[-2] if closes_15m[-2] > 0 else 0.0
            r15_3 = (c_now - closes_15m[-4]) / closes_15m[-4] if closes_15m[-4] > 0 else 0.0
            r15_6 = (c_now - closes_15m[-7]) / closes_15m[-7] if closes_15m[-7] > 0 else 0.0
            micro_raw = (0.5 * r15_6) + (0.3 * r15_3) + (0.2 * r15_1)
            micro_15m = round(_clip(micro_raw / 0.012, -1.0, 1.0), 4)

    return {
        "trend_score": round(_clip(trend_score, -1.0, 1.0), 4),
        "momentum_score": round(_clip(momentum_score, -1.0, 1.0), 4),
        "atr_pct": round(max(0.0, atr_pct), 4),
        "trend_1d": round(r_1d, 6),
        "trend_4h": round(r_4h, 6),
        "trend_1h": round(r_1h, 6),
        "micro_trend_15m": micro_15m,
        "source": "klines_1h_mtf",
    }


def _fetch_binance_auto_universe(limit: int = 12) -> list[str]:
    payload = _fetch_binance_ticker_rows()
    rows: list[tuple[str, float]] = []
    for item in payload:
        symbol = str(item.get("symbol") or "").upper().strip()
        if not _is_binance_directional_symbol(symbol):
            continue
        try:
            vol = float(item.get("quoteVolume") or 0.0)
        except (TypeError, ValueError):
            vol = 0.0
        if vol < _binance_monitor_volume_floor():
            continue
        rows.append((symbol, vol))
    rows.sort(key=lambda x: x[1], reverse=True)
    out: list[str] = []
    seen: set[str] = set()
    for symbol, _ in rows:
        if symbol in seen:
            continue
        seen.add(symbol)
        out.append(symbol)
        if len(out) >= limit:
            break
    return out


def _build_auto_pick_universe(
    exchange: str,
    *,
    db: Session | None = None,
    tenant_id: str | None = None,
    direction: str = "LONG",
) -> list[PretradeCheckRequest]:
    ex = (exchange or "").upper()
    pick_direction = (direction or "LONG").upper().strip()

    def _sides_for_direction() -> list[str]:
        if pick_direction == "LONG":
            return ["BUY"]
        if pick_direction == "SHORT":
            return ["SELL"]
        # BOTH
        return ["BUY", "SELL"]

    sides = _sides_for_direction()
    if not sides:
        return []

    if ex == "IBKR":
        symbols = _ibkr_fallback_symbols()
        base_by_symbol = {
            "SPY": (0.20, 0.12, 1.8, 6.0, 8.0),
            "QQQ": (0.25, 0.15, 2.0, 7.0, 9.0),
            "IWM": (0.08, 0.05, 2.4, 8.0, 10.0),
            "AAPL": (0.22, 0.18, 2.1, 7.0, 9.0),
            "MSFT": (0.18, 0.14, 1.9, 6.0, 8.0),
            "NVDA": (0.35, 0.30, 3.2, 9.0, 12.0),
            "AMZN": (0.15, 0.10, 2.3, 7.0, 9.0),
            "META": (0.17, 0.12, 2.5, 8.0, 10.0),
            "TSLA": (0.28, 0.22, 3.8, 10.0, 13.0),
        }
        out_ibkr: list[PretradeCheckRequest] = []
        for s in symbols:
            for side in sides:
                out_ibkr.append(
                    PretradeCheckRequest(
                        symbol=s,
                        side=side,
                        qty=1.0,
                        rr_estimate=1.6,
                        trend_tf="4H",
                        signal_tf="1H",
                        timing_tf="15M",
                        spread_bps=base_by_symbol.get(s, (0.0, 0.0, 2.2, 8.0, 10.0))[3],
                        slippage_bps=base_by_symbol.get(s, (0.0, 0.0, 2.2, 8.0, 10.0))[4],
                        volume_24h_usdt=0.0,
                        in_rth=True,
                        macro_event_block=False,
                        earnings_within_24h=False,
                        market_trend_score=base_by_symbol.get(s, (0.0, 0.0, 2.2, 8.0, 10.0))[0],
                        atr_pct=base_by_symbol.get(s, (0.0, 0.0, 2.2, 8.0, 10.0))[2],
                        momentum_score=base_by_symbol.get(s, (0.0, 0.0, 2.2, 8.0, 10.0))[1],
                    )
                )
        return out_ibkr
    # Prefer the latest market-monitor bucket so auto-pick uses the same filtered universe.
    if db is not None and tenant_id:
        latest_bucket = db.execute(
            select(func.max(MarketTrendSnapshot.bucket_5m)).where(
                MarketTrendSnapshot.tenant_id == tenant_id,
                MarketTrendSnapshot.exchange == "BINANCE",
            )
        ).scalar_one_or_none()
        if latest_bucket is not None:
            snap_rows = db.execute(
                select(MarketTrendSnapshot).where(
                    MarketTrendSnapshot.tenant_id == tenant_id,
                    MarketTrendSnapshot.exchange == "BINANCE",
                    MarketTrendSnapshot.bucket_5m == latest_bucket,
                )
            ).scalars().all()
            ranked_snapshots = sorted(
                [
                    r for r in snap_rows
                    if _is_binance_monitor_row_allowed(str(r.symbol or ""), float(r.volume_24h_usdt or 0.0))
                ],
                key=lambda r: float(r.volume_24h_usdt or 0.0),
                reverse=True,
            )[:12]
            if ranked_snapshots:
                out: list[PretradeCheckRequest] = []
                for r in ranked_snapshots:
                    qv = float(r.volume_24h_usdt or 0.0)
                    liq = min(1.0, qv / 200_000_000.0)
                    spread = max(3.0, 14.0 - (10.0 * liq))
                    slippage = max(5.0, 18.0 - (12.0 * liq))
                    for side in sides:
                        out.append(
                            PretradeCheckRequest(
                                symbol=str(r.symbol),
                                side=side,
                                qty=0.01,
                                rr_estimate=1.7,
                                trend_tf="4H",
                                signal_tf="1H",
                                timing_tf="15M",
                                spread_bps=round(spread, 2),
                                slippage_bps=round(slippage, 2),
                                volume_24h_usdt=qv,
                                market_trend_score=round(float(r.trend_score or 0.0), 3),
                                market_trend_score_1d=None,
                                market_trend_score_4h=None,
                                market_trend_score_1h=None,
                                market_micro_trend_15m=None,
                                atr_pct=round(float(r.atr_pct or 0.0), 3),
                                momentum_score=round(float(r.momentum_score or 0.0), 3),
                                funding_rate_bps=0.0,
                                crypto_event_block=False,
                            )
                        )
                return out

    ticker_rows = _fetch_binance_ticker_rows()
    if ticker_rows:
        ranked: list[tuple[dict, float]] = []
        for item in ticker_rows:
            symbol = str(item.get("symbol") or "").upper().strip()
            if not _is_binance_directional_symbol(symbol):
                continue
            try:
                qv = float(item.get("quoteVolume") or 0.0)
                pct = float(item.get("priceChangePercent") or 0.0)
                high = float(item.get("highPrice") or 0.0)
                low = float(item.get("lowPrice") or 0.0)
                last = float(item.get("lastPrice") or 0.0)
            except (TypeError, ValueError):
                continue
            if last <= 0:
                continue
            if qv < _binance_monitor_volume_floor():
                continue
            ranked.append(({
                "symbol": symbol,
                "quote_volume": qv,
                "pct": pct,
                "high": high,
                "low": low,
                "last": last,
            }, qv))
        ranked.sort(key=lambda x: x[1], reverse=True)
        selected = [r[0] for r in ranked[:12]]
        out: list[PretradeCheckRequest] = []
        for row in selected:
            qv = float(row["quote_volume"])
            pct = float(row.get("pct") or 0.0)
            mtf = _compute_binance_mtf_signal(str(row["symbol"]))
            if mtf is not None:
                trend = float(mtf.get("trend_score") or 0.0)
                momentum = float(mtf.get("momentum_score") or 0.0)
                vol = float(mtf.get("atr_pct") or 0.0)
            else:
                last = float(row.get("last") or 0.0)
                high = float(row.get("high") or 0.0)
                low = float(row.get("low") or 0.0)
                vol = ((high - low) / last) * 100.0 if high > 0 and low > 0 and last > 0 else 0.0
                trend = max(-1.0, min(1.0, pct / 8.0))
                momentum = max(-1.0, min(1.0, pct / 6.0))
            liq = min(1.0, qv / 200_000_000.0)
            spread = max(3.0, 14.0 - (10.0 * liq))
            slippage = max(5.0, 18.0 - (12.0 * liq))
            for side in sides:
                out.append(
                    PretradeCheckRequest(
                        symbol=str(row["symbol"]),
                        side=side,
                        qty=0.01,
                        rr_estimate=1.7,
                        trend_tf="4H",
                        signal_tf="1H",
                        timing_tf="15M",
                        spread_bps=round(spread, 2),
                        slippage_bps=round(slippage, 2),
                        volume_24h_usdt=qv,
                        market_trend_score=round(trend, 3),
                        market_trend_score_1d=round(float(mtf.get("trend_1d")) if mtf is not None and mtf.get("trend_1d") is not None else trend, 6),
                        market_trend_score_4h=round(float(mtf.get("trend_4h")) if mtf is not None and mtf.get("trend_4h") is not None else trend, 6),
                        market_trend_score_1h=round(float(mtf.get("trend_1h")) if mtf is not None and mtf.get("trend_1h") is not None else trend, 6),
                        market_micro_trend_15m=(
                            round(float(mtf.get("micro_trend_15m")), 6)
                            if mtf is not None and mtf.get("micro_trend_15m") is not None
                            else None
                        ),
                        atr_pct=round(vol, 3),
                        momentum_score=round(momentum, 3),
                        funding_rate_bps=0.0,
                        crypto_event_block=False,
                    )
                )
        if out:
            return out
    return [
        PretradeCheckRequest(
            symbol=s,
            side=side,
            qty=0.01,
            rr_estimate=1.7,
            trend_tf="4H",
            signal_tf="1H",
            timing_tf="15M",
            spread_bps=7.0,
            slippage_bps=10.0,
            volume_24h_usdt=90_000_000.0,
            market_trend_score=0.0,
            market_trend_score_1d=None,
            market_trend_score_4h=None,
            market_trend_score_1h=None,
            market_micro_trend_15m=None,
            atr_pct=0.0,
            momentum_score=0.0,
            funding_rate_bps=0.0,
            crypto_event_block=False,
        )
        for side in sides
        for s in _binance_fallback_symbols()
    ]


def _bucket_5m(dt: datetime) -> datetime:
    d = dt.astimezone(timezone.utc)
    minute_bucket = (d.minute // 5) * 5
    return d.replace(minute=minute_bucket, second=0, microsecond=0)


def _market_confidence_pct(*, trend_score: float, momentum_score: float, atr_pct: float, regime: str) -> float:
    trend_strength = min(1.0, max(0.0, abs(float(trend_score))))
    momentum_strength = min(1.0, max(0.0, abs(float(momentum_score))))
    atr_norm = min(1.0, max(0.0, float(atr_pct) / 12.0))
    volatility_fit = 1.0 - abs(atr_norm - 0.35)
    volatility_fit = min(1.0, max(0.0, volatility_fit))
    raw = (trend_strength * 0.45) + (momentum_strength * 0.35) + (volatility_fit * 0.20)
    if (regime or "").lower() == "range":
        raw *= 0.9
    return round(min(100.0, max(0.0, raw * 100.0)), 2)


def _build_market_monitor_rows(exchange: str) -> list[dict]:
    ex = (exchange or "").upper()
    if ex == "BINANCE":
        ticker_rows = _fetch_binance_ticker_rows()
        if ticker_rows:
            ranked_by_volume: list[tuple[dict, float]] = []
            for item in ticker_rows:
                symbol = str(item.get("symbol") or "").upper().strip()
                if not _is_binance_directional_symbol(symbol):
                    continue
                try:
                    qv = float(item.get("quoteVolume") or 0.0)
                    pct = float(item.get("priceChangePercent") or 0.0)
                    high = float(item.get("highPrice") or 0.0)
                    low = float(item.get("lowPrice") or 0.0)
                    last = float(item.get("lastPrice") or 0.0)
                except (TypeError, ValueError):
                    continue
                if last <= 0:
                    continue
                if qv < _binance_monitor_volume_floor():
                    continue
                ranked_by_volume.append(
                    (
                        {
                            "symbol": symbol,
                            "pct": pct,
                            "high": high,
                            "low": low,
                            "last": last,
                            "volume_24h_usdt": round(max(0.0, qv), 2),
                        },
                        qv,
                    )
                )
            ranked_by_volume.sort(key=lambda x: x[1], reverse=True)
            out: list[dict] = []
            # Compute MTF only on the most liquid symbols to keep calls bounded.
            for base_row, qv in ranked_by_volume[:20]:
                symbol = str(base_row["symbol"])
                mtf = _compute_binance_mtf_signal(symbol)
                if mtf is None:
                    volatility = ((float(base_row["high"]) - float(base_row["low"])) / float(base_row["last"])) * 100.0 if float(base_row["last"]) > 0 else 0.0
                    trend = max(-1.0, min(1.0, float(base_row["pct"]) / 8.0))
                    momentum = max(-1.0, min(1.0, float(base_row["pct"]) / 6.0))
                    mtf = {
                        "trend_score": round(trend, 4),
                        "momentum_score": round(momentum, 4),
                        "atr_pct": round(max(0.0, volatility), 4),
                        "source": "ticker_24h_fallback",
                    }
                regime, _ = infer_market_regime(
                    trend_score=float(mtf.get("trend_score") or 0.0),
                    atr_pct=float(mtf.get("atr_pct") or 0.0),
                    momentum_score=float(mtf.get("momentum_score") or 0.0),
                )
                out.append(
                    {
                        "exchange": "BINANCE",
                        "symbol": symbol,
                        "trend_score": float(mtf.get("trend_score") or 0.0),
                        "momentum_score": float(mtf.get("momentum_score") or 0.0),
                        "atr_pct": float(mtf.get("atr_pct") or 0.0),
                        "volume_24h_usdt": round(max(0.0, qv), 2),
                        "regime": regime,
                        "source": str(mtf.get("source") or "ticker_24h_fallback"),
                    }
                )
            out = out[:12]
            if out:
                return out
        return [
            {
                "exchange": "BINANCE",
                "symbol": s,
                "trend_score": 0.0,
                "momentum_score": 0.0,
                "atr_pct": 6.5,
                "volume_24h_usdt": 0.0,
                "regime": "range",
                "source": "fallback",
            }
            for s in _binance_fallback_symbols()
        ]

    base_by_symbol = {
        "SPY": (0.20, 0.12, 1.8),
        "QQQ": (0.25, 0.15, 2.0),
        "IWM": (0.08, 0.05, 2.4),
        "AAPL": (0.22, 0.18, 2.1),
        "MSFT": (0.18, 0.14, 1.9),
        "NVDA": (0.35, 0.30, 3.2),
        "AMZN": (0.15, 0.10, 2.3),
        "META": (0.17, 0.12, 2.5),
        "TSLA": (0.28, 0.22, 3.8),
    }
    out: list[dict] = []
    for s in _ibkr_fallback_symbols():
        trend, momentum, atr = base_by_symbol.get(s, (0.0, 0.0, 2.2))
        regime, _ = infer_market_regime(
            trend_score=float(trend),
            atr_pct=float(atr),
            momentum_score=float(momentum),
        )
        out.append(
            {
                "exchange": "IBKR",
                "symbol": s,
                "trend_score": round(trend, 4),
                "momentum_score": round(momentum, 4),
                "atr_pct": round(atr, 4),
                "volume_24h_usdt": 0.0,
                "regime": regime,
                "source": "equity_fallback",
            }
        )
    return out


def run_market_monitor_tick_for_tenant(
    db: Session,
    tenant_id: str,
    *,
    exchanges: tuple[str, ...] = ("BINANCE", "IBKR"),
) -> dict:
    now = datetime.now(timezone.utc)
    bucket = _bucket_5m(now)
    inserted = 0
    detail: list[dict] = []
    for exchange in exchanges:
        ex = (exchange or "").upper()
        rows = _build_market_monitor_rows(ex)
        db.query(MarketTrendSnapshot).filter(
            MarketTrendSnapshot.tenant_id == tenant_id,
            MarketTrendSnapshot.exchange == ex,
            MarketTrendSnapshot.bucket_5m == bucket,
        ).delete(synchronize_session=False)
        for row in rows:
            confidence = _market_confidence_pct(
                trend_score=float(row.get("trend_score") or 0.0),
                momentum_score=float(row.get("momentum_score") or 0.0),
                atr_pct=float(row.get("atr_pct") or 0.0),
                regime=str(row.get("regime") or "range"),
            )
            db.add(
                MarketTrendSnapshot(
                    tenant_id=tenant_id,
                    exchange=ex,
                    symbol=str(row.get("symbol") or ""),
                    regime=str(row.get("regime") or "range"),
                    confidence=confidence,
                    trend_score=float(row.get("trend_score") or 0.0),
                    momentum_score=float(row.get("momentum_score") or 0.0),
                    atr_pct=float(row.get("atr_pct") or 0.0),
                    volume_24h_usdt=float(row.get("volume_24h_usdt") or 0.0),
                    source=str(row.get("source") or "fallback"),
                    bucket_5m=bucket,
                )
            )
            inserted += 1
        detail_row = {"exchange": ex, "symbols": len(rows)}
        if ex == "BINANCE" and len(rows) < 3:
            detail_row["warning"] = "low_universe_count_below_3"
            print(  # noqa: T201
                "[market-monitor] alert",
                {"tenant_id": tenant_id, "exchange": ex, "symbols": len(rows), "bucket_5m": bucket.isoformat()},
            )
        detail.append(detail_row)
    db.commit()
    return {
        "tenant_id": tenant_id,
        "bucket_5m": bucket.isoformat(),
        "inserted": inserted,
        "detail": detail,
    }


def _build_operational_readiness_report(
    db: Session,
    *,
    tenant_id: str,
    real_only: bool,
    include_service_users: bool,
) -> dict:
    users = db.execute(
        select(User)
        .where(User.tenant_id == tenant_id)
        .order_by(User.email.asc())
    ).scalars().all()
    return build_readiness_report(
        db,
        users=users,
        real_only=real_only,
        include_service_users=include_service_users,
    )


def _build_security_posture_rows(
    db: Session,
    *,
    tenant_id: Optional[str],
    real_only: bool,
    max_secret_age_days: int,
):
    now = datetime.now(timezone.utc)
    users_q = select(User).order_by(User.email.asc())
    if tenant_id:
        users_q = users_q.where(User.tenant_id == tenant_id)
    users = db.execute(users_q).scalars().all()
    posture_rows: list[SecurityPostureUserOut] = []
    missing_2fa = 0
    stale_secrets = 0

    for user in users:
        if real_only and not _is_real_user_email(user.email):
            continue

        user_2fa = (
            db.execute(
                select(UserTwoFactor).where(UserTwoFactor.user_id == user.id)
            )
            .scalar_one_or_none()
        )
        two_factor_enabled = bool(user_2fa and user_2fa.enabled)

        secret_rows = db.execute(
            select(ExchangeSecret.exchange, ExchangeSecret.updated_at).where(
                ExchangeSecret.user_id == user.id
            )
        ).all()
        configured_exchanges = {row[0] for row in secret_rows}

        oldest_days: Optional[int] = None
        for _, updated_at in secret_rows:
            if updated_at is None:
                continue
            ts = updated_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_days = max(0, int((now - ts.astimezone(timezone.utc)).total_seconds() // 86400))
            if oldest_days is None or age_days > oldest_days:
                oldest_days = age_days

        stale = oldest_days is not None and oldest_days > max_secret_age_days
        if stale:
            stale_secrets += 1

        if user.role in {"admin", "operator", "viewer", "trader"} and not two_factor_enabled:
            missing_2fa += 1

        posture_rows.append(
            SecurityPostureUserOut(
                user_id=user.id,
                email=user.email,
                role=user.role,
                two_factor_enabled=two_factor_enabled,
                binance_secret_configured="BINANCE" in configured_exchanges,
                ibkr_secret_configured="IBKR" in configured_exchanges,
                oldest_secret_age_days=oldest_days,
                stale_secret=stale,
            )
        )

    return now, posture_rows, missing_2fa, stale_secrets


def _assert_exchange_enabled(
    db: Session,
    current_user: User,
    exchange: str,
):
    if is_exchange_enabled_for_user(
        db=db,
        user_id=current_user.id,
        exchange=exchange,
    ):
        return

    log_audit_event(
        db,
        action="execution.blocked.exchange_disabled",
        user_id=current_user.id,
        entity_type="execution",
        details={"exchange": exchange},
    )
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Exchange {exchange} is disabled for this user",
    )


def _evaluate_pretrade_for_user(
    db: Session,
    current_user: User,
    exchange: str,
    payload: PretradeCheckRequest,
    log_event: bool = True,
):
    strategy = resolve_strategy_for_user_exchange(
        db=db,
        user_id=current_user.id,
        exchange=exchange,
    )
    profile = resolve_risk_profile(db, current_user.id, current_user.email)
    today = today_colombia()
    checks = []

    checks.append(
        {
            "name": "strategy_enabled",
            "passed": bool(strategy["enabled"]),
            "detail": f"{strategy['strategy_id']} ({strategy['source']})",
        }
    )

    has_secret = (
        db.execute(
            select(ExchangeSecret).where(
                ExchangeSecret.user_id == current_user.id,
                ExchangeSecret.exchange == exchange,
            )
        )
        .scalar_one_or_none()
        is not None
    )
    checks.append(
        {
            "name": "exchange_secret_configured",
            "passed": has_secret,
            "detail": exchange,
        }
    )

    dr = (
        db.execute(
            select(DailyRiskState).where(
                DailyRiskState.user_id == current_user.id,
                DailyRiskState.day == today,
            )
        )
        .scalar_one_or_none()
    )
    max_trades = int(profile["max_trades_per_day"])
    daily_stop = -abs(float(profile["max_daily_loss_pct"]))
    trades_today = int(dr.trades_today) if dr else 0
    realized_pnl_today = float(dr.realized_pnl_today) if dr else 0.0

    checks.append(
        {
            "name": "daily_stop_not_reached",
            "passed": realized_pnl_today > daily_stop,
            "detail": f"pnl={realized_pnl_today} threshold={daily_stop}",
        }
    )
    checks.append(
        {
            "name": "max_trades_not_reached",
            "passed": trades_today < max_trades,
            "detail": f"trades={trades_today}/{max_trades}",
        }
    )

    max_open_positions = int(profile["max_open_positions"])
    open_positions = db.execute(
        select(func.count())
        .select_from(Position)
        .where(
            Position.user_id == current_user.id,
            Position.status == "OPEN",
        )
    ).scalar_one()
    checks.append(
        {
            "name": "max_open_positions_not_reached",
            "passed": int(open_positions) < max_open_positions,
            "detail": f"open={open_positions}/{max_open_positions}",
        }
    )

    cooldown_minutes = float(profile["cooldown_between_trades_minutes"])
    last_trade_at = db.execute(
        select(func.max(func.coalesce(Position.closed_at, Position.opened_at))).where(
            Position.user_id == current_user.id
        )
    ).scalar_one_or_none()
    cooldown_passed = True
    cooldown_detail = "no previous trade"
    if last_trade_at:
        if last_trade_at.tzinfo is None:
            last_trade_at = last_trade_at.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - last_trade_at.astimezone(timezone.utc)).total_seconds() / 60.0
        cooldown_passed = elapsed >= cooldown_minutes
        cooldown_detail = f"elapsed={round(elapsed,2)}m required={cooldown_minutes}m"
    checks.append(
        {
            "name": "cooldown_passed",
            "passed": cooldown_passed,
            "detail": cooldown_detail,
        }
    )

    strategy_id = strategy["strategy_id"]
    market_regime, regime_source = infer_market_regime(
        trend_score=float(payload.market_trend_score),
        atr_pct=float(payload.atr_pct),
        momentum_score=float(payload.momentum_score),
    )
    runtime_policy = resolve_runtime_policy(
        db=db,
        strategy_id=strategy_id,
        exchange=exchange,
    )
    strategy_checks = _build_strategy_checks(
        exchange=exchange,
        strategy_id=strategy_id,
        payload=payload,
        market_regime=market_regime,
        runtime_policy=runtime_policy,
        profile=profile,
    )
    checks.extend(strategy_checks)

    passed = all(bool(c["passed"]) for c in checks)
    if log_event:
        action = "pretrade.check.passed" if passed else "pretrade.check.blocked"
        log_audit_event(
            db,
            action=action,
            user_id=current_user.id,
            entity_type="pretrade",
            details={
                "exchange": exchange,
                "strategy_id": strategy_id,
                "strategy_source": strategy["source"],
                "request": {
                    "symbol": payload.symbol,
                    "side": payload.side,
                    "qty": payload.qty,
                    "rr_estimate": payload.rr_estimate,
                    "trend_tf": payload.trend_tf,
                    "signal_tf": payload.signal_tf,
                    "timing_tf": payload.timing_tf,
                    "market_session": payload.market_session,
                    "market_trend_score": payload.market_trend_score,
                    "atr_pct": payload.atr_pct,
                    "momentum_score": payload.momentum_score,
                    "leverage": payload.leverage,
                    "funding_rate_bps": payload.funding_rate_bps,
                },
                "market_regime": market_regime,
                "regime_source": regime_source,
                "checks": checks,
            },
        )
        db.commit()

    return {
        "passed": passed,
        "exchange": exchange,
        "strategy_id": strategy_id,
        "strategy_source": strategy["source"],
        "risk_profile": profile["profile_name"],
        "market_regime": market_regime,
        "regime_source": regime_source,
        "checks": checks,
    }


def _pretrade_scores(
    result: dict,
    payload: PretradeCheckRequest,
    *,
    score_weight_rules: float = 0.4,
    score_weight_market: float = 0.6,
) -> tuple[float, float, float]:
    checks = result.get("checks", [])
    total = max(1, len(checks))
    passed_count = sum(1 for c in checks if bool(c.get("passed")))
    ratio = passed_count / total
    score_rules = ratio * 100.0

    trend_raw = max(-1.0, min(1.0, float(payload.market_trend_score)))
    momentum_raw = max(-1.0, min(1.0, float(payload.momentum_score)))
    micro_raw = payload.market_micro_trend_15m
    micro_raw = 0.0 if micro_raw is None else max(-1.0, min(1.0, float(micro_raw)))
    side = str(payload.side or "BUY").upper()
    # For SHORT candidates, negative trend/momentum should increase score.
    trend = trend_raw if side == "BUY" else (-trend_raw)
    momentum = momentum_raw if side == "BUY" else (-momentum_raw)
    micro = micro_raw if side == "BUY" else (-micro_raw)
    rr = max(0.0, min(3.0, float(payload.rr_estimate)))
    spread = max(0.0, float(payload.spread_bps))
    slippage = max(0.0, float(payload.slippage_bps))
    atr_pct = max(0.0, float(payload.atr_pct))
    vol_24h = max(0.0, float(payload.volume_24h_usdt))
    liq = min(1.0, vol_24h / 200_000_000.0)
    atr_penalty = max(0.0, atr_pct - 6.0) * 1.5

    score_market = 45.0
    score_market += trend * 16.0
    score_market += momentum * 14.0
    # Micro trend is confirmation only; dampen impact in noisy volatility.
    micro_mult = 0.6 if atr_pct > 6.0 else 1.0
    score_market += micro * 4.0 * micro_mult
    score_market += rr * 7.0
    score_market += liq * 10.0
    score_market -= spread * 0.6
    score_market -= slippage * 0.55
    score_market -= atr_penalty
    score_market = max(0.0, min(100.0, score_market))

    w_rules = max(0.0, float(score_weight_rules))
    w_market = max(0.0, float(score_weight_market))
    denom = max(0.0001, w_rules + w_market)
    score_final = ((w_rules * score_rules) + (w_market * score_market)) / denom
    score_final = max(0.0, min(100.0, score_final))
    return round(score_rules, 2), round(score_market, 2), round(score_final, 2)


def _learning_advice_for_asset(
    *,
    db: Session,
    tenant_id: str,
    exchange: str,
    symbol: str,
    horizon_minutes: int,
) -> dict:
    lookback_hours = max(1, int(settings.LEARNING_DECISION_LOOKBACK_HOURS or 720))
    min_samples = max(1, int(settings.LEARNING_DECISION_MIN_SAMPLES or 30))
    from_dt = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    rows = db.execute(
        select(LearningRollupHourly)
        .where(
            LearningRollupHourly.tenant_id == tenant_id,
            LearningRollupHourly.exchange == str(exchange or "").upper(),
            LearningRollupHourly.symbol == str(symbol or "").upper(),
            LearningRollupHourly.horizon_minutes == int(horizon_minutes),
            LearningRollupHourly.bucket_hour >= from_dt,
        )
        .order_by(LearningRollupHourly.bucket_hour.desc())
        .limit(200)
    ).scalars().all()
    if not rows:
        return {
            "prob_hit_pct": None,
            "samples": 0,
            "learning_score": None,
            "enabled": False,
            "reason": "no_history",
        }
    samples = int(sum(int(r.samples or 0) for r in rows))
    if samples < min_samples:
        return {
            "prob_hit_pct": None,
            "samples": samples,
            "learning_score": None,
            "enabled": False,
            "reason": "insufficient_samples",
        }
    weighted_hit = sum(float(r.hit_rate_pct or 0.0) * int(r.samples or 0) for r in rows) / max(1, samples)
    weighted_ret = sum(float(r.avg_return_pct or 0.0) * int(r.samples or 0) for r in rows) / max(1, samples)
    ret_component = max(0.0, min(100.0, 50.0 + (weighted_ret * 10.0)))
    learning_score = (0.75 * weighted_hit) + (0.25 * ret_component)
    return {
        "prob_hit_pct": round(float(weighted_hit), 2),
        "samples": samples,
        "learning_score": round(float(learning_score), 2),
        "enabled": True,
        "reason": "ok",
    }


def _blend_learning_score(score_base: float, learning_score: Optional[float]) -> tuple[float, float]:
    base = max(0.0, min(100.0, float(score_base)))
    if learning_score is None:
        return round(base, 2), 0.0
    rules_w = max(0.0, float(settings.LEARNING_DECISION_RULES_WEIGHT or 0.9))
    model_w = max(0.0, float(settings.LEARNING_DECISION_MODEL_WEIGHT or 0.1))
    denom = max(0.0001, rules_w + model_w)
    raw_blend = ((rules_w * base) + (model_w * float(learning_score))) / denom
    raw_delta = raw_blend - base
    max_delta = max(0.0, float(settings.LEARNING_DECISION_MAX_DELTA_POINTS or 6.0))
    delta = max(-max_delta, min(max_delta, raw_delta))
    final = max(0.0, min(100.0, base + delta))
    return round(final, 2), round(delta, 2)


def _classify_liquidity_state(
    *,
    spread_bps: float,
    slippage_bps: float,
    max_spread_bps: float,
    max_slippage_bps: float,
    selected_score: float,
    min_score_pct: float,
) -> tuple[str, float]:
    # Green: strong margin vs limits and score comfortably above threshold.
    green = (
        spread_bps <= (0.80 * max_spread_bps)
        and slippage_bps <= (0.80 * max_slippage_bps)
        and selected_score >= (min_score_pct + 2.0)
    )
    if green:
        return "green", 1.0
    # Gray: still tradable but with tighter edge; reduce size.
    gray = (
        spread_bps <= max_spread_bps
        and slippage_bps <= max_slippage_bps
        and selected_score >= min_score_pct
    )
    if gray:
        return "gray", 0.5
    return "red", 0.0


def _partition_ym(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m")


def _bucket_1h(dt: datetime) -> datetime:
    d = dt.astimezone(timezone.utc)
    return d.replace(minute=0, second=0, microsecond=0)


def _to_utc_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    d = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat()


def _safe_json(value) -> str:
    try:
        return json.dumps(value, ensure_ascii=True)
    except Exception:
        return "[]"


def _fetch_binance_price_map(symbols: list[str]) -> dict[str, float]:
    wanted = {str(s or "").upper().strip() for s in symbols if str(s or "").strip()}
    if not wanted:
        return {}
    out: dict[str, float] = {}
    for item in _fetch_binance_ticker_rows():
        symbol = str(item.get("symbol") or "").upper().strip()
        if symbol not in wanted:
            continue
        try:
            px = float(item.get("lastPrice") or 0.0)
        except (TypeError, ValueError):
            px = 0.0
        if px > 0:
            out[symbol] = px
    return out


def _position_direction_to_exit_check_side(position_side: str) -> str:
    s = str(position_side or "").upper().strip()
    if s in {"SHORT", "SELL"}:
        return "SELL"
    return "BUY"


def _position_realized_pnl(side: str, entry_price: float, exit_price: float, qty: float, fees: float = 0.0) -> float:
    side_u = _position_direction_to_exit_check_side(side)
    sign = -1.0 if side_u == "SELL" else 1.0
    return (sign * (float(exit_price) - float(entry_price)) * float(qty)) - float(fees)


def _latest_market_snapshot_for_symbol(
    *,
    db: Session,
    tenant_id: str,
    exchange: str,
    symbol: str,
) -> Optional[MarketTrendSnapshot]:
    return db.execute(
        select(MarketTrendSnapshot)
        .where(
            MarketTrendSnapshot.tenant_id == tenant_id,
            MarketTrendSnapshot.exchange == str(exchange).upper(),
            MarketTrendSnapshot.symbol == str(symbol).upper(),
        )
        .order_by(MarketTrendSnapshot.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _close_position_internal(
    *,
    db: Session,
    user: User,
    position: Position,
    exit_price: float,
    fees: float,
    reason: str,
    checks: list[dict],
) -> float:
    realized_pnl = _position_realized_pnl(
        side=str(position.side),
        entry_price=float(position.entry_price),
        exit_price=float(exit_price),
        qty=float(position.qty),
        fees=float(fees),
    )
    position.fees = float(fees)
    position.realized_pnl = float(realized_pnl)
    position.status = "CLOSED"
    position.closed_at = datetime.now(timezone.utc)

    sig = db.execute(select(Signal).where(Signal.id == position.signal_id)).scalar_one_or_none()
    if sig:
        sig.status = "COMPLETED"

    today = today_colombia()
    dr = (
        db.execute(
            select(DailyRiskState).where(
                DailyRiskState.user_id == user.id,
                DailyRiskState.day == today,
            )
        )
        .scalar_one_or_none()
    )
    if not dr:
        dr = DailyRiskState(user_id=user.id, day=today)
        db.add(dr)
        db.flush()
    profile = resolve_risk_profile(db, user.id, user.email)
    apply_profile_daily_limits(dr, profile)
    dr.trades_today += 1
    dr.realized_pnl_today += float(realized_pnl)

    log_audit_event(
        db,
        action="position.auto_close",
        user_id=user.id,
        entity_type="position",
        entity_id=position.id,
        details={
            "reason": reason,
            "exit_price": float(exit_price),
            "fees": float(fees),
            "realized_pnl": float(realized_pnl),
            "checks": checks,
        },
    )
    return float(realized_pnl)


def _record_learning_decision_snapshot(
    *,
    db: Session,
    current_user: User,
    exchange: str,
    payload: PretradeAutoPickRequest,
    out: dict,
    selected_candidate: Optional[PretradeCheckRequest],
    min_score_pct: float,
    score_weight_rules: float,
    score_weight_market: float,
    max_spread: Optional[float],
    max_slippage: Optional[float],
) -> Optional[str]:
    if not settings.LEARNING_PIPELINE_ENABLED:
        return None
    now = datetime.now(timezone.utc)
    horizon = max(5, int(settings.LEARNING_LABEL_HORIZON_MINUTES))
    decision_id = str(uuid.uuid4())
    symbol = out.get("selected_symbol")
    entry_price = None
    entry_price_source = None
    if symbol and str(exchange).upper() == "BINANCE":
        price_map = _fetch_binance_price_map([str(symbol)])
        entry_price = price_map.get(str(symbol).upper())
        if entry_price:
            entry_price_source = "binance_ticker_24h"

    snap = LearningDecisionSnapshot(
        decision_id=decision_id,
        tenant_id=_tenant_id(current_user),
        user_id=current_user.id,
        user_email=current_user.email,
        exchange=str(exchange).upper(),
        partition_ym=_partition_ym(now),
        decision_ts=now,
        target_horizon_minutes=horizon,
        dry_run=bool(payload.dry_run),
        selected=bool(out.get("selected", False)),
        decision=str(out.get("decision") or "unknown"),
        selected_symbol=symbol,
        selected_side=out.get("selected_side"),
        selected_qty=out.get("selected_qty"),
        selected_score=out.get("selected_score"),
        selected_score_rules=out.get("selected_score_rules"),
        selected_score_market=out.get("selected_score_market"),
        selected_market_regime=out.get("selected_market_regime"),
        selected_liquidity_state=out.get("selected_liquidity_state"),
        selected_size_multiplier=out.get("selected_size_multiplier"),
        top_candidate_symbol=out.get("top_candidate_symbol"),
        top_candidate_score=out.get("top_candidate_score"),
        top_candidate_score_rules=out.get("top_candidate_score_rules"),
        top_candidate_score_market=out.get("top_candidate_score_market"),
        avg_score=out.get("avg_score"),
        avg_score_rules=out.get("avg_score_rules"),
        avg_score_market=out.get("avg_score_market"),
        scanned_assets=int((out.get("scan") or {}).get("scanned_assets") or 0),
        min_score_pct=float(min_score_pct),
        score_weight_rules=float(score_weight_rules),
        score_weight_market=float(score_weight_market),
        spread_bps=float(selected_candidate.spread_bps) if selected_candidate else None,
        slippage_bps=float(selected_candidate.slippage_bps) if selected_candidate else None,
        max_spread_bps=float(max_spread) if max_spread is not None else None,
        max_slippage_bps=float(max_slippage) if max_slippage is not None else None,
        rr_estimate=float(selected_candidate.rr_estimate) if selected_candidate else None,
        trend_score=float(selected_candidate.market_trend_score) if selected_candidate else None,
        momentum_score=float(selected_candidate.momentum_score) if selected_candidate else None,
        atr_pct=float(selected_candidate.atr_pct) if selected_candidate else None,
        volume_24h_usdt=float(selected_candidate.volume_24h_usdt) if selected_candidate else None,
        entry_price=entry_price,
        entry_price_source=entry_price_source,
        top_failed_checks_json=_safe_json(out.get("top_failed_checks") or []),
        checks_json=_safe_json((out.get("scan") or {}).get("assets") or []),
    )
    db.add(snap)
    db.flush()

    due_at = now + timedelta(minutes=horizon)
    outcome = LearningDecisionOutcome(
        decision_id=decision_id,
        tenant_id=_tenant_id(current_user),
        user_id=current_user.id,
        exchange=str(exchange).upper(),
        symbol=symbol,
        partition_ym=_partition_ym(now),
        decision_ts=now,
        due_at=due_at,
        horizon_minutes=horizon,
        outcome_status="pending",
        entry_price=entry_price,
        price_source=entry_price_source,
        label_rule="ret_pct_gt_0",
    )
    db.add(outcome)
    return decision_id


def _scan_pretrade_candidates(
    db: Session,
    current_user: User,
    exchange: str,
    payload: PretradeScanRequest,
    *,
    score_weight_rules: float = 0.4,
    score_weight_market: float = 0.6,
) -> dict:
    started = time.perf_counter()
    rows = []
    passed_assets = 0
    blocked_assets = 0

    for candidate in payload.candidates:
        tick = time.perf_counter()
        exposure_check = {"name": "exposure_limits", "passed": True, "detail": "ok"}
        try:
            assert_exposure_limits(
                db=db,
                current_user=current_user,
                exchange=exchange,
                symbol=candidate.symbol,
                qty=candidate.qty,
                price_estimate=0.0,
            )
        except HTTPException as e:
            exposure_check = {
                "name": "exposure_limits",
                "passed": False,
                "detail": str(e.detail),
            }
        result = _evaluate_pretrade_for_user(
            db=db,
            current_user=current_user,
            exchange=exchange,
            payload=candidate,
            log_event=False,
        )
        result["checks"].append(exposure_check)
        result["passed"] = all(bool(c.get("passed")) for c in result.get("checks", []))
        duration_ms = round((time.perf_counter() - tick) * 1000.0, 2)
        checks = result.get("checks", [])
        failed_checks = [str(c.get("name")) for c in checks if not bool(c.get("passed"))]
        passed = bool(result.get("passed"))
        if passed:
            passed_assets += 1
        else:
            blocked_assets += 1
        score_rules, score_market, score_final = _pretrade_scores(
            result,
            candidate,
            score_weight_rules=score_weight_rules,
            score_weight_market=score_weight_market,
        )
        learning = _learning_advice_for_asset(
            db=db,
            tenant_id=_tenant_id(current_user),
            exchange=exchange,
            symbol=candidate.symbol,
            horizon_minutes=max(5, int(settings.LEARNING_LABEL_HORIZON_MINUTES or 60)),
        )
        score_blended, learning_delta = _blend_learning_score(
            score_base=score_final,
            learning_score=learning.get("learning_score"),
        )
        rows.append(
            {
                "symbol": candidate.symbol,
                "side": candidate.side,
                "qty": candidate.qty,
                "passed": passed,
                "score": score_blended,
                "score_base": score_final,
                "score_rules": score_rules,
                "score_market": score_market,
                "learning_prob_hit_pct": learning.get("prob_hit_pct"),
                "learning_samples": learning.get("samples"),
                "learning_score": learning.get("learning_score"),
                "learning_delta_points": learning_delta,
                "learning_enabled": bool(learning.get("enabled", False)),
                "market_regime": result.get("market_regime", "range"),
                "regime_source": result.get("regime_source", "legacy"),
                "passed_checks": len(checks) - len(failed_checks),
                "total_checks": len(checks),
                "failed_checks": failed_checks,
                "duration_ms": duration_ms,
                "pretrade": result,
            }
        )

    rows = rank_scan_rows(
        rows,
        include_blocked=bool(payload.include_blocked),
        top_n=int(payload.top_n),
    )

    total_ms = round((time.perf_counter() - started) * 1000.0, 2)
    avg_ms = round(total_ms / max(1, len(payload.candidates)), 2)
    return {
        "exchange": exchange,
        "scanned_assets": len(payload.candidates),
        "returned_assets": len(rows),
        "passed_assets": passed_assets,
        "blocked_assets": blocked_assets,
        "duration_ms_total": total_ms,
        "duration_ms_avg": avg_ms,
        "assets": rows,
    }


def _resolve_auto_pick_mtf_trend_fields(
    symbol: Optional[str],
    candidate_obj: Optional[PretradeCheckRequest],
    exchange: str,
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
    trend = float(candidate_obj.market_trend_score) if candidate_obj else None
    trend_1d = (
        float(candidate_obj.market_trend_score_1d)
        if candidate_obj and candidate_obj.market_trend_score_1d is not None
        else None
    )
    trend_4h = (
        float(candidate_obj.market_trend_score_4h)
        if candidate_obj and candidate_obj.market_trend_score_4h is not None
        else None
    )
    trend_1h = (
        float(candidate_obj.market_trend_score_1h)
        if candidate_obj and candidate_obj.market_trend_score_1h is not None
        else None
    )
    micro_15m = (
        float(candidate_obj.market_micro_trend_15m)
        if candidate_obj and candidate_obj.market_micro_trend_15m is not None
        else None
    )
    # For BINANCE, fill missing MTF fields directly from klines signal when snapshots
    # only provided aggregate trend_score.
    if (exchange or "").upper() == "BINANCE" and symbol and (
        trend is None or trend_1d is None or trend_4h is None or trend_1h is None or micro_15m is None
    ):
        try:
            mtf = _compute_binance_mtf_signal(str(symbol).upper())
        except Exception:
            mtf = None
        if mtf:
            if trend is None:
                trend = float(mtf.get("trend_score") or 0.0)
            if trend_1d is None and mtf.get("trend_1d") is not None:
                trend_1d = float(mtf.get("trend_1d"))
            if trend_4h is None and mtf.get("trend_4h") is not None:
                trend_4h = float(mtf.get("trend_4h"))
            if trend_1h is None and mtf.get("trend_1h") is not None:
                trend_1h = float(mtf.get("trend_1h"))
            if micro_15m is None and mtf.get("micro_trend_15m") is not None:
                micro_15m = float(mtf.get("micro_trend_15m"))
    return trend, trend_1d, trend_4h, trend_1h, micro_15m


def _select_auto_pick_candidate(
    *,
    db: Session,
    current_user: User,
    exchange: str,
    payload: PretradeAutoPickRequest,
    runtime_policy: dict,
    min_score_pct: float,
    score_weight_rules: float,
    score_weight_market: float,
) -> dict:
    # Respect explicit candidates when provided (tests/manual overrides).
    # Otherwise use the broker universe from market monitor snapshots.
    universe = list(payload.candidates or [])
    if not universe:
        universe = _build_auto_pick_universe(
            exchange,
            db=db,
            tenant_id=_tenant_id(current_user),
            direction=payload.direction,
        )
    scan_payload = PretradeScanRequest(
        candidates=universe,
        # Auto-pick evaluates the full broker universe each tick.
        top_n=max(1, len(universe)),
        include_blocked=True,
    )
    scan = _scan_pretrade_candidates(
        db=db,
        current_user=current_user,
        exchange=exchange,
        payload=scan_payload,
        score_weight_rules=score_weight_rules,
        score_weight_market=score_weight_market,
    )
    candidate_by_symbol = {c.symbol.upper(): c for c in universe}
    assets = scan.get("assets", [])
    top_candidate = assets[0] if assets else None
    top_candidate_symbol = (top_candidate or {}).get("symbol")
    top_candidate_obj = (
        candidate_by_symbol.get(str(top_candidate_symbol).upper())
        if top_candidate_symbol
        else None
    )
    (
        top_candidate_trend_score,
        top_candidate_trend_score_1d,
        top_candidate_trend_score_4h,
        top_candidate_trend_score_1h,
        top_candidate_micro_trend_15m,
    ) = _resolve_auto_pick_mtf_trend_fields(top_candidate_symbol, top_candidate_obj, exchange)
    avg_score = None
    avg_score_base = None
    avg_score_rules = None
    avg_score_market = None
    if assets:
        avg_score = round(sum(float(a.get("score") or 0.0) for a in assets) / len(assets), 2)
        avg_score_base = round(sum(float(a.get("score_base") or a.get("score") or 0.0) for a in assets) / len(assets), 2)
        avg_score_rules = round(sum(float(a.get("score_rules") or 0.0) for a in assets) / len(assets), 2)
        avg_score_market = round(sum(float(a.get("score_market") or 0.0) for a in assets) / len(assets), 2)

    if not universe:
        return {
            "universe": universe,
            "scan": scan,
            "candidate_by_symbol": candidate_by_symbol,
            "top_candidate": top_candidate,
            "top_candidate_symbol": top_candidate_symbol,
            "top_candidate_trend_score": top_candidate_trend_score,
            "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
            "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
            "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
            "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
            "avg_score": avg_score,
            "avg_score_base": avg_score_base,
            "avg_score_rules": avg_score_rules,
            "avg_score_market": avg_score_market,
            "early_response": {
                "exchange": exchange,
                "dry_run": bool(payload.dry_run),
                "requested_direction": payload.direction,
                "selected": False,
                "selected_symbol": None,
                "selected_side": None,
                "selected_qty": None,
                "selected_score": None,
                "selected_score_rules": None,
                "selected_score_market": None,
                "selected_trend_score": None,
                "selected_trend_score_1d": None,
                "selected_trend_score_4h": None,
                "selected_trend_score_1h": None,
                "selected_micro_trend_15m": None,
                "selected_market_regime": None,
                "top_candidate_symbol": None,
                "top_candidate_score": None,
                "top_candidate_score_rules": None,
                "top_candidate_score_market": None,
                "top_candidate_trend_score": None,
                "top_candidate_trend_score_1d": None,
                "top_candidate_trend_score_4h": None,
                "top_candidate_trend_score_1h": None,
                "top_candidate_micro_trend_15m": None,
                "avg_score": None,
                "avg_score_rules": None,
                "avg_score_market": None,
                "decision": "no_universe_symbols_configured",
                "top_failed_checks": ["allowlist_empty"],
                "execution": None,
                "scan": scan,
            },
            "early_finalize_kwargs": {},
        }

    passed_assets = [a for a in assets if bool(a.get("passed"))]
    score_eligible = [
        a
        for a in passed_assets
        if float(a.get("score") or 0.0)
        >= score_threshold_for_side(
            min_score_pct=float(min_score_pct),
            side=str(a.get("side") or "BUY"),
        )
    ]
    if not score_eligible:
        top_failed_checks: list[str] = []
        if assets:
            top_failed_checks = list(assets[0].get("failed_checks") or [])
        if passed_assets and "score_below_min_threshold" not in top_failed_checks:
            top_failed_checks = ["score_below_min_threshold", *top_failed_checks]
        return {
            "universe": universe,
            "scan": scan,
            "candidate_by_symbol": candidate_by_symbol,
            "top_candidate": top_candidate,
            "top_candidate_symbol": top_candidate_symbol,
            "top_candidate_trend_score": top_candidate_trend_score,
            "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
            "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
            "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
            "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
            "avg_score": avg_score,
            "avg_score_base": avg_score_base,
            "avg_score_rules": avg_score_rules,
            "avg_score_market": avg_score_market,
            "early_response": {
                "exchange": exchange,
                "dry_run": bool(payload.dry_run),
                "requested_direction": payload.direction,
                "selected": False,
                "selected_symbol": None,
                "selected_side": None,
                "selected_qty": None,
                "selected_score": None,
                "selected_score_rules": None,
                "selected_score_market": None,
                "selected_trend_score": None,
                "selected_trend_score_1d": None,
                "selected_trend_score_4h": None,
                "selected_trend_score_1h": None,
                "selected_micro_trend_15m": None,
                "selected_market_regime": None,
                "top_candidate_symbol": top_candidate_symbol,
                "top_candidate_score": (top_candidate or {}).get("score"),
                "top_candidate_score_base": (top_candidate or {}).get("score_base"),
                "top_candidate_score_rules": (top_candidate or {}).get("score_rules"),
                "top_candidate_score_market": (top_candidate or {}).get("score_market"),
                "top_candidate_learning_prob_hit_pct": (top_candidate or {}).get("learning_prob_hit_pct"),
                "top_candidate_learning_samples": (top_candidate or {}).get("learning_samples"),
                "top_candidate_learning_score": (top_candidate or {}).get("learning_score"),
                "top_candidate_learning_delta_points": (top_candidate or {}).get("learning_delta_points"),
                "top_candidate_trend_score": top_candidate_trend_score,
                "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
                "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
                "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
                "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
                "avg_score": avg_score,
                "avg_score_base": avg_score_base,
                "avg_score_rules": avg_score_rules,
                "avg_score_market": avg_score_market,
                "decision": "no_candidate_passed",
                "top_failed_checks": top_failed_checks,
                "execution": None,
                "scan": scan,
            },
            "early_finalize_kwargs": {},
        }

    selected = score_eligible[0]
    regime = str(selected.get("market_regime") or "range")
    max_spread = float(runtime_policy.get(f"max_spread_bps_{regime}", 15.0))
    max_slippage = float(runtime_policy.get(f"max_slippage_bps_{regime}", 20.0))
    candidate = candidate_by_symbol.get(str(selected.get("symbol") or "").upper())
    cand_spread = float(candidate.spread_bps) if candidate else max_spread
    cand_slippage = float(candidate.slippage_bps) if candidate else max_slippage
    selected_score = float(selected.get("score") or 0.0)
    liquidity_state, size_multiplier = _classify_liquidity_state(
        spread_bps=cand_spread,
        slippage_bps=cand_slippage,
        max_spread_bps=max_spread,
        max_slippage_bps=max_slippage,
        selected_score=selected_score,
        min_score_pct=min_score_pct,
    )
    selected_side = str(selected.get("side") or "BUY").upper()
    if selected_side == "SELL" and liquidity_state != "green":
        return {
            "universe": universe,
            "scan": scan,
            "candidate_by_symbol": candidate_by_symbol,
            "top_candidate": top_candidate,
            "top_candidate_symbol": top_candidate_symbol,
            "top_candidate_trend_score": top_candidate_trend_score,
            "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
            "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
            "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
            "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
            "avg_score": avg_score,
            "avg_score_base": avg_score_base,
            "avg_score_rules": avg_score_rules,
            "avg_score_market": avg_score_market,
            "early_response": {
                "exchange": exchange,
                "dry_run": bool(payload.dry_run),
                "requested_direction": payload.direction,
                "selected": False,
                "selected_symbol": None,
                "selected_side": None,
                "selected_qty": None,
                "selected_score": None,
                "selected_score_rules": None,
                "selected_score_market": None,
                "selected_trend_score": None,
                "selected_trend_score_1d": None,
                "selected_trend_score_4h": None,
                "selected_trend_score_1h": None,
                "selected_micro_trend_15m": None,
                "selected_market_regime": None,
                "selected_liquidity_state": liquidity_state,
                "selected_size_multiplier": 0.0,
                "top_candidate_symbol": top_candidate_symbol,
                "top_candidate_score": (top_candidate or {}).get("score"),
                "top_candidate_score_rules": (top_candidate or {}).get("score_rules"),
                "top_candidate_score_market": (top_candidate or {}).get("score_market"),
                "top_candidate_trend_score": top_candidate_trend_score,
                "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
                "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
                "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
                "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
                "avg_score": avg_score,
                "avg_score_rules": avg_score_rules,
                "avg_score_market": avg_score_market,
                "decision": "no_candidate_passed",
                "top_failed_checks": ["short_requires_green_liquidity"],
                "execution": None,
                "scan": scan,
            },
            "early_finalize_kwargs": {"max_spread": max_spread, "max_slippage": max_slippage},
        }
    if liquidity_state == "red":
        return {
            "universe": universe,
            "scan": scan,
            "candidate_by_symbol": candidate_by_symbol,
            "top_candidate": top_candidate,
            "top_candidate_symbol": top_candidate_symbol,
            "top_candidate_trend_score": top_candidate_trend_score,
            "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
            "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
            "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
            "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
            "avg_score": avg_score,
            "avg_score_base": avg_score_base,
            "avg_score_rules": avg_score_rules,
            "avg_score_market": avg_score_market,
            "early_response": {
                "exchange": exchange,
                "dry_run": bool(payload.dry_run),
                "requested_direction": payload.direction,
                "selected": False,
                "selected_symbol": None,
                "selected_side": None,
                "selected_qty": None,
                "selected_score": None,
                "selected_score_rules": None,
                "selected_score_market": None,
                "selected_trend_score": None,
                "selected_trend_score_1d": None,
                "selected_trend_score_4h": None,
                "selected_trend_score_1h": None,
                "selected_micro_trend_15m": None,
                "selected_market_regime": None,
                "selected_liquidity_state": "red",
                "selected_size_multiplier": 0.0,
                "top_candidate_symbol": top_candidate_symbol,
                "top_candidate_score": (top_candidate or {}).get("score"),
                "top_candidate_score_rules": (top_candidate or {}).get("score_rules"),
                "top_candidate_score_market": (top_candidate or {}).get("score_market"),
                "top_candidate_trend_score": top_candidate_trend_score,
                "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
                "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
                "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
                "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
                "avg_score": avg_score,
                "avg_score_rules": avg_score_rules,
                "avg_score_market": avg_score_market,
                "decision": "no_candidate_passed",
                "top_failed_checks": ["effective_liquidity_failed"],
                "execution": None,
                "scan": scan,
            },
            "early_finalize_kwargs": {"max_spread": max_spread, "max_slippage": max_slippage},
        }

    selected_qty_requested = float(selected["qty"])
    selected_qty = selected_qty_requested * float(size_multiplier)
    if selected_qty <= 0:
        selected_qty = selected_qty_requested
    if selected_side == "SELL":
        selected_qty = selected_qty * 0.35
        size_multiplier = float(size_multiplier) * 0.35

    selected_qty_sized = float(selected_qty)
    selected_symbol = str(selected["symbol"])

    return {
        "universe": universe,
        "scan": scan,
        "candidate_by_symbol": candidate_by_symbol,
        "top_candidate": top_candidate,
        "top_candidate_symbol": top_candidate_symbol,
        "top_candidate_trend_score": top_candidate_trend_score,
        "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
        "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
        "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
        "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
        "avg_score": avg_score,
        "avg_score_base": avg_score_base,
        "avg_score_rules": avg_score_rules,
        "avg_score_market": avg_score_market,
        "early_response": None,
        "early_finalize_kwargs": {},
        "selected": selected,
        "candidate": candidate,
        "max_spread": max_spread,
        "max_slippage": max_slippage,
        "liquidity_state": liquidity_state,
        "size_multiplier": size_multiplier,
        "selected_side": selected_side,
        "selected_qty_requested": selected_qty_requested,
        "selected_qty": selected_qty,
        "selected_qty_sized": selected_qty_sized,
        "selected_symbol": selected_symbol,
    }


def _auto_pick_from_scan(
    db: Session,
    current_user: User,
    exchange: str,
    payload: PretradeAutoPickRequest,
    idempotency_key: Optional[str] = None,
) -> dict:
    strategy = resolve_strategy_for_user_exchange(
        db=db,
        user_id=current_user.id,
        exchange=exchange,
    )
    runtime_policy = resolve_runtime_policy(
        db=db,
        strategy_id=strategy["strategy_id"],
        exchange=exchange,
    )
    min_score_pct = float(runtime_policy.get("min_score_pct", 78.0))
    score_weight_rules = float(runtime_policy.get("score_weight_rules", 0.4))
    score_weight_market = float(runtime_policy.get("score_weight_market", 0.6))
    selection = _select_auto_pick_candidate(
        db=db,
        current_user=current_user,
        exchange=exchange,
        payload=payload,
        runtime_policy=runtime_policy,
        min_score_pct=min_score_pct,
        score_weight_rules=score_weight_rules,
        score_weight_market=score_weight_market,
    )
    candidate_by_symbol = selection["candidate_by_symbol"]
    scan = selection["scan"]
    top_candidate = selection["top_candidate"]
    top_candidate_symbol = selection["top_candidate_symbol"]
    top_candidate_trend_score = selection["top_candidate_trend_score"]
    top_candidate_trend_score_1d = selection["top_candidate_trend_score_1d"]
    top_candidate_trend_score_4h = selection["top_candidate_trend_score_4h"]
    top_candidate_trend_score_1h = selection["top_candidate_trend_score_1h"]
    top_candidate_micro_trend_15m = selection["top_candidate_micro_trend_15m"]
    avg_score = selection["avg_score"]
    avg_score_base = selection["avg_score_base"]
    avg_score_rules = selection["avg_score_rules"]
    avg_score_market = selection["avg_score_market"]

    def _finalize(response: dict, *, max_spread: Optional[float] = None, max_slippage: Optional[float] = None) -> dict:
        response["execution_status"] = _resolve_auto_pick_execution_status(response)
        try:
            selected_symbol = response.get("selected_symbol")
            selected_candidate = (
                candidate_by_symbol.get(str(selected_symbol).upper())
                if selected_symbol
                else None
            )
            decision_id = _record_learning_decision_snapshot(
                db=db,
                current_user=current_user,
                exchange=exchange,
                payload=payload,
                out=response,
                selected_candidate=selected_candidate,
                min_score_pct=min_score_pct,
                score_weight_rules=score_weight_rules,
                score_weight_market=score_weight_market,
                max_spread=max_spread,
                max_slippage=max_slippage,
            )
            response["learning_decision_id"] = decision_id
        except Exception:
            # Learning must never block trading decisions.
            pass
        try:
            _attach_prediction_vs_real(db=db, response=response)
        except Exception:
            response["predicted_hit_pct"] = None
            response["predicted_positive"] = None
            response["outcome_status"] = None
            response["realized_hit"] = None
            response["prediction_vs_real"] = "no_prediction"
        return response

    early_response = selection["early_response"]
    if early_response is not None:
        return _finalize(early_response, **selection["early_finalize_kwargs"])

    selected = selection["selected"]
    regime = str(selected.get("market_regime") or "range")
    max_spread = float(runtime_policy.get(f"max_spread_bps_{regime}", 15.0))
    max_slippage = float(runtime_policy.get(f"max_slippage_bps_{regime}", 20.0))
    candidate = candidate_by_symbol.get(str(selected.get("symbol") or "").upper())
    cand_spread = float(candidate.spread_bps) if candidate else max_spread
    cand_slippage = float(candidate.slippage_bps) if candidate else max_slippage
    selected_score = float(selected.get("score") or 0.0)
    liquidity_state, size_multiplier = _classify_liquidity_state(
        spread_bps=cand_spread,
        slippage_bps=cand_slippage,
        max_spread_bps=max_spread,
        max_slippage_bps=max_slippage,
        selected_score=selected_score,
        min_score_pct=min_score_pct,
    )
    selected_side = str(selected.get("side") or "BUY").upper()
    selected_qty_requested = float(selected["qty"])
    selected_qty = selected_qty_requested * float(size_multiplier)
    if selected_qty <= 0:
        selected_qty = selected_qty_requested
    if selected_side == "SELL":
        selected_qty = selected_qty * 0.35
        size_multiplier = float(size_multiplier) * 0.35

    selected_qty_sized = float(selected_qty)
    selected_symbol = str(selected["symbol"])

    execution_preview = resolve_execution_quantity_preview(
        exchange=exchange,
        symbol=selected_symbol,
        side=selected_side,
        requested_qty=selected_qty_sized,
    )

    assert_exposure_limits(
        db=db,
        current_user=current_user,
        exchange=exchange,
        symbol=selected_symbol,
        qty=execution_preview["normalized_qty"],
        price_estimate=execution_preview.get("price_estimate") or 0.0,
    )

    # canonical final operational qty for downstream execution path
    selected_qty = float(execution_preview.get("normalized_qty", 0.0))

    execution = None
    decision = "dry_run_selected_gray" if liquidity_state == "gray" else "dry_run_selected"
    idempotency_reserved = False
    idempotency_finalized = False
    idempotency_endpoint = None
    idempotency_request_payload = None
    intent_lock_key = None
    intent_lock_acquired = False
    intent_lock_conn = None
    try:
        if not payload.dry_run:
            enforce_exit_plan = bool(
                settings.AUTO_PICK_REAL_REQUIRE_EXIT_PLAN and settings.AUTO_PICK_REAL_GUARD_ENABLED
            )
            real_guard_reason, plan_reason, exit_plan = _evaluate_real_execution_pre_dispatch_gate(
                current_user=current_user,
                exchange=exchange,
                symbol=selected_symbol,
                side=selected_side,
                candidate=candidate,
                enforce_exit_plan=enforce_exit_plan,
            )
            if real_guard_reason:
                return _finalize({
                    "exchange": exchange,
                    "dry_run": bool(payload.dry_run),
                    "requested_direction": payload.direction,
                    "selected": False,
                    "selected_symbol": None,
                    "selected_side": None,
                    "selected_qty": None,
                    "selected_score": None,
                    "selected_score_rules": None,
                    "selected_score_market": None,
                    "selected_trend_score": None,
                    "selected_trend_score_1d": None,
                    "selected_trend_score_4h": None,
                    "selected_trend_score_1h": None,
                    "selected_micro_trend_15m": None,
                    "selected_market_regime": None,
                    "selected_liquidity_state": liquidity_state,
                    "selected_size_multiplier": round(float(size_multiplier), 4),
                    "top_candidate_symbol": top_candidate_symbol,
                    "top_candidate_score": (top_candidate or {}).get("score"),
                    "top_candidate_score_rules": (top_candidate or {}).get("score_rules"),
                    "top_candidate_score_market": (top_candidate or {}).get("score_market"),
                    "top_candidate_trend_score": top_candidate_trend_score,
                    "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
                    "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
                    "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
                    "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
                    "avg_score": avg_score,
                    "avg_score_rules": avg_score_rules,
                    "avg_score_market": avg_score_market,
                    "decision": "blocked_real_execution_guard",
                    "top_failed_checks": [real_guard_reason],
                    "execution": None,
                    "scan": scan,
                }, max_spread=max_spread, max_slippage=max_slippage)
            if plan_reason:
                return _finalize({
                    "exchange": exchange,
                    "dry_run": bool(payload.dry_run),
                    "requested_direction": payload.direction,
                    "selected": False,
                    "selected_symbol": None,
                    "selected_side": None,
                    "selected_qty": None,
                    "selected_score": None,
                    "selected_score_rules": None,
                    "selected_score_market": None,
                    "selected_trend_score": None,
                    "selected_trend_score_1d": None,
                    "selected_trend_score_4h": None,
                    "selected_trend_score_1h": None,
                    "selected_micro_trend_15m": None,
                    "selected_market_regime": None,
                    "selected_liquidity_state": liquidity_state,
                    "selected_size_multiplier": round(float(size_multiplier), 4),
                    "top_candidate_symbol": top_candidate_symbol,
                    "top_candidate_score": (top_candidate or {}).get("score"),
                    "top_candidate_score_rules": (top_candidate or {}).get("score_rules"),
                    "top_candidate_score_market": (top_candidate or {}).get("score_market"),
                    "top_candidate_trend_score": top_candidate_trend_score,
                    "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
                    "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
                    "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
                    "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
                    "avg_score": avg_score,
                    "avg_score_rules": avg_score_rules,
                    "avg_score_market": avg_score_market,
                    "decision": "blocked_real_execution_guard",
                    "top_failed_checks": [plan_reason],
                    "execution": {"exit_plan": None},
                    "scan": scan,
                }, max_spread=max_spread, max_slippage=max_slippage)
            (
                intent_lock_reason,
                intent_lock_key,
                intent_lock_acquired,
                intent_lock_conn,
            ) = _evaluate_semantic_intent_lock_acquire(
                current_user=current_user,
                exchange=exchange,
                symbol=selected_symbol,
                side=selected_side,
            )

            if intent_lock_reason:
                log_audit_event(
                    db,
                    action="execution.blocked.intent_lock",
                    user_id=current_user.id,
                    entity_type="execution",
                    details={
                        "exchange": exchange,
                        "symbol": selected_symbol,
                        "side": selected_side,
                        "reason": intent_lock_reason,
                    },
                )
                return _finalize({
                    "exchange": exchange,
                    "dry_run": bool(payload.dry_run),
                    "requested_direction": payload.direction,
                    "selected": False,
                    "selected_symbol": None,
                    "selected_side": None,
                    "selected_qty": None,
                    "selected_score": None,
                    "selected_score_rules": None,
                    "selected_score_market": None,
                    "selected_trend_score": None,
                    "selected_trend_score_1d": None,
                    "selected_trend_score_4h": None,
                    "selected_trend_score_1h": None,
                    "selected_micro_trend_15m": None,
                    "selected_market_regime": None,
                    "selected_liquidity_state": liquidity_state,
                    "selected_size_multiplier": round(float(size_multiplier), 4),
                    "top_candidate_symbol": top_candidate_symbol,
                    "top_candidate_score": (top_candidate or {}).get("score"),
                    "top_candidate_score_rules": (top_candidate or {}).get("score_rules"),
                    "top_candidate_score_market": (top_candidate or {}).get("score_market"),
                    "top_candidate_trend_score": top_candidate_trend_score,
                    "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
                    "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
                    "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
                    "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
                    "avg_score": avg_score,
                    "avg_score_rules": avg_score_rules,
                    "avg_score_market": avg_score_market,
                    "decision": "blocked_real_execution_guard",
                    "top_failed_checks": [intent_lock_reason],
                    "execution": None,
                    "scan": scan,
                }, max_spread=max_spread, max_slippage=max_slippage)

            (
                broker_guard_reason,
                broker_guard_required_usdt,
                broker_guard_usdt_free,
            ) = _evaluate_binance_spot_usdt_broker_guard(
                user_id=current_user.id,
                exchange=exchange,
                side=selected_side,
                symbol=selected_symbol,
                execution_preview=execution_preview,
            )

            if broker_guard_reason:
                log_audit_event(
                    db,
                    action="execution.blocked.broker_spot_guard",
                    user_id=current_user.id,
                    entity_type="execution",
                    details={
                        "exchange": exchange,
                        "symbol": selected_symbol,
                        "side": selected_side,
                        "reason": broker_guard_reason,
                        "estimated_notional": execution_preview.get("estimated_notional"),
                        "required_usdt": broker_guard_required_usdt,
                        "usdt_free": broker_guard_usdt_free,
                    },
                )
                return _finalize({
                    "exchange": exchange,
                    "dry_run": bool(payload.dry_run),
                    "requested_direction": payload.direction,
                    "selected": False,
                    "selected_symbol": None,
                    "selected_side": None,
                    "selected_qty": None,
                    "selected_score": None,
                    "selected_score_rules": None,
                    "selected_score_market": None,
                    "selected_trend_score": None,
                    "selected_trend_score_1d": None,
                    "selected_trend_score_4h": None,
                    "selected_trend_score_1h": None,
                    "selected_micro_trend_15m": None,
                    "selected_market_regime": None,
                    "selected_liquidity_state": liquidity_state,
                    "selected_size_multiplier": round(float(size_multiplier), 4),
                    "top_candidate_symbol": top_candidate_symbol,
                    "top_candidate_score": (top_candidate or {}).get("score"),
                    "top_candidate_score_rules": (top_candidate or {}).get("score_rules"),
                    "top_candidate_score_market": (top_candidate or {}).get("score_market"),
                    "top_candidate_trend_score": top_candidate_trend_score,
                    "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
                    "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
                    "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
                    "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
                    "avg_score": avg_score,
                    "avg_score_rules": avg_score_rules,
                    "avg_score_market": avg_score_market,
                    "decision": "blocked_real_execution_guard",
                    "top_failed_checks": [broker_guard_reason],
                    "execution": None,
                    "scan": scan,
                }, max_spread=max_spread, max_slippage=max_slippage)
            if exchange == "BINANCE":
                return _run_binance_auto_pick_live_flow(
                    db=db,
                    current_user=current_user,
                    exchange=exchange,
                    payload=payload,
                    idempotency_key=idempotency_key,
                    selected=selected,
                    selected_symbol=selected_symbol,
                    selected_qty=selected_qty,
                    selected_qty_requested=selected_qty_requested,
                    selected_qty_sized=selected_qty_sized,
                    selected_side=selected_side,
                    candidate=candidate,
                    execution_preview=execution_preview,
                    liquidity_state=liquidity_state,
                    size_multiplier=size_multiplier,
                    top_candidate_symbol=top_candidate_symbol,
                    top_candidate=top_candidate,
                    top_candidate_trend_score=top_candidate_trend_score,
                    top_candidate_trend_score_1d=top_candidate_trend_score_1d,
                    top_candidate_trend_score_4h=top_candidate_trend_score_4h,
                    top_candidate_trend_score_1h=top_candidate_trend_score_1h,
                    top_candidate_micro_trend_15m=top_candidate_micro_trend_15m,
                    avg_score=avg_score,
                    avg_score_base=avg_score_base,
                    avg_score_rules=avg_score_rules,
                    avg_score_market=avg_score_market,
                    scan=scan,
                    enforce_exit_plan=enforce_exit_plan,
                    exit_plan=exit_plan,
                    max_spread=max_spread,
                    max_slippage=max_slippage,
                    _finalize=_finalize,
                )
            cached_response, idempotency_endpoint, idempotency_request_payload = _reserve_auto_pick_pre_dispatch_idempotency(
                db=db,
                user_id=current_user.id,
                exchange=exchange,
                symbol=selected_symbol,
                side=selected_side,
                selected_qty=selected_qty,
                idempotency_key=idempotency_key,
            )
            if cached_response is not None:
                return cached_response
            idempotency_reserved = True

            try:
                execution = execute_ibkr_test_order_for_user(
                    user_id=current_user.id,
                    symbol=selected["symbol"],
                    side=selected["side"],
                    qty=selected_qty,
                )
                decision = "executed_test_order_gray" if liquidity_state == "gray" else "executed_test_order"
                if enforce_exit_plan:
                    execution = {**(execution or {}), "exit_plan": exit_plan}
            except HTTPException as exc:
                decision = "insufficient_resources_or_execution_error"
                execution = {"error": str(exc.detail)}
                if idempotency_reserved:
                    _finalize_auto_pick_idempotent_intent_best_effort(
                        db=db,
                        user_id=current_user.id,
                        endpoint=idempotency_endpoint,
                        idempotency_key=idempotency_key,
                        request_payload=idempotency_request_payload,
                        response_payload={"decision": decision, "execution": execution},
                        status_code=500,
                    )
                    idempotency_finalized = True

        (
            selected_trend_score,
            selected_trend_score_1d,
            selected_trend_score_4h,
            selected_trend_score_1h,
            selected_micro_trend_15m,
        ) = _resolve_auto_pick_mtf_trend_fields(selected_symbol, candidate, exchange)

        out = _finalize({
            "exchange": exchange,
            "dry_run": bool(payload.dry_run),
            "requested_direction": payload.direction,
            "selected": True,
            "selected_symbol": selected_symbol,
            "selected_side": selected["side"],
            "selected_qty_requested": round(selected_qty_requested, 8),
            "selected_qty_sized": round(selected_qty_sized, 8),
            "selected_qty_normalized": round(float(execution_preview.get("normalized_qty", 0.0)), 8),
            "selected_price_estimate": execution_preview.get("price_estimate"),
            "selected_estimated_notional": execution_preview.get("estimated_notional"),
            "selected_qty_normalization_source": execution_preview.get("normalization_source"),
            "selected_qty": round(selected_qty, 8),
            "selected_score": selected["score"],
            "selected_score_base": selected.get("score_base"),
            "selected_score_rules": selected["score_rules"],
            "selected_score_market": selected["score_market"],
            "selected_learning_prob_hit_pct": selected.get("learning_prob_hit_pct"),
            "selected_learning_samples": selected.get("learning_samples"),
            "selected_learning_score": selected.get("learning_score"),
            "selected_learning_delta_points": selected.get("learning_delta_points"),
            "selected_trend_score": selected_trend_score,
            "selected_trend_score_1d": selected_trend_score_1d,
            "selected_trend_score_4h": selected_trend_score_4h,
            "selected_trend_score_1h": selected_trend_score_1h,
            "selected_micro_trend_15m": selected_micro_trend_15m,
            "selected_market_regime": selected["market_regime"],
            "selected_liquidity_state": liquidity_state,
            "selected_size_multiplier": round(float(size_multiplier), 4),
            "top_candidate_symbol": top_candidate_symbol,
            "top_candidate_score": (top_candidate or {}).get("score"),
            "top_candidate_score_base": (top_candidate or {}).get("score_base"),
            "top_candidate_score_rules": (top_candidate or {}).get("score_rules"),
            "top_candidate_score_market": (top_candidate or {}).get("score_market"),
            "top_candidate_learning_prob_hit_pct": (top_candidate or {}).get("learning_prob_hit_pct"),
            "top_candidate_learning_samples": (top_candidate or {}).get("learning_samples"),
            "top_candidate_learning_score": (top_candidate or {}).get("learning_score"),
            "top_candidate_learning_delta_points": (top_candidate or {}).get("learning_delta_points"),
            "top_candidate_trend_score": top_candidate_trend_score,
            "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
            "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
            "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
            "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
            "avg_score": avg_score,
            "avg_score_base": avg_score_base,
            "avg_score_rules": avg_score_rules,
            "avg_score_market": avg_score_market,
            "decision": decision,
            "top_failed_checks": [],
            "execution": execution,
            "scan": scan,
        }, max_spread=max_spread, max_slippage=max_slippage)

        if idempotency_reserved and not idempotency_finalized:
            # Keep the candidate result path operational; reservation finalization is best-effort.
            _finalize_auto_pick_idempotent_intent_best_effort(
                db=db,
                user_id=current_user.id,
                endpoint=idempotency_endpoint,
                idempotency_key=idempotency_key,
                request_payload=idempotency_request_payload,
                response_payload=out,
                status_code=200,
            )

        return out
    finally:
        if intent_lock_conn is not None:
            try:
                if intent_lock_acquired and intent_lock_key is not None:
                    intent_lock_conn.execute(
                        text("SELECT pg_advisory_unlock(:k)"),
                        {"k": intent_lock_key},
                    )
            except Exception:
                # Best-effort unlock: do not mask the primary flow error.
                pass
            finally:
                try:
                    intent_lock_conn.close()
                except Exception:
                    pass


def _build_strategy_checks(
    exchange: str,
    strategy_id: str,
    payload: PretradeCheckRequest,
    market_regime: str,
    runtime_policy: dict,
    profile: dict,
) -> list[dict]:
    checks: list[dict] = []
    ex = exchange.upper()
    st = strategy_id.upper()

    if st == "INTRADAY_V1":
        allowed_trend_tfs = {"1H"}
        allowed_signal_tfs = {"15M"}
        allowed_timing_tfs = {"5M", "15M"}
    else:
        if ex == "IBKR":
            allowed_trend_tfs = {"1D", "4H"}
            allowed_signal_tfs = {"1H", "30M"}
            allowed_timing_tfs = {"5M", "15M"}
        else:
            allowed_trend_tfs = {"4H"}
            allowed_signal_tfs = {"1H"}
            allowed_timing_tfs = {"15M"}

    allow_regime = bool(runtime_policy.get(f"allow_{market_regime}", True))
    rr_min = float(runtime_policy.get(f"rr_min_{market_regime}", 1.5))
    is_short = str(payload.side or "BUY").upper() == "SELL"
    if is_short:
        rr_min = max(rr_min, 2.0)
    checks.append(
        {
            "name": "market_regime_allowed",
            "passed": allow_regime,
            "detail": f"regime={market_regime} allowed={allow_regime}",
        }
    )
    checks.append(
        {
            "name": "max_leverage",
            "passed": float(payload.leverage) <= float(profile.get("max_leverage", 1.0)),
            "detail": f"value={payload.leverage} required<={float(profile.get('max_leverage', 1.0))}",
        }
    )

    checks.append(
        {
            "name": "strategy_rr_min",
            "passed": float(payload.rr_estimate) >= rr_min,
            "detail": f"rr={payload.rr_estimate} required>={rr_min}",
        }
    )
    if is_short:
        t1d = payload.market_trend_score_1d if payload.market_trend_score_1d is not None else payload.market_trend_score
        t4h = payload.market_trend_score_4h if payload.market_trend_score_4h is not None else payload.market_trend_score
        t1h = payload.market_trend_score_1h if payload.market_trend_score_1h is not None else payload.market_trend_score
        checks.append(
            {
                "name": "short_mtf_1d_strong_bear",
                "passed": float(t1d) <= -0.40,
                "detail": f"value={round(float(t1d),6)} required<=-0.40",
            }
        )
        checks.append(
            {
                "name": "short_mtf_4h_strong_bear",
                "passed": float(t4h) <= -0.35,
                "detail": f"value={round(float(t4h),6)} required<=-0.35",
            }
        )
        checks.append(
            {
                "name": "short_mtf_1h_bear",
                "passed": float(t1h) <= -0.25,
                "detail": f"value={round(float(t1h),6)} required<=-0.25",
            }
        )
        micro = payload.market_micro_trend_15m
        checks.append(
            {
                "name": "short_micro_15m_confirm",
                "passed": True if micro is None else float(micro) <= -0.12,
                "detail": "no_data -> pass" if micro is None else f"value={round(float(micro),6)} required<=-0.12",
            }
        )
    else:
        micro = payload.market_micro_trend_15m
        checks.append(
            {
                "name": "long_micro_15m_confirm",
                "passed": True if micro is None else float(micro) >= 0.08,
                "detail": "no_data -> pass" if micro is None else f"value={round(float(micro),6)} required>=0.08",
            }
        )
    checks.append(
        {
            "name": "strategy_trend_tf",
            "passed": payload.trend_tf in allowed_trend_tfs,
            "detail": f"value={payload.trend_tf} allowed={sorted(allowed_trend_tfs)}",
        }
    )
    checks.append(
        {
            "name": "strategy_signal_tf",
            "passed": payload.signal_tf in allowed_signal_tfs,
            "detail": f"value={payload.signal_tf} allowed={sorted(allowed_signal_tfs)}",
        }
    )
    checks.append(
        {
            "name": "strategy_timing_tf",
            "passed": payload.timing_tf in allowed_timing_tfs,
            "detail": f"value={payload.timing_tf} allowed={sorted(allowed_timing_tfs)}",
        }
    )

    if ex == "BINANCE":
        checks.append(
            {
                "name": "symbol_allowlist",
                "passed": True,
                "detail": f"{payload.symbol.upper()} (auto-universe)",
            }
        )
        checks.append(
            {
                "name": "crypto_event_clear",
                "passed": not bool(payload.crypto_event_block),
                "detail": f"crypto_event_block={payload.crypto_event_block}",
            }
        )

        min_volume = float(runtime_policy.get(f"min_volume_24h_usdt_{market_regime}", 0.0))
        max_spread = float(runtime_policy.get(f"max_spread_bps_{market_regime}", 15.0))
        max_slippage = float(runtime_policy.get(f"max_slippage_bps_{market_regime}", 20.0))
        if payload.market_session == "OFF_HOURS":
            min_volume *= 1.3
            max_spread *= 0.8
            max_slippage *= 0.8

        # Conservative anti-carry guard for perpetual funding regimes.
        if market_regime == "range":
            max_funding = 12.0
        elif market_regime == "bear":
            max_funding = 15.0
        else:
            max_funding = 20.0

        checks.append(
            {
                "name": "liq_volume_24h",
                "passed": float(payload.volume_24h_usdt) >= min_volume,
                "detail": f"value={payload.volume_24h_usdt} required>={min_volume}",
            }
        )
        checks.append(
            {
                "name": "liq_spread_bps",
                "passed": float(payload.spread_bps) <= max_spread,
                "detail": f"value={payload.spread_bps} required<={max_spread}",
            }
        )
        checks.append(
            {
                "name": "liq_slippage_bps",
                "passed": float(payload.slippage_bps) <= max_slippage,
                "detail": f"value={payload.slippage_bps} required<={max_slippage}",
            }
        )
        checks.append(
            {
                "name": "funding_rate_bps",
                "passed": abs(float(payload.funding_rate_bps)) <= max_funding,
                "detail": f"value={payload.funding_rate_bps} abs_required<={max_funding}",
            }
        )
    else:
        checks.append(
            {
                "name": "symbol_allowlist",
                "passed": True,
                "detail": f"{payload.symbol.upper()} (auto-universe)",
            }
        )
        max_spread = float(runtime_policy.get(f"max_spread_bps_{market_regime}", 15.0))
        max_slippage = float(runtime_policy.get(f"max_slippage_bps_{market_regime}", 20.0))
        checks.append(
            {
                "name": "ibkr_in_rth",
                "passed": bool(payload.in_rth),
                "detail": "must be true",
            }
        )
        checks.append(
            {
                "name": "ibkr_spread_bps",
                "passed": float(payload.spread_bps) <= max_spread,
                "detail": f"value={payload.spread_bps} required<={max_spread}",
            }
        )
        checks.append(
            {
                "name": "ibkr_slippage_bps",
                "passed": float(payload.slippage_bps) <= max_slippage,
                "detail": f"value={payload.slippage_bps} required<={max_slippage}",
            }
        )
        checks.append(
            {
                "name": "ibkr_no_macro_block",
                "passed": not bool(payload.macro_event_block),
                "detail": f"macro_event_block={payload.macro_event_block}",
            }
        )
        checks.append(
            {
                "name": "ibkr_no_earnings_24h",
                "passed": not bool(payload.earnings_within_24h),
                "detail": f"earnings_within_24h={payload.earnings_within_24h}",
            }
        )

    return checks


def _build_exit_checks(
    exchange: str,
    strategy_id: str,
    payload: ExitCheckRequest,
    market_regime: str,
    runtime_policy: dict,
) -> tuple[list[dict], list[str]]:
    ex = exchange.upper()
    st = strategy_id.upper()
    checks: list[dict] = []
    reasons: list[str] = []

    side = payload.side.upper()
    entry = float(payload.entry_price)
    current = float(payload.current_price)
    stop = float(payload.stop_loss)
    take = float(payload.take_profit)
    opened_minutes = int(payload.opened_minutes)

    if side == "BUY":
        sl_hit = current <= stop
        tp_hit = current >= take
    else:
        sl_hit = current >= stop
        tp_hit = current <= take

    checks.append({"name": "exit_stop_loss_hit", "passed": sl_hit, "detail": f"current={current} stop={stop}"})
    checks.append({"name": "exit_take_profit_hit", "passed": tp_hit, "detail": f"current={current} take_profit={take}"})
    if sl_hit:
        reasons.append("stop_loss_hit")
    if tp_hit:
        reasons.append("take_profit_hit")

    if st == "INTRADAY_V1":
        fallback_hold = 240
    else:
        fallback_hold = 480
    max_hold_minutes = int(float(runtime_policy.get(f"max_hold_minutes_{market_regime}", fallback_hold)))
    min_progress_r = max(0.0, float(settings.EXIT_TIME_MIN_PROGRESS_R or 0.5))

    risk_distance = abs(entry - stop)
    favorable_move = (current - entry) if side == "BUY" else (entry - current)
    progress_r = (favorable_move / risk_distance) if risk_distance > 0 else 0.0

    timeout = opened_minutes >= max_hold_minutes
    checks.append(
        {
            "name": "exit_time_limit",
            "passed": timeout,
            "detail": f"opened_minutes={opened_minutes} limit={max_hold_minutes}",
        }
    )
    progress_ok = progress_r >= min_progress_r
    checks.append(
        {
            "name": "exit_time_min_progress_r",
            "passed": progress_ok,
            "detail": f"progress_r={round(progress_r,4)} required>={round(min_progress_r,4)}",
        }
    )
    if timeout:
        reasons.append("time_limit_reached")
        if not progress_ok:
            reasons.append("time_limit_no_progress")

    trend_break = bool(payload.trend_break)
    signal_reverse = bool(payload.signal_reverse)
    checks.append({"name": "exit_trend_break", "passed": trend_break, "detail": f"trend_break={trend_break}"})
    checks.append({"name": "exit_signal_reverse", "passed": signal_reverse, "detail": f"signal_reverse={signal_reverse}"})
    if trend_break:
        reasons.append("trend_break")
    if signal_reverse:
        reasons.append("signal_reverse")

    if ex == "IBKR":
        event_forced_exit = bool(payload.macro_event_block) or bool(payload.earnings_within_24h)
        checks.append(
            {
                "name": "exit_event_risk",
                "passed": event_forced_exit,
                "detail": f"macro_event_block={payload.macro_event_block} earnings_within_24h={payload.earnings_within_24h}",
            }
        )
        if event_forced_exit:
            reasons.append("event_risk_exit")

    # Deduplicate while preserving order.
    uniq_reasons = list(dict.fromkeys(reasons))
    return checks, uniq_reasons

@router.get("/health")
def ops_health():
    return {"system_state": "OK", "note": "placeholder"}


@router.get("/backoffice/summary", response_model=BackofficeSummaryOut)
def backoffice_summary(
    real_only: bool = True,
    max_secret_age_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role("admin", "operator", "viewer")),
):
    tenant = _tenant_id(current_user)
    now, posture_rows, missing_2fa, stale_secrets = _build_security_posture_rows(
        db,
        tenant_id=tenant,
        real_only=real_only,
        max_secret_age_days=max_secret_age_days,
    )
    _ = now
    counts = {"admin": 0, "operator": 0, "viewer": 0, "trader": 0, "disabled": 0}
    for row in posture_rows:
        role = (row.role or "").lower()
        if role in counts:
            counts[role] += 1

    return BackofficeSummaryOut(
        tenant_id=tenant,
        total_users=len(posture_rows),
        admins=counts["admin"],
        operators=counts["operator"],
        viewers=counts["viewer"],
        traders=counts["trader"],
        disabled=counts["disabled"],
        users_missing_2fa=missing_2fa,
        users_with_stale_secrets=stale_secrets,
    )


@router.get("/backoffice/users", response_model=list[BackofficeUserOut])
def backoffice_users(
    real_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role("admin", "operator", "viewer")),
):
    tenant = _tenant_id(current_user)
    users = db.execute(
        select(User)
        .where(User.tenant_id == tenant)
        .order_by(User.email.asc())
    ).scalars().all()

    out = []
    for u in users:
        if real_only and not _is_real_user_email(u.email):
            continue

        user_2fa = (
            db.execute(select(UserTwoFactor).where(UserTwoFactor.user_id == u.id))
            .scalar_one_or_none()
        )
        two_factor_enabled = bool(user_2fa and user_2fa.enabled)

        secrets = db.execute(
            select(ExchangeSecret.exchange).where(ExchangeSecret.user_id == u.id)
        ).all()
        secret_set = {row[0] for row in secrets}
        binance_secret = "BINANCE" in secret_set
        ibkr_secret = "IBKR" in secret_set

        assignment_rows = db.execute(
            select(StrategyAssignment.exchange, StrategyAssignment.enabled).where(
                StrategyAssignment.user_id == u.id
            )
        ).all()
        enabled_map = {exchange: bool(enabled) for exchange, enabled in assignment_rows}
        binance_enabled = bool(enabled_map.get("BINANCE", False))
        ibkr_enabled = bool(enabled_map.get("IBKR", False))

        checks = []
        if u.role in {"admin", "operator", "viewer", "trader"}:
            checks.append(two_factor_enabled)
        if binance_enabled:
            checks.append(binance_secret)
        if ibkr_enabled:
            checks.append(ibkr_secret)
        readiness = "READY" if all(checks) else "MISSING"

        out.append(
            BackofficeUserOut(
                user_id=u.id,
                email=u.email,
                role=u.role,
                two_factor_enabled=two_factor_enabled,
                binance_enabled=binance_enabled,
                ibkr_enabled=ibkr_enabled,
                binance_secret_configured=binance_secret,
                ibkr_secret_configured=ibkr_secret,
                readiness=readiness,
            )
        )
    return out


@router.get("/admin/trading-control", response_model=TradingControlOut)
def get_admin_trading_control(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    enabled = get_trading_enabled(db)
    return TradingControlOut(
        trading_enabled=enabled,
        updated_by=current_user.email,
        reason=None,
    )


@router.post("/admin/trading-control", response_model=TradingControlOut)
def update_admin_trading_control(
    payload: TradingControlUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    if payload.trading_enabled is False and len((payload.reason or "").strip()) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reason is required (min 8 chars) when disabling trading",
        )
    set_trading_enabled(db, enabled=payload.trading_enabled)
    log_audit_event(
        db,
        action="security.trading_control.updated",
        user_id=current_user.id,
        entity_type="security",
        details={
            "trading_enabled": payload.trading_enabled,
            "reason": payload.reason,
        },
    )
    db.commit()
    return TradingControlOut(
        trading_enabled=payload.trading_enabled,
        updated_by=current_user.email,
        reason=payload.reason,
    )


@router.get("/admin/risk/profiles", response_model=list[RiskProfileConfigOut])
def get_admin_risk_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    return list_risk_profiles(db)


@router.put("/admin/risk/profiles/{profile_name}", response_model=RiskProfileConfigOut)
def put_admin_risk_profile(
    profile_name: str,
    payload: RiskProfileConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    name = (profile_name or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="profile_name is required")

    if not (0.01 <= float(payload.max_risk_per_trade_pct) <= 10.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="max_risk_per_trade_pct out of range")
    if not (0.1 <= float(payload.max_daily_loss_pct) <= 50.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="max_daily_loss_pct out of range")
    if not (1 <= int(payload.max_trades_per_day) <= 200):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="max_trades_per_day out of range")
    if not (1 <= int(payload.max_open_positions) <= 100):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="max_open_positions out of range")
    if not (0.0 <= float(payload.cooldown_between_trades_minutes) <= 1440.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cooldown_between_trades_minutes out of range")
    if not (0.1 <= float(payload.max_leverage) <= 50.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="max_leverage out of range")
    if not (0.1 <= float(payload.min_rr) <= 20.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="min_rr out of range")

    out = upsert_risk_profile_config(
        db,
        profile_name=name,
        max_risk_per_trade_pct=float(payload.max_risk_per_trade_pct),
        max_daily_loss_pct=float(payload.max_daily_loss_pct),
        max_trades_per_day=int(payload.max_trades_per_day),
        max_open_positions=int(payload.max_open_positions),
        cooldown_between_trades_minutes=float(payload.cooldown_between_trades_minutes),
        max_leverage=float(payload.max_leverage),
        stop_loss_required=bool(payload.stop_loss_required),
        min_rr=float(payload.min_rr),
    )
    log_audit_event(
        db,
        action="risk.profile.config.updated",
        user_id=current_user.id,
        entity_type="risk_profile",
        details=out,
    )
    db.commit()
    return out


@router.get("/admin/strategy-runtime-policies", response_model=list[StrategyRuntimePolicyOut])
def get_admin_strategy_runtime_policies(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    return list_runtime_policies(db)


@router.put(
    "/admin/strategy-runtime-policies/{strategy_id}/{exchange}",
    response_model=StrategyRuntimePolicyOut,
)
def put_admin_strategy_runtime_policy(
    strategy_id: str,
    exchange: str,
    payload: StrategyRuntimePolicyUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    if not (0.1 <= float(payload.rr_min_bull) <= 20.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rr_min_bull out of range")
    if not (0.1 <= float(payload.rr_min_bear) <= 20.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rr_min_bear out of range")
    if not (0.1 <= float(payload.rr_min_range) <= 20.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rr_min_range out of range")
    if not (0.0 <= float(payload.min_score_pct) <= 100.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="min_score_pct out of range")
    if not (0.0 <= float(payload.score_weight_rules) <= 1.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="score_weight_rules out of range")
    if not (0.0 <= float(payload.score_weight_market) <= 1.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="score_weight_market out of range")
    if float(payload.score_weight_rules) + float(payload.score_weight_market) <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="score_weight_rules + score_weight_market must be > 0",
        )
    for name, value in {
        "max_spread_bps_bull": payload.max_spread_bps_bull,
        "max_spread_bps_bear": payload.max_spread_bps_bear,
        "max_spread_bps_range": payload.max_spread_bps_range,
        "max_slippage_bps_bull": payload.max_slippage_bps_bull,
        "max_slippage_bps_bear": payload.max_slippage_bps_bear,
        "max_slippage_bps_range": payload.max_slippage_bps_range,
    }.items():
        if not (0.0 <= float(value) <= 500.0):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{name} out of range")
    for name, value in {
        "max_hold_minutes_bull": payload.max_hold_minutes_bull,
        "max_hold_minutes_bear": payload.max_hold_minutes_bear,
        "max_hold_minutes_range": payload.max_hold_minutes_range,
    }.items():
        if not (1.0 <= float(value) <= 10080.0):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{name} out of range")

    out = upsert_runtime_policy(
        db,
        strategy_id=strategy_id,
        exchange=exchange,
        payload=payload.model_dump(),
    )
    log_audit_event(
        db,
        action="strategy.runtime_policy.updated",
        user_id=current_user.id,
        entity_type="strategy_runtime_policy",
        details=out,
    )
    db.commit()
    return out


@router.get("/admin/idempotency/stats", response_model=IdempotencyStatsOut)
def get_idempotency_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    total = int(
        db.execute(select(func.count()).select_from(IdempotencyKey)).scalar_one()
    )
    oldest = db.execute(select(func.min(IdempotencyKey.created_at))).scalar_one_or_none()
    newest = db.execute(select(func.max(IdempotencyKey.created_at))).scalar_one_or_none()
    log_audit_event(
        db,
        action="security.idempotency.stats.read",
        user_id=current_user.id,
        entity_type="security",
        details={"records_total": total},
    )
    db.commit()
    return IdempotencyStatsOut(
        records_total=total,
        max_age_days=int(settings.IDEMPOTENCY_KEY_MAX_AGE_DAYS),
        oldest_record_at=oldest.isoformat() if oldest else None,
        newest_record_at=newest.isoformat() if newest else None,
    )


@router.post("/admin/idempotency/cleanup", response_model=IdempotencyCleanupOut)
def post_idempotency_cleanup(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    deleted = cleanup_old_idempotency_keys(db)
    log_audit_event(
        db,
        action="security.idempotency.cleanup",
        user_id=current_user.id,
        entity_type="security",
        details={
            "deleted": deleted,
            "max_age_days": int(settings.IDEMPOTENCY_KEY_MAX_AGE_DAYS),
        },
    )
    db.commit()
    return IdempotencyCleanupOut(
        deleted=int(deleted),
        max_age_days=int(settings.IDEMPOTENCY_KEY_MAX_AGE_DAYS),
    )


@router.get("/audit/me", response_model=list[AuditOut])
def my_audit(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == current_user.id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return rows


@router.get("/audit/all", response_model=list[AuditOut])
def all_audit(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    tenant_ids = (
        select(User.id).where(User.tenant_id == _tenant_id(current_user))
    )
    rows = (
        db.execute(
            select(AuditLog)
            .where(AuditLog.user_id.in_(tenant_ids))
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return rows


@router.get("/admin/auto-pick/report", response_model=AutoPickReportOut)
def auto_pick_report(
    hours: int = 2,
    limit: int = 500,
    interval_minutes: int = 5,
    direction: str = "ALL",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    def _friendly_check_name(raw: str) -> str:
        key = str(raw or "").strip()
        mapping = {
            "short_not_supported_for_exchange": "SHORT no soportado para este exchange",
            "short_mtf_1d_strong_bear": "SHORT: tendencia 1D no suficientemente bajista",
            "short_mtf_4h_strong_bear": "SHORT: tendencia 4H no suficientemente bajista",
            "short_mtf_1h_bear": "SHORT: tendencia 1H no bajista",
            "short_micro_15m_confirm": "SHORT: micro tendencia 15m no confirma",
            "long_micro_15m_confirm": "LONG: micro tendencia 15m no confirma",
            "short_requires_green_liquidity": "SHORT: liquidez no green",
            "strategy_rr_min": "RR por debajo del minimo",
            "score_below_min_threshold": "Score por debajo del minimo",
            "liq_volume_24h": "Liquidez: volumen 24h insuficiente",
            "liq_spread_bps": "Liquidez: spread alto",
            "liq_slippage_bps": "Liquidez: slippage alto",
            "effective_liquidity_failed": "Liquidez efectiva no apta",
            "real_guard_email_allowlist": "Ejecucion real bloqueada: usuario fuera de allowlist",
            "real_guard_exchange_allowlist": "Ejecucion real bloqueada: exchange fuera de allowlist",
            "real_guard_symbol_allowlist": "Ejecucion real bloqueada: simbolo fuera de allowlist",
            "real_guard_binance_quote": "Ejecucion real bloqueada: quote distinta a USDT",
            "real_guard_exit_plan_required": "Ejecucion real bloqueada: plan de salida requerido",
            "real_guard_exit_plan_rr_below_minimum": "Ejecucion real bloqueada: RR de salida por debajo del minimo",
            "real_guard_exit_plan_price_unavailable": "Ejecucion real bloqueada: no hay precio para construir plan de salida",
            "real_guard_exit_plan_invalid_risk": "Ejecucion real bloqueada: riesgo invalido para plan de salida",
            "market_regime_allowed": "Regimen de mercado no permitido",
            "max_leverage": "Leverage supera el maximo",
            "ibkr_in_rth": "IBKR fuera de horario RTH",
            "ibkr_no_macro_block": "Bloqueo por evento macro",
            "ibkr_no_earnings_24h": "Bloqueo por earnings <24h",
        }
        return mapping.get(key, key)

    hours = max(1, min(hours, 48))
    limit = max(1, min(limit, 2000))
    interval_minutes = max(1, min(interval_minutes, 60))
    direction_norm = (direction or "ALL").upper().strip()
    if direction_norm not in {"ALL", "LONG", "SHORT", "BOTH"}:
        direction_norm = "ALL"
    now = datetime.now(timezone.utc)
    from_dt = now - timedelta(hours=hours)
    tenant_ids = select(User.id).where(User.tenant_id == _tenant_id(current_user))
    user_rows = (
        db.execute(select(User.id, User.email).where(User.tenant_id == _tenant_id(current_user)))
        .all()
    )
    email_by_id = {uid: email for uid, email in user_rows}

    rows = (
        db.execute(
            select(AuditLog)
            .where(
                AuditLog.user_id.in_(tenant_ids),
                AuditLog.action == "pretrade.auto_pick.completed",
                AuditLog.created_at >= from_dt,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )

    parsed_rows: list[tuple[AuditLog, dict]] = []
    decision_ids: set[str] = set()
    for r in rows:
        try:
            details = json.loads(r.details) if r.details else {}
        except Exception:
            details = {}
        parsed_rows.append((r, details))
        decision_id = str(details.get("learning_decision_id") or "").strip()
        if decision_id:
            decision_ids.add(decision_id)

    outcome_by_decision: dict[str, LearningDecisionOutcome] = {}
    if decision_ids:
        outcomes = (
            db.execute(
                select(LearningDecisionOutcome).where(
                    LearningDecisionOutcome.decision_id.in_(decision_ids)
                )
            )
            .scalars()
            .all()
        )
        for o in outcomes:
            key = str(o.decision_id or "").strip()
            if not key:
                continue
            prev = outcome_by_decision.get(key)
            if prev is None:
                outcome_by_decision[key] = o
                continue
            prev_labeled = str(prev.outcome_status or "").lower() == "labeled"
            new_labeled = str(o.outcome_status or "").lower() == "labeled"
            if (not prev_labeled and new_labeled) or (
                prev.horizon_minutes is not None
                and o.horizon_minutes is not None
                and int(o.horizon_minutes) < int(prev.horizon_minutes)
            ):
                outcome_by_decision[key] = o

    out_rows = []
    for r, details in parsed_rows:
        row_direction = str(details.get("requested_direction") or "LONG").upper().strip()
        if direction_norm != "ALL" and row_direction != direction_norm:
            continue
        created_at = r.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        created_at = (created_at or now).astimezone(timezone.utc)
        minute_bucket = (created_at.minute // interval_minutes) * interval_minutes
        bucket = created_at.replace(minute=minute_bucket, second=0, microsecond=0)
        dry_run = bool(details.get("dry_run", True))
        decision = str(details.get("decision") or "unknown")
        selected = bool(details.get("selected", False))
        bought = decision == "executed_test_order"
        reason = decision
        if not selected:
            top_failed = details.get("top_failed_checks") or []
            if isinstance(top_failed, list) and top_failed:
                first = _friendly_check_name(str(top_failed[0]))
                rest = max(0, len(top_failed) - 1)
                reason = f"no_compra: {first}" + (f" (+{rest})" if rest else "")
            else:
                reason = "no_compra: sin candidato aprobado"
        top_symbol = details.get("top_candidate_symbol")
        top_score = details.get("top_candidate_score")
        selected_score = details.get("selected_score")
        top_score_rules = details.get("top_candidate_score_rules")
        selected_score_rules = details.get("selected_score_rules")
        top_score_market = details.get("top_candidate_score_market")
        selected_score_market = details.get("selected_score_market")
        selected_trend_score = details.get("selected_trend_score")
        selected_trend_score_1d = details.get("selected_trend_score_1d")
        selected_trend_score_4h = details.get("selected_trend_score_4h")
        selected_trend_score_1h = details.get("selected_trend_score_1h")
        selected_micro_trend_15m = details.get("selected_micro_trend_15m")
        top_candidate_trend_score = details.get("top_candidate_trend_score")
        top_candidate_trend_score_1d = details.get("top_candidate_trend_score_1d")
        top_candidate_trend_score_4h = details.get("top_candidate_trend_score_4h")
        top_candidate_trend_score_1h = details.get("top_candidate_trend_score_1h")
        top_candidate_micro_trend_15m = details.get("top_candidate_micro_trend_15m")
        decision_id = str(details.get("learning_decision_id") or "").strip()
        predicted_hit_pct = details.get("selected_learning_prob_hit_pct")
        if predicted_hit_pct is None:
            predicted_hit_pct = details.get("top_candidate_learning_prob_hit_pct")
        predicted_positive = None
        if predicted_hit_pct is not None:
            try:
                predicted_hit_pct = round(float(predicted_hit_pct), 2)
                predicted_positive = float(predicted_hit_pct) >= 50.0
            except Exception:
                predicted_hit_pct = None
                predicted_positive = None
        outcome_row = outcome_by_decision.get(decision_id) if decision_id else None
        outcome_status = outcome_row.outcome_status if outcome_row is not None else None
        realized_hit = None
        if outcome_row is not None and str(outcome_status or "").lower() == "labeled":
            realized_hit = outcome_row.hit
        prediction_vs_real = _resolve_prediction_vs_real_state(
            predicted_positive=predicted_positive,
            outcome_status=outcome_status,
            realized_hit=realized_hit,
        )
        out_rows.append(
            AutoPickReportItemOut(
                timestamp=created_at.isoformat(),
                bucket_5m=bucket.isoformat(),
                user_email=email_by_id.get(r.user_id, "unknown"),
                exchange=str(details.get("exchange") or "UNKNOWN"),
                dry_run=dry_run,
                selected=selected,
                bought=bought,
                symbol=top_symbol if top_symbol is not None else details.get("selected_symbol"),
                side=details.get("selected_side"),
                qty=details.get("selected_qty"),
                score=top_score if top_score is not None else selected_score,
                score_rules=top_score_rules if top_score_rules is not None else selected_score_rules,
                score_market=top_score_market if top_score_market is not None else selected_score_market,
                trend_score=(top_candidate_trend_score if top_candidate_trend_score is not None else selected_trend_score),
                trend_score_1d=(top_candidate_trend_score_1d if top_candidate_trend_score_1d is not None else selected_trend_score_1d),
                trend_score_4h=(top_candidate_trend_score_4h if top_candidate_trend_score_4h is not None else selected_trend_score_4h),
                trend_score_1h=(top_candidate_trend_score_1h if top_candidate_trend_score_1h is not None else selected_trend_score_1h),
                micro_trend_15m=(top_candidate_micro_trend_15m if top_candidate_micro_trend_15m is not None else selected_micro_trend_15m),
                top_candidate_trend_score=top_candidate_trend_score,
                top_candidate_trend_score_1d=top_candidate_trend_score_1d,
                top_candidate_trend_score_4h=top_candidate_trend_score_4h,
                top_candidate_trend_score_1h=top_candidate_trend_score_1h,
                top_candidate_micro_trend_15m=top_candidate_micro_trend_15m,
                avg_score=details.get("avg_score"),
                avg_score_rules=details.get("avg_score_rules"),
                avg_score_market=details.get("avg_score_market"),
                market_regime=details.get("selected_market_regime"),
                predicted_hit_pct=predicted_hit_pct,
                predicted_positive=predicted_positive,
                outcome_status=outcome_status,
                realized_hit=realized_hit,
                prediction_vs_real=prediction_vs_real,
                decision=decision,
                reason=reason,
                scanned_assets=int(details.get("scanned_assets") or 0),
            )
        )

    return AutoPickReportOut(
        generated_at=now.isoformat(),
        hours=hours,
        window_from=from_dt.isoformat(),
        window_to=now.isoformat(),
        interval_minutes=interval_minutes,
        rows=out_rows,
    )


@router.post("/admin/market-monitor/tick")
def admin_market_monitor_tick(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    out = run_market_monitor_tick_for_tenant(
        db=db,
        tenant_id=_tenant_id(current_user),
    )
    log_audit_event(
        db,
        action="market.monitor.tick",
        user_id=current_user.id,
        entity_type="market_monitor",
        details=out,
    )
    db.commit()
    return out


@router.get("/admin/market-monitor/report", response_model=MarketTrendMonitorOut)
def admin_market_monitor_report(
    hours: int = 2,
    limit: int = 300,
    exchange: str = "ALL",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    hours = max(1, min(hours, 48))
    limit = max(1, min(limit, 5000))
    now = datetime.now(timezone.utc)
    from_dt = now - timedelta(hours=hours)
    exchange_norm = (exchange or "ALL").upper().strip()
    q = select(MarketTrendSnapshot).where(
        MarketTrendSnapshot.tenant_id == _tenant_id(current_user),
        MarketTrendSnapshot.created_at >= from_dt,
    )
    if exchange_norm in {"BINANCE", "IBKR"}:
        q = q.where(MarketTrendSnapshot.exchange == exchange_norm)
    else:
        exchange_norm = "ALL"
    rows = db.execute(q.order_by(MarketTrendSnapshot.created_at.desc()).limit(limit)).scalars().all()
    out_rows: list[MarketTrendSnapshotOut] = []
    for r in rows:
        if (r.exchange or "").upper() == "BINANCE" and not _is_binance_monitor_row_allowed(
            str(r.symbol or ""),
            float(r.volume_24h_usdt or 0.0),
        ):
            continue
        out_rows.append(
            MarketTrendSnapshotOut(
                timestamp=(r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat(),
                bucket_5m=(r.bucket_5m if r.bucket_5m.tzinfo else r.bucket_5m.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat(),
                exchange=r.exchange,
                symbol=r.symbol,
                regime=r.regime,
                confidence=float(r.confidence),
                trend_score=float(r.trend_score),
                momentum_score=float(r.momentum_score),
                atr_pct=float(r.atr_pct),
                volume_24h_usdt=float(r.volume_24h_usdt),
                source=r.source,
            )
        )
    return MarketTrendMonitorOut(
        generated_at=now.isoformat(),
        hours=hours,
        window_from=from_dt.isoformat(),
        window_to=now.isoformat(),
        exchange=exchange_norm,
        total_rows=len(out_rows),
        rows=out_rows,
    )


@router.get("/admin/audit/export", response_model=AuditExportOut)
def export_audit(
    limit: int = 500,
    from_iso: Optional[str] = None,
    to_iso: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    tenant = _tenant_id(current_user)
    tenant_ids = select(User.id).where(User.tenant_id == tenant)

    q = select(AuditLog).where(AuditLog.user_id.in_(tenant_ids))
    if from_iso:
        try:
            from_dt = datetime.fromisoformat(from_iso.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid from_iso")
        q = q.where(AuditLog.created_at >= from_dt)
    if to_iso:
        try:
            to_dt = datetime.fromisoformat(to_iso.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid to_iso")
        q = q.where(AuditLog.created_at <= to_dt)

    rows = (
        db.execute(
            q.order_by(AuditLog.created_at.desc()).limit(max(1, min(limit, 5000)))
        )
        .scalars()
        .all()
    )
    records = [AuditOut.model_validate(r) for r in rows]
    meta = AuditExportMetaOut(
        exported_at=datetime.now(timezone.utc).isoformat(),
        exported_by=current_user.email,
        tenant_id=tenant,
        limit=max(1, min(limit, 5000)),
        from_iso=from_iso,
        to_iso=to_iso,
        records_count=len(records),
        algorithm="sha256+hmac-sha256",
    )

    payload = {
        "meta": meta.model_dump(),
        "records": [r.model_dump(mode="json") for r in records],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    payload_sha256 = hashlib.sha256(canonical).hexdigest()
    signing_key = (settings.AUDIT_EXPORT_SIGNING_KEY or settings.SECRET_KEY).encode("utf-8")
    signature = hmac.new(signing_key, canonical, hashlib.sha256).hexdigest()

    log_audit_event(
        db,
        action="security.audit.export",
        user_id=current_user.id,
        entity_type="security",
        details={
            "tenant_id": tenant,
            "records_count": len(records),
            "from_iso": from_iso,
            "to_iso": to_iso,
            "limit": max(1, min(limit, 5000)),
        },
    )
    db.commit()

    return AuditExportOut(
        meta=meta,
        records=records,
        payload_sha256=payload_sha256,
        signature_hmac_sha256=signature,
    )


@router.get("/risk/daily-compare")
def daily_risk_compare(
    real_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    today = today_colombia()
    users = db.execute(
        select(User)
        .where(User.tenant_id == _tenant_id(current_user))
        .order_by(User.email.asc())
    ).scalars().all()
    rows = []

    for user in users:
        email_l = (user.email or "").lower()
        if real_only and (
            email_l.startswith("smoke.")
            or email_l.startswith("disabled_")
            or email_l.endswith("@example.com")
            or email_l.endswith("@example.invalid")
        ):
            continue

        profile = resolve_risk_profile(db, user.id, user.email)
        dr = (
            db.execute(
                select(DailyRiskState).where(
                    DailyRiskState.user_id == user.id,
                    DailyRiskState.day == today,
                )
            )
            .scalar_one_or_none()
        )

        open_positions = db.execute(
            select(func.count())
            .select_from(Position)
            .where(Position.user_id == user.id, Position.status == "OPEN")
        ).scalar_one()
        closed_today = db.execute(
            select(func.count())
            .select_from(Position)
            .where(
                Position.user_id == user.id,
                Position.status == "CLOSED",
                func.date(Position.closed_at) == str(today),
            )
        ).scalar_one()
        blocked_today = db.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.user_id == user.id,
                AuditLog.action.like("position.open.blocked.%"),
                func.date(AuditLog.created_at) == str(today),
            )
        ).scalar_one()

        max_trades = int(dr.max_trades) if dr else int(profile["max_trades_per_day"])
        daily_stop = float(dr.daily_stop) if dr else -abs(float(profile["max_daily_loss_pct"]))
        trades_today = int(dr.trades_today) if dr else 0
        realized_pnl_today = float(dr.realized_pnl_today) if dr else 0.0

        rows.append(
            {
                "user_id": user.id,
                "email": user.email,
                "role": user.role,
                "risk_profile": profile["profile_name"],
                "limits": {
                    "max_risk_per_trade_pct": float(profile["max_risk_per_trade_pct"]),
                    "max_daily_loss_pct": float(profile["max_daily_loss_pct"]),
                    "max_trades_per_day": int(profile["max_trades_per_day"]),
                    "max_open_positions": int(profile["max_open_positions"]),
                    "cooldown_between_trades_minutes": float(profile["cooldown_between_trades_minutes"]),
                    "min_rr": float(profile["min_rr"]),
                },
                "today": {
                    "day": str(today),
                    "trades_today": trades_today,
                    "realized_pnl_today": realized_pnl_today,
                    "daily_stop_threshold": daily_stop,
                    "open_positions_now": int(open_positions),
                    "closed_positions_today": int(closed_today),
                    "blocked_open_attempts_today": int(blocked_today),
                    "trades_utilization_pct": round((trades_today / max_trades) * 100.0, 2) if max_trades > 0 else 0.0,
                },
            }
        )

    return {
        "day": str(today),
        "generated_for": current_user.email,
        "users": rows,
    }


@router.post("/strategy/assign", response_model=StrategyAssignOut)
def assign_strategy(
    payload: StrategyAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    user = db.execute(
        select(User).where(
            User.email == payload.user_email,
            User.tenant_id == _tenant_id(current_user),
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    row = upsert_strategy_assignment(
        db=db,
        user_id=user.id,
        exchange=payload.exchange,
        strategy_id=payload.strategy_id,
        enabled=payload.enabled,
    )
    db.flush()
    log_audit_event(
        db,
        action="strategy.assignment.updated",
        user_id=current_user.id,
        entity_type="strategy_assignment",
        entity_id=row.id,
        details={
            "target_user_id": user.id,
            "target_user_email": user.email,
            "exchange": row.exchange,
            "strategy_id": row.strategy_id,
            "enabled": row.enabled,
        },
    )
    db.commit()
    return {
        "user_id": user.id,
        "user_email": user.email,
        "exchange": row.exchange,
        "strategy_id": row.strategy_id,
        "enabled": bool(row.enabled),
    }


@router.get("/strategy/assignments", response_model=list[StrategyAssignmentOut])
def list_strategy_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    rows = db.execute(
        select(StrategyAssignment, User)
        .join(User, StrategyAssignment.user_id == User.id)
        .where(User.tenant_id == _tenant_id(current_user))
        .order_by(User.email.asc(), StrategyAssignment.exchange.asc())
    ).all()
    return [
        {
            "user_id": strategy.user_id,
            "user_email": user.email,
            "exchange": strategy.exchange,
            "strategy_id": strategy.strategy_id,
            "enabled": bool(strategy.enabled),
        }
        for strategy, user in rows
    ]


@router.post("/execution/pretrade/binance/check", response_model=PretradeCheckOut)
def pretrade_binance_check(
    payload: PretradeCheckRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="pretrade_check",
        exchange="BINANCE",
    )
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
    )
    assert_exposure_limits(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
        symbol=payload.symbol,
        qty=payload.qty,
        price_estimate=0.0,
    )
    req_payload = payload.model_dump()
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/pretrade/binance/check",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached

    result = _evaluate_pretrade_for_user(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
        payload=payload,
    )
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/pretrade/binance/check",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=result,
    )
    return result


@router.post("/execution/pretrade/ibkr/check", response_model=PretradeCheckOut)
def pretrade_ibkr_check(
    payload: PretradeCheckRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="pretrade_check",
        exchange="IBKR",
    )
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="IBKR",
    )
    assert_exposure_limits(
        db=db,
        current_user=current_user,
        exchange="IBKR",
        symbol=payload.symbol,
        qty=payload.qty,
        price_estimate=0.0,
    )
    req_payload = payload.model_dump()
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/pretrade/ibkr/check",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached

    result = _evaluate_pretrade_for_user(
        db=db,
        current_user=current_user,
        exchange="IBKR",
        payload=payload,
    )
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/pretrade/ibkr/check",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=result,
    )
    return result


@router.post("/execution/pretrade/binance/scan", response_model=PretradeScanOut)
def pretrade_binance_scan(
    payload: PretradeScanRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="pretrade_scan",
        exchange="BINANCE",
    )
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
    )
    req_payload = payload.model_dump()
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/pretrade/binance/scan",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached
    out = _scan_pretrade_candidates(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
        payload=payload,
    )
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/pretrade/binance/scan",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=out,
    )
    log_audit_event(
        db,
        action="pretrade.scan.completed",
        user_id=current_user.id,
        entity_type="pretrade_scan",
        details={
            "exchange": "BINANCE",
            "scanned_assets": out["scanned_assets"],
            "returned_assets": out["returned_assets"],
            "passed_assets": out["passed_assets"],
            "blocked_assets": out["blocked_assets"],
            "duration_ms_total": out["duration_ms_total"],
            "duration_ms_avg": out["duration_ms_avg"],
        },
    )
    db.commit()
    return out


@router.post("/execution/pretrade/ibkr/scan", response_model=PretradeScanOut)
def pretrade_ibkr_scan(
    payload: PretradeScanRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="pretrade_scan",
        exchange="IBKR",
    )
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="IBKR",
    )
    req_payload = payload.model_dump()
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/pretrade/ibkr/scan",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached
    out = _scan_pretrade_candidates(
        db=db,
        current_user=current_user,
        exchange="IBKR",
        payload=payload,
    )
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/pretrade/ibkr/scan",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=out,
    )
    log_audit_event(
        db,
        action="pretrade.scan.completed",
        user_id=current_user.id,
        entity_type="pretrade_scan",
        details={
            "exchange": "IBKR",
            "scanned_assets": out["scanned_assets"],
            "returned_assets": out["returned_assets"],
            "passed_assets": out["passed_assets"],
            "blocked_assets": out["blocked_assets"],
            "duration_ms_total": out["duration_ms_total"],
            "duration_ms_avg": out["duration_ms_avg"],
        },
    )
    db.commit()
    return out


@router.post("/execution/pretrade/binance/auto-pick", response_model=PretradeAutoPickOut)
def pretrade_binance_auto_pick(
    payload: PretradeAutoPickRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="pretrade_auto_pick",
        exchange="BINANCE",
    )
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
    )
    _require_idempotency_for_auto_pick_execution(
        payload=payload,
        idempotency_key=idempotency_key,
    )
    req_payload = payload.model_dump()
    log_audit_event(
        db,
        action="pretrade.auto_pick.started",
        user_id=current_user.id,
        entity_type="pretrade_auto_pick",
        details={
            "exchange": "BINANCE",
            "dry_run": bool(payload.dry_run),
            "requested_direction": payload.direction,
        },
    )
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/pretrade/binance/auto-pick",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached
    out = _auto_pick_from_scan(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
        payload=payload,
        idempotency_key=idempotency_key,
    )
    idempotency_handled = bool(out.pop("_idempotency_handled", False)) if isinstance(out, dict) else False
    if not idempotency_handled:
        store_idempotent_response(
            db,
            user_id=current_user.id,
            endpoint="/ops/execution/pretrade/binance/auto-pick",
            idempotency_key=idempotency_key,
            request_payload=req_payload,
            response_payload=out,
        )
    log_audit_event(
        db,
        action="pretrade.auto_pick.completed",
        user_id=current_user.id,
        entity_type="pretrade_auto_pick",
        details={
            "exchange": "BINANCE",
            "dry_run": bool(payload.dry_run),
            "requested_direction": out.get("requested_direction", payload.direction),
            "decision": out["decision"],
            "execution_status": out.get("execution_status"),
            "selected": out["selected"],
            "selected_symbol": out["selected_symbol"],
            "selected_side": out["selected_side"],
            "selected_qty": out["selected_qty"],
            "selected_score": out["selected_score"],
            "selected_score_base": out.get("selected_score_base"),
            "selected_score_rules": out.get("selected_score_rules"),
            "selected_score_market": out.get("selected_score_market"),
            "selected_learning_prob_hit_pct": out.get("selected_learning_prob_hit_pct"),
            "selected_learning_samples": out.get("selected_learning_samples"),
            "selected_learning_score": out.get("selected_learning_score"),
            "selected_learning_delta_points": out.get("selected_learning_delta_points"),
            "selected_trend_score": out.get("selected_trend_score"),
            "selected_trend_score_1d": out.get("selected_trend_score_1d"),
            "selected_trend_score_4h": out.get("selected_trend_score_4h"),
            "selected_trend_score_1h": out.get("selected_trend_score_1h"),
            "selected_micro_trend_15m": out.get("selected_micro_trend_15m"),
            "selected_market_regime": out["selected_market_regime"],
            "selected_liquidity_state": out.get("selected_liquidity_state"),
            "selected_size_multiplier": out.get("selected_size_multiplier"),
            "top_candidate_symbol": out.get("top_candidate_symbol"),
            "top_candidate_score": out.get("top_candidate_score"),
            "top_candidate_score_base": out.get("top_candidate_score_base"),
            "top_candidate_score_rules": out.get("top_candidate_score_rules"),
            "top_candidate_score_market": out.get("top_candidate_score_market"),
            "top_candidate_learning_prob_hit_pct": out.get("top_candidate_learning_prob_hit_pct"),
            "top_candidate_learning_samples": out.get("top_candidate_learning_samples"),
            "top_candidate_learning_score": out.get("top_candidate_learning_score"),
            "top_candidate_learning_delta_points": out.get("top_candidate_learning_delta_points"),
            "top_candidate_trend_score": out.get("top_candidate_trend_score"),
            "top_candidate_trend_score_1d": out.get("top_candidate_trend_score_1d"),
            "top_candidate_trend_score_4h": out.get("top_candidate_trend_score_4h"),
            "top_candidate_trend_score_1h": out.get("top_candidate_trend_score_1h"),
            "top_candidate_micro_trend_15m": out.get("top_candidate_micro_trend_15m"),
            "avg_score": out.get("avg_score"),
            "avg_score_base": out.get("avg_score_base"),
            "avg_score_rules": out.get("avg_score_rules"),
            "avg_score_market": out.get("avg_score_market"),
            "learning_decision_id": out.get("learning_decision_id"),
            "top_failed_checks": out.get("top_failed_checks", []),
            "scanned_assets": out["scan"]["scanned_assets"],
        },
    )
    db.commit()
    return out


@router.post("/execution/pretrade/ibkr/auto-pick", response_model=PretradeAutoPickOut)
def pretrade_ibkr_auto_pick(
    payload: PretradeAutoPickRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="pretrade_auto_pick",
        exchange="IBKR",
    )
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="IBKR",
    )
    _require_idempotency_for_auto_pick_execution(
        payload=payload,
        idempotency_key=idempotency_key,
    )
    req_payload = payload.model_dump()
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/pretrade/ibkr/auto-pick",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached
    out = _auto_pick_from_scan(
        db=db,
        current_user=current_user,
        exchange="IBKR",
        payload=payload,
        idempotency_key=idempotency_key,
    )
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/pretrade/ibkr/auto-pick",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=out,
    )
    log_audit_event(
        db,
        action="pretrade.auto_pick.completed",
        user_id=current_user.id,
        entity_type="pretrade_auto_pick",
        details={
            "exchange": "IBKR",
            "dry_run": bool(payload.dry_run),
            "requested_direction": out.get("requested_direction", payload.direction),
            "decision": out["decision"],
            "execution_status": out.get("execution_status"),
            "selected": out["selected"],
            "selected_symbol": out["selected_symbol"],
            "selected_side": out["selected_side"],
            "selected_qty": out["selected_qty"],
            "selected_score": out["selected_score"],
            "selected_score_base": out.get("selected_score_base"),
            "selected_score_rules": out.get("selected_score_rules"),
            "selected_score_market": out.get("selected_score_market"),
            "selected_learning_prob_hit_pct": out.get("selected_learning_prob_hit_pct"),
            "selected_learning_samples": out.get("selected_learning_samples"),
            "selected_learning_score": out.get("selected_learning_score"),
            "selected_learning_delta_points": out.get("selected_learning_delta_points"),
            "selected_trend_score": out.get("selected_trend_score"),
            "selected_trend_score_1d": out.get("selected_trend_score_1d"),
            "selected_trend_score_4h": out.get("selected_trend_score_4h"),
            "selected_trend_score_1h": out.get("selected_trend_score_1h"),
            "selected_micro_trend_15m": out.get("selected_micro_trend_15m"),
            "selected_market_regime": out["selected_market_regime"],
            "selected_liquidity_state": out.get("selected_liquidity_state"),
            "selected_size_multiplier": out.get("selected_size_multiplier"),
            "top_candidate_symbol": out.get("top_candidate_symbol"),
            "top_candidate_score": out.get("top_candidate_score"),
            "top_candidate_score_base": out.get("top_candidate_score_base"),
            "top_candidate_score_rules": out.get("top_candidate_score_rules"),
            "top_candidate_score_market": out.get("top_candidate_score_market"),
            "top_candidate_learning_prob_hit_pct": out.get("top_candidate_learning_prob_hit_pct"),
            "top_candidate_learning_samples": out.get("top_candidate_learning_samples"),
            "top_candidate_learning_score": out.get("top_candidate_learning_score"),
            "top_candidate_learning_delta_points": out.get("top_candidate_learning_delta_points"),
            "top_candidate_trend_score": out.get("top_candidate_trend_score"),
            "top_candidate_trend_score_1d": out.get("top_candidate_trend_score_1d"),
            "top_candidate_trend_score_4h": out.get("top_candidate_trend_score_4h"),
            "top_candidate_trend_score_1h": out.get("top_candidate_trend_score_1h"),
            "top_candidate_micro_trend_15m": out.get("top_candidate_micro_trend_15m"),
            "avg_score": out.get("avg_score"),
            "avg_score_base": out.get("avg_score_base"),
            "avg_score_rules": out.get("avg_score_rules"),
            "avg_score_market": out.get("avg_score_market"),
            "learning_decision_id": out.get("learning_decision_id"),
            "top_failed_checks": out.get("top_failed_checks", []),
            "scanned_assets": out["scan"]["scanned_assets"],
        },
    )
    db.commit()
    return out


@router.post("/admin/auto-pick/tick")
def admin_auto_pick_tick(
    dry_run: bool = True,
    top_n: int = 10,
    direction: str = "LONG",
    real_only: bool = True,
    include_service_users: bool = False,
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    out = run_auto_pick_tick_for_tenant(
        db=db,
        tenant_id=_tenant_id(current_user),
        dry_run=dry_run,
        top_n=top_n,
        direction=direction,
        real_only=real_only,
        include_service_users=include_service_users,
        user_email=user_email,
    )
    db.commit()
    return out


def run_auto_pick_tick_for_tenant(
    db: Session,
    tenant_id: str,
    dry_run: bool = True,
    top_n: int = 10,
    direction: str = "LONG",
    real_only: bool = True,
    include_service_users: bool = False,
    user_email: Optional[str] = None,
):
    top_n = max(1, min(int(top_n), 100))
    direction = str(direction or "LONG").upper().strip()
    if direction not in {"LONG", "SHORT", "BOTH"}:
        direction = "LONG"
    users = (
        db.execute(select(User).where(User.tenant_id == tenant_id).order_by(User.email.asc()))
        .scalars()
        .all()
    )
    target_email = (user_email or "").strip().lower()
    executed = []
    for u in users:
        if target_email and (u.email or "").strip().lower() != target_email:
            continue
        if u.role not in {"admin", "trader"}:
            continue
        if real_only and not _is_real_user_email(u.email):
            continue
        if (not include_service_users) and _is_service_user_email(u.email):
            continue
        for exchange in ("BINANCE", "IBKR"):
            if not is_exchange_enabled_for_user(db=db, user_id=u.id, exchange=exchange):
                continue
            out = _auto_pick_from_scan(
                db=db,
                current_user=u,
                exchange=exchange,
                payload=PretradeAutoPickRequest(top_n=top_n, dry_run=dry_run, direction=direction),
                idempotency_key=None,
            )
            log_audit_event(
                db,
                action="pretrade.auto_pick.completed",
                user_id=u.id,
                entity_type="pretrade_auto_pick",
                details={
                    "exchange": exchange,
                    "dry_run": bool(dry_run),
                    "requested_direction": out.get("requested_direction", direction),
                    "decision": out["decision"],
                    "selected": out["selected"],
                    "selected_symbol": out["selected_symbol"],
                    "selected_side": out["selected_side"],
                    "selected_qty": out["selected_qty"],
                    "selected_score": out["selected_score"],
                    "selected_score_base": out.get("selected_score_base"),
                    "selected_score_rules": out.get("selected_score_rules"),
                    "selected_score_market": out.get("selected_score_market"),
                    "selected_learning_prob_hit_pct": out.get("selected_learning_prob_hit_pct"),
                    "selected_learning_samples": out.get("selected_learning_samples"),
                    "selected_learning_score": out.get("selected_learning_score"),
                    "selected_learning_delta_points": out.get("selected_learning_delta_points"),
                    "selected_trend_score": out.get("selected_trend_score"),
                    "selected_trend_score_1d": out.get("selected_trend_score_1d"),
                    "selected_trend_score_4h": out.get("selected_trend_score_4h"),
                    "selected_trend_score_1h": out.get("selected_trend_score_1h"),
                    "selected_micro_trend_15m": out.get("selected_micro_trend_15m"),
                    "selected_market_regime": out["selected_market_regime"],
                    "selected_liquidity_state": out.get("selected_liquidity_state"),
                    "selected_size_multiplier": out.get("selected_size_multiplier"),
                    "top_candidate_symbol": out.get("top_candidate_symbol"),
                    "top_candidate_score": out.get("top_candidate_score"),
                    "top_candidate_score_base": out.get("top_candidate_score_base"),
                    "top_candidate_score_rules": out.get("top_candidate_score_rules"),
                    "top_candidate_score_market": out.get("top_candidate_score_market"),
                    "top_candidate_learning_prob_hit_pct": out.get("top_candidate_learning_prob_hit_pct"),
                    "top_candidate_learning_samples": out.get("top_candidate_learning_samples"),
                    "top_candidate_learning_score": out.get("top_candidate_learning_score"),
                    "top_candidate_learning_delta_points": out.get("top_candidate_learning_delta_points"),
                    "top_candidate_trend_score": out.get("top_candidate_trend_score"),
                    "top_candidate_trend_score_1d": out.get("top_candidate_trend_score_1d"),
                    "top_candidate_trend_score_4h": out.get("top_candidate_trend_score_4h"),
                    "top_candidate_trend_score_1h": out.get("top_candidate_trend_score_1h"),
                    "top_candidate_micro_trend_15m": out.get("top_candidate_micro_trend_15m"),
                    "avg_score": out.get("avg_score"),
                    "avg_score_base": out.get("avg_score_base"),
                    "avg_score_rules": out.get("avg_score_rules"),
                    "avg_score_market": out.get("avg_score_market"),
                    "learning_decision_id": out.get("learning_decision_id"),
                    "top_failed_checks": out.get("top_failed_checks", []),
                    "scanned_assets": out["scan"]["scanned_assets"],
                },
            )
            executed.append(
                {
                    "user_email": u.email,
                    "exchange": exchange,
                    "requested_direction": out.get("requested_direction", direction),
                    "decision": out["decision"],
                    "selected": out["selected"],
                    "selected_symbol": out["selected_symbol"],
                    "selected_score": out["selected_score"],
                    "selected_score_base": out.get("selected_score_base"),
                    "selected_score_rules": out.get("selected_score_rules"),
                    "selected_score_market": out.get("selected_score_market"),
                    "selected_learning_prob_hit_pct": out.get("selected_learning_prob_hit_pct"),
                    "selected_learning_samples": out.get("selected_learning_samples"),
                    "selected_learning_score": out.get("selected_learning_score"),
                    "selected_learning_delta_points": out.get("selected_learning_delta_points"),
                    "selected_trend_score": out.get("selected_trend_score"),
                    "selected_trend_score_1d": out.get("selected_trend_score_1d"),
                    "selected_trend_score_4h": out.get("selected_trend_score_4h"),
                    "selected_trend_score_1h": out.get("selected_trend_score_1h"),
                    "selected_micro_trend_15m": out.get("selected_micro_trend_15m"),
                    "selected_liquidity_state": out.get("selected_liquidity_state"),
                    "selected_size_multiplier": out.get("selected_size_multiplier"),
                    "top_candidate_symbol": out.get("top_candidate_symbol"),
                    "top_candidate_score": out.get("top_candidate_score"),
                    "top_candidate_score_base": out.get("top_candidate_score_base"),
                    "top_candidate_score_rules": out.get("top_candidate_score_rules"),
                    "top_candidate_score_market": out.get("top_candidate_score_market"),
                    "top_candidate_learning_prob_hit_pct": out.get("top_candidate_learning_prob_hit_pct"),
                    "top_candidate_learning_samples": out.get("top_candidate_learning_samples"),
                    "top_candidate_learning_score": out.get("top_candidate_learning_score"),
                    "top_candidate_learning_delta_points": out.get("top_candidate_learning_delta_points"),
                    "top_candidate_trend_score": out.get("top_candidate_trend_score"),
                    "top_candidate_trend_score_1d": out.get("top_candidate_trend_score_1d"),
                    "top_candidate_trend_score_4h": out.get("top_candidate_trend_score_4h"),
                    "top_candidate_trend_score_1h": out.get("top_candidate_trend_score_1h"),
                    "top_candidate_micro_trend_15m": out.get("top_candidate_micro_trend_15m"),
                    "avg_score": out.get("avg_score"),
                    "avg_score_base": out.get("avg_score_base"),
                    "avg_score_rules": out.get("avg_score_rules"),
                    "avg_score_market": out.get("avg_score_market"),
                    "learning_decision_id": out.get("learning_decision_id"),
                    "scanned_assets": out["scan"]["scanned_assets"],
                }
            )
    db.commit()
    return {
        "dry_run": bool(dry_run),
        "top_n": top_n,
        "direction": direction,
        "executed_count": len(executed),
        "results": executed,
    }


@router.post("/admin/exit/tick", response_model=AutoExitTickOut)
def admin_exit_tick(
    dry_run: bool = True,
    real_only: bool = True,
    include_service_users: bool = False,
    max_positions: int = 500,
    user_email: Optional[str] = None,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    req_payload = {
        "dry_run": bool(dry_run),
        "real_only": bool(real_only),
        "include_service_users": bool(include_service_users),
        "max_positions": int(max_positions),
        "user_email": (user_email or "").strip().lower() or None,
        "tenant_id": _tenant_id(current_user),
    }
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/admin/exit/tick",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached

    out = run_exit_tick_for_tenant(
        db=db,
        tenant_id=_tenant_id(current_user),
        dry_run=dry_run,
        real_only=real_only,
        include_service_users=include_service_users,
        max_positions=max_positions,
        user_email=user_email,
    )
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/admin/exit/tick",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=out,
    )
    db.commit()
    return out


def run_exit_tick_for_tenant(
    *,
    db: Session,
    tenant_id: str,
    dry_run: bool = True,
    real_only: bool = True,
    include_service_users: bool = False,
    max_positions: int = 500,
    user_email: Optional[str] = None,
) -> dict:
    now = datetime.now(timezone.utc)
    max_positions = max(1, min(int(max_positions), 5000))
    paused = bool(settings.AUTO_EXIT_INTERNAL_PAUSE)
    max_closes_per_tick = max(0, int(settings.AUTO_EXIT_INTERNAL_MAX_CLOSES_PER_TICK or 0))
    symbol_cooldown_seconds = max(0, int(settings.AUTO_EXIT_INTERNAL_SYMBOL_COOLDOWN_SECONDS or 0))
    max_errors_per_tick = max(1, int(settings.AUTO_EXIT_INTERNAL_MAX_ERRORS_PER_TICK or 1))
    reason_priority = {
        "stop_loss_hit": 0,
        "event_risk_exit": 1,
        "time_limit_no_progress": 2,
        "trend_break": 3,
        "signal_reverse": 4,
        "take_profit_hit": 5,
    }
    users = (
        db.execute(select(User).where(User.tenant_id == tenant_id).order_by(User.email.asc()))
        .scalars()
        .all()
    )
    target_email = (user_email or "").strip().lower()
    eligible_users = []
    for u in users:
        if target_email and (u.email or "").strip().lower() != target_email:
            continue
        if u.role not in {"admin", "trader"}:
            continue
        if real_only and not _is_real_user_email(u.email):
            continue
        if (not include_service_users) and _is_service_user_email(u.email):
            continue
        eligible_users.append(u)
    if not eligible_users:
        return {
            "dry_run": bool(dry_run),
            "paused": paused,
            "scanned_positions": 0,
            "exit_candidates": 0,
            "closed_positions": 0,
            "skipped_no_price": 0,
            "skipped_by_policy": 0,
            "errors": 0,
            "results": [],
        }

    user_by_id = {u.id: u for u in eligible_users}
    open_positions = (
        db.execute(
            select(Position)
            .where(
                Position.user_id.in_(list(user_by_id.keys())),
                Position.status == "OPEN",
            )
            .order_by(Position.opened_at.asc())
            .limit(max_positions)
        )
        .scalars()
        .all()
    )
    binance_symbols = sorted(
        {
            str(p.symbol or "").upper()
            for p in open_positions
            if infer_exchange_from_symbol(str(p.symbol or "")) == "BINANCE"
        }
    )
    binance_prices = _fetch_binance_price_map(binance_symbols) if binance_symbols else {}

    scanned_positions = len(open_positions)
    exit_candidates = 0
    closed_positions = 0
    skipped_no_price = 0
    skipped_by_policy = 0
    errors = 0
    results_by_position_id: dict[str, dict] = {}
    exit_candidates_pending: list[dict] = []
    closed_in_tick: set[tuple[str, str]] = set()

    for p in open_positions:
        user = user_by_id.get(p.user_id)
        if user is None:
            continue
        symbol = str(p.symbol or "").upper()
        exchange = infer_exchange_from_symbol(symbol)
        side_for_exit = _position_direction_to_exit_check_side(str(p.side))
        opened_at = p.opened_at if p.opened_at and p.opened_at.tzinfo else (p.opened_at.replace(tzinfo=timezone.utc) if p.opened_at else now)
        opened_minutes = int(max(0.0, (now - opened_at.astimezone(timezone.utc)).total_seconds() / 60.0))
        current_price = None
        if exchange == "BINANCE":
            current_price = binance_prices.get(symbol)
        if not current_price or float(current_price) <= 0:
            skipped_no_price += 1
            reason = "no_price"
            log_audit_event(
                db,
                action="exit.auto_close.skipped_no_price",
                user_id=user.id,
                entity_type="position",
                entity_id=p.id,
                details={"exchange": exchange, "symbol": symbol, "opened_minutes": opened_minutes},
            )
            results_by_position_id[p.id] = {
                "user_email": user.email,
                "exchange": exchange,
                "position_id": p.id,
                "symbol": symbol,
                "side": side_for_exit,
                "opened_minutes": opened_minutes,
                "should_exit": False,
                "closed": False,
                "reason": reason,
                "dry_run": bool(dry_run),
                "entry_price": float(p.entry_price),
                "current_price": None,
                "realized_pnl": None,
            }
            continue

        snapshot = _latest_market_snapshot_for_symbol(
            db=db,
            tenant_id=tenant_id,
            exchange=exchange,
            symbol=symbol,
        )
        trend_score = float(snapshot.trend_score) if snapshot else 0.0
        atr_pct = float(snapshot.atr_pct) if snapshot else 0.0
        momentum_score = float(snapshot.momentum_score) if snapshot else 0.0
        market_regime, regime_source = infer_market_regime(
            trend_score=trend_score,
            atr_pct=atr_pct,
            momentum_score=momentum_score,
        )
        strategy = resolve_strategy_for_user_exchange(
            db=db,
            user_id=user.id,
            exchange=exchange,
        )
        runtime_policy = resolve_runtime_policy(
            db=db,
            strategy_id=strategy["strategy_id"],
            exchange=exchange,
        )
        exit_payload = ExitCheckRequest(
            symbol=symbol,
            side=side_for_exit,
            entry_price=float(p.entry_price),
            current_price=float(current_price),
            stop_loss=float(p.stop_loss if p.stop_loss is not None else p.entry_price),
            take_profit=float(p.take_profit if p.take_profit is not None else p.entry_price),
            opened_minutes=opened_minutes,
            trend_break=False,
            signal_reverse=False,
            macro_event_block=False,
            earnings_within_24h=False,
            market_trend_score=trend_score,
            atr_pct=atr_pct,
            momentum_score=momentum_score,
        )
        checks, reasons = _build_exit_checks(
            exchange=exchange,
            strategy_id=strategy["strategy_id"],
            payload=exit_payload,
            market_regime=market_regime,
            runtime_policy=runtime_policy,
        )
        should_exit = len(reasons) > 0
        if should_exit:
            exit_candidates += 1
        reason = ",".join(reasons) if reasons else "hold"
        top_priority = min(reason_priority.get(r, 99) for r in reasons) if reasons else 99
        base_result = {
            "user_email": user.email,
            "exchange": exchange,
            "position_id": p.id,
            "symbol": symbol,
            "side": side_for_exit,
            "opened_minutes": opened_minutes,
            "should_exit": should_exit,
            "closed": False,
            "reason": reason,
            "dry_run": bool(dry_run),
            "entry_price": float(p.entry_price),
            "current_price": float(current_price),
            "realized_pnl": None,
        }
        results_by_position_id[p.id] = base_result

        if should_exit:
            exit_candidates_pending.append(
                {
                    "priority": top_priority,
                    "opened_minutes": opened_minutes,
                    "position": p,
                    "user": user,
                    "exchange": exchange,
                    "symbol": symbol,
                    "side_for_exit": side_for_exit,
                    "current_price": float(current_price),
                    "checks": checks,
                    "reasons": reasons,
                    "reason_text": reason,
                    "strategy_id": strategy["strategy_id"],
                    "strategy_source": strategy["source"],
                    "market_regime": market_regime,
                    "regime_source": regime_source,
                }
            )
        else:
            log_audit_event(
                db,
                action="exit.auto_close.hold",
                user_id=user.id,
                entity_type="position",
                entity_id=p.id,
                details={
                    "exchange": exchange,
                    "strategy_id": strategy["strategy_id"],
                    "strategy_source": strategy["source"],
                    "market_regime": market_regime,
                    "regime_source": regime_source,
                    "opened_minutes": opened_minutes,
                    "dry_run": bool(dry_run),
                    "should_exit": False,
                    "closed": False,
                    "reasons": reasons,
                    "checks": checks,
                    "current_price": float(current_price),
                    "realized_pnl": None,
                },
            )

    for item in sort_exit_candidates(exit_candidates_pending):
        p = item["position"]
        user = item["user"]
        key = (str(user.id), str(item["symbol"]))
        out_row = results_by_position_id.get(p.id)
        if out_row is None:
            continue
        policy_skip_reason: Optional[str] = resolve_policy_skip_reason_basic(
            dry_run=bool(dry_run),
            paused=bool(paused),
            errors=int(errors),
            max_errors_per_tick=int(max_errors_per_tick),
            closed_positions=int(closed_positions),
            max_closes_per_tick=int(max_closes_per_tick),
            already_closed_symbol_in_tick=(key in closed_in_tick),
        )

        if policy_skip_reason is None and (not dry_run) and symbol_cooldown_seconds > 0:
            recent_cutoff = now - timedelta(seconds=symbol_cooldown_seconds)
            recent_closed = db.execute(
                select(Position.id).where(
                    Position.user_id == user.id,
                    Position.symbol == item["symbol"],
                    Position.status == "CLOSED",
                    Position.closed_at.is_not(None),
                    Position.closed_at >= recent_cutoff,
                    Position.id != p.id,
                ).limit(1)
            ).scalar_one_or_none()
            if recent_closed:
                policy_skip_reason = "symbol_cooldown_window"

        if policy_skip_reason:
            skipped_by_policy += 1
            out_row["reason"] = f"policy_skipped:{policy_skip_reason}|{item['reason_text']}"
            log_audit_event(
                db,
                action="exit.auto_close.policy_skipped",
                user_id=user.id,
                entity_type="position",
                entity_id=p.id,
                details={
                    "policy_skip_reason": policy_skip_reason,
                    "exchange": item["exchange"],
                    "opened_minutes": item["opened_minutes"],
                    "dry_run": bool(dry_run),
                    "reasons": item["reasons"],
                },
            )
            continue

        realized_pnl = None
        closed = False
        if not dry_run:
            try:
                realized_pnl = _close_position_internal(
                    db=db,
                    user=user,
                    position=p,
                    exit_price=item["current_price"],
                    fees=0.0,
                    reason=item["reason_text"],
                    checks=item["checks"],
                )
                closed = True
                closed_positions += 1
                closed_in_tick.add(key)
            except Exception as exc:
                errors += 1
                skipped_by_policy += 1
                out_row["reason"] = f"policy_skipped:close_error|{item['reason_text']}"
                log_audit_event(
                    db,
                    action="exit.auto_close.error",
                    user_id=user.id,
                    entity_type="position",
                    entity_id=p.id,
                    details={
                        "exchange": item["exchange"],
                        "error": str(exc),
                        "dry_run": bool(dry_run),
                        "reasons": item["reasons"],
                    },
                )
                continue

        out_row["closed"] = closed
        out_row["realized_pnl"] = realized_pnl
        log_audit_event(
            db,
            action="exit.auto_close.triggered",
            user_id=user.id,
            entity_type="position",
            entity_id=p.id,
            details={
                "exchange": item["exchange"],
                "strategy_id": item["strategy_id"],
                "strategy_source": item["strategy_source"],
                "market_regime": item["market_regime"],
                "regime_source": item["regime_source"],
                "opened_minutes": item["opened_minutes"],
                "dry_run": bool(dry_run),
                "should_exit": True,
                "closed": closed,
                "reasons": item["reasons"],
                "checks": item["checks"],
                "current_price": item["current_price"],
                "realized_pnl": realized_pnl,
            },
        )

    results: list[dict] = []
    for p in open_positions:
        row = results_by_position_id.get(p.id)
        if row:
            results.append(row)

    log_audit_event(
        db,
        action="exit.auto_close.tick.summary",
        user_id=None,
        entity_type="tenant",
        entity_id=tenant_id,
        details={
            "dry_run": bool(dry_run),
            "paused": paused,
            "scanned_positions": scanned_positions,
            "exit_candidates": exit_candidates,
            "closed_positions": closed_positions,
            "skipped_no_price": skipped_no_price,
            "skipped_by_policy": skipped_by_policy,
            "errors": errors,
        },
    )
    db.commit()
    return {
        "dry_run": bool(dry_run),
        "paused": paused,
        "scanned_positions": scanned_positions,
        "exit_candidates": exit_candidates,
        "closed_positions": closed_positions,
        "skipped_no_price": skipped_no_price,
        "skipped_by_policy": skipped_by_policy,
        "errors": errors,
        "results": results,
    }


def _label_learning_outcomes(
    *,
    db: Session,
    tenant_id: str,
    horizon_minutes: Optional[int] = None,
    limit: int = 500,
    dry_run: bool = True,
) -> dict:
    now = datetime.now(timezone.utc)
    grace_minutes = max(0, int(settings.LEARNING_LABEL_GRACE_MINUTES))
    q = (
        select(LearningDecisionOutcome)
        .where(
            LearningDecisionOutcome.tenant_id == tenant_id,
            LearningDecisionOutcome.outcome_status.in_(["pending", "no_price"]),
            LearningDecisionOutcome.due_at <= now,
        )
        .order_by(LearningDecisionOutcome.due_at.asc())
        .limit(max(1, min(int(limit), 5000)))
    )
    if horizon_minutes is not None:
        q = q.where(LearningDecisionOutcome.horizon_minutes == int(horizon_minutes))

    rows = db.execute(q).scalars().all()
    scanned = len(rows)
    labeled = 0
    expired = 0
    no_price = 0
    if not rows:
        return {
            "dry_run": bool(dry_run),
            "horizon_minutes": int(horizon_minutes or settings.LEARNING_LABEL_HORIZON_MINUTES),
            "scanned": 0,
            "labeled": 0,
            "expired": 0,
            "no_price": 0,
            "labeled_rate_pct": 0.0,
            "expired_rate_pct": 0.0,
            "no_price_rate_pct": 0.0,
        }

    symbols = [str(r.symbol or "") for r in rows if (r.exchange or "").upper() == "BINANCE" and r.symbol]
    binance_prices = _fetch_binance_price_map(symbols)
    decision_ids = [r.decision_id for r in rows]
    snap_rows = db.execute(
        select(LearningDecisionSnapshot).where(LearningDecisionSnapshot.decision_id.in_(decision_ids))
    ).scalars().all()
    snap_by_decision = {s.decision_id: s for s in snap_rows}

    for row in rows:
        snap = snap_by_decision.get(row.decision_id)
        side = str((snap.selected_side if snap else "") or "BUY").upper()
        sign = -1.0 if side == "SELL" else 1.0
        qty = float((snap.selected_qty if snap else 0.0) or 0.0)
        entry = float((row.entry_price or (snap.entry_price if snap else 0.0)) or 0.0)
        symbol = str((row.symbol or (snap.selected_symbol if snap else "")) or "").upper()
        exchange = str(row.exchange or "").upper()

        exit_price = None
        price_source = None
        if exchange == "BINANCE" and symbol:
            px = binance_prices.get(symbol)
            if px and px > 0:
                exit_price = float(px)
                price_source = "binance_ticker_24h"

        if not exit_price or not entry or entry <= 0:
            can_expire = now >= (row.due_at + timedelta(minutes=grace_minutes))
            if can_expire:
                expired += 1
                if not dry_run:
                    row.outcome_status = "expired"
                    row.labeled_at = now
                    row.meta_json = _safe_json({"reason": "missing_price_or_entry"})
            else:
                no_price += 1
                if not dry_run:
                    row.outcome_status = "no_price"
            continue

        ret_pct = ((exit_price - entry) / entry) * 100.0 * sign
        pnl_quote = qty * (exit_price - entry) * sign
        hit = bool(ret_pct > 0.0)
        labeled += 1
        if not dry_run:
            row.outcome_status = "labeled"
            row.labeled_at = now
            row.exit_price = round(exit_price, 10)
            row.price_source = price_source
            row.return_pct = round(ret_pct, 6)
            row.pnl_quote = round(pnl_quote, 10)
            row.hit = hit
            row.max_drawdown_pct = None
            row.max_runup_pct = None
            row.meta_json = _safe_json({"labeled_from": "ticker_24h"})

    if not dry_run:
        db.flush()
    return {
        "dry_run": bool(dry_run),
        "horizon_minutes": int(horizon_minutes or settings.LEARNING_LABEL_HORIZON_MINUTES),
        "scanned": scanned,
        "labeled": labeled,
        "expired": expired,
        "no_price": no_price,
        "labeled_rate_pct": compute_rate(labeled, scanned),
        "expired_rate_pct": compute_rate(expired, scanned),
        "no_price_rate_pct": compute_rate(no_price, scanned),
    }


def _run_learning_retention(
    *,
    db: Session,
    dry_run: bool = True,
    raw_ttl_days: Optional[int] = None,
    rollup_ttl_days: Optional[int] = None,
) -> dict:
    raw_days = max(7, int(raw_ttl_days or settings.LEARNING_RAW_TTL_DAYS))
    rollup_days = max(30, int(rollup_ttl_days or settings.LEARNING_ROLLUP_TTL_DAYS))
    now = datetime.now(timezone.utc)
    raw_cutoff = now - timedelta(days=raw_days)
    rollup_cutoff = now - timedelta(days=rollup_days)

    delete_snap_q = delete(LearningDecisionSnapshot).where(LearningDecisionSnapshot.decision_ts < raw_cutoff)
    delete_outcome_q = delete(LearningDecisionOutcome).where(LearningDecisionOutcome.decision_ts < raw_cutoff)
    delete_rollup_q = delete(LearningRollupHourly).where(LearningRollupHourly.bucket_hour < rollup_cutoff)

    if dry_run:
        snap_count = db.execute(
            select(func.count()).select_from(LearningDecisionSnapshot).where(LearningDecisionSnapshot.decision_ts < raw_cutoff)
        ).scalar_one()
        out_count = db.execute(
            select(func.count()).select_from(LearningDecisionOutcome).where(LearningDecisionOutcome.decision_ts < raw_cutoff)
        ).scalar_one()
        roll_count = db.execute(
            select(func.count()).select_from(LearningRollupHourly).where(LearningRollupHourly.bucket_hour < rollup_cutoff)
        ).scalar_one()
    else:
        snap_count = db.execute(delete_snap_q).rowcount or 0
        out_count = db.execute(delete_outcome_q).rowcount or 0
        roll_count = db.execute(delete_rollup_q).rowcount or 0
        db.flush()

    return {
        "dry_run": bool(dry_run),
        "raw_ttl_days": raw_days,
        "rollup_ttl_days": rollup_days,
        "deleted_snapshots": int(snap_count),
        "deleted_outcomes": int(out_count),
        "deleted_rollups": int(roll_count),
    }


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    vals = sorted(float(v) for v in values)
    pos = (len(vals) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    if lo == hi:
        return float(vals[lo])
    frac = pos - lo
    return float(vals[lo] + (vals[hi] - vals[lo]) * frac)


def _refresh_learning_rollup_hourly(
    *,
    db: Session,
    tenant_id: str,
    hours: int = 48,
    dry_run: bool = False,
) -> dict:
    window_hours = max(1, min(int(hours), 24 * 30))
    max_rows = max(1_000, min(int(settings.LEARNING_ROLLUP_MAX_ROWS or 50_000), 500_000))
    now = datetime.now(timezone.utc)
    from_dt = now - timedelta(hours=window_hours)
    rows = db.execute(
        select(LearningDecisionOutcome, LearningDecisionSnapshot)
        .join(
            LearningDecisionSnapshot,
            LearningDecisionSnapshot.decision_id == LearningDecisionOutcome.decision_id,
        )
        .where(
            LearningDecisionOutcome.tenant_id == tenant_id,
            LearningDecisionOutcome.outcome_status == "labeled",
            LearningDecisionOutcome.labeled_at >= from_dt,
        )
        .order_by(LearningDecisionOutcome.labeled_at.desc())
        .limit(max_rows)
    )

    grouped: dict[tuple, dict] = {}
    processed_rows = 0
    for outcome, snap in rows:
        processed_rows += 1
        key = (
            _bucket_1h(outcome.labeled_at or outcome.decision_ts),
            str(outcome.exchange or "UNKNOWN"),
            str(outcome.symbol or snap.selected_symbol or ""),
            int(outcome.horizon_minutes or 60),
        )
        agg = grouped.setdefault(
            key,
            {
                "samples": 0,
                "hit_count": 0,
                "returns": [],
                "sum_returns": 0.0,
                "sum_score": 0.0,
                "count_score": 0,
                "sum_score_rules": 0.0,
                "count_score_rules": 0,
                "sum_score_market": 0.0,
                "count_score_market": 0,
                "green": 0,
                "gray": 0,
                "red": 0,
            },
        )
        agg["samples"] += 1
        ret = float(outcome.return_pct or 0.0)
        agg["returns"].append(ret)
        agg["sum_returns"] += ret
        if bool(outcome.hit):
            agg["hit_count"] += 1
        if snap.selected_score is not None:
            agg["sum_score"] += float(snap.selected_score)
            agg["count_score"] += 1
        if snap.selected_score_rules is not None:
            agg["sum_score_rules"] += float(snap.selected_score_rules)
            agg["count_score_rules"] += 1
        if snap.selected_score_market is not None:
            agg["sum_score_market"] += float(snap.selected_score_market)
            agg["count_score_market"] += 1
        liq_state = str(snap.selected_liquidity_state or "").lower()
        if liq_state == "green":
            agg["green"] += 1
        elif liq_state == "gray":
            agg["gray"] += 1
        elif liq_state == "red":
            agg["red"] += 1

    upserted = 0
    if not dry_run:
        db.execute(
            delete(LearningRollupHourly).where(
                LearningRollupHourly.tenant_id == tenant_id,
                LearningRollupHourly.bucket_hour >= from_dt,
            )
        )
    for key, agg in grouped.items():
        bucket_hour, exchange, symbol, horizon = key
        samples = int(agg["samples"])
        returns = agg["returns"]
        hit_rate = (int(agg["hit_count"]) / samples) * 100.0 if samples else 0.0

        if not dry_run:
            db.add(
                LearningRollupHourly(
                    tenant_id=tenant_id,
                    partition_ym=_partition_ym(bucket_hour),
                    bucket_hour=bucket_hour,
                    exchange=exchange,
                    symbol=symbol or None,
                    horizon_minutes=horizon,
                    samples=samples,
                    hit_rate_pct=round(hit_rate, 4),
                    avg_return_pct=round(float(agg["sum_returns"]) / samples if samples else 0.0, 6),
                    p50_return_pct=round(_percentile(returns, 0.50), 6),
                    p90_return_pct=round(_percentile(returns, 0.90), 6),
                    avg_score=(
                        round(float(agg["sum_score"]) / int(agg["count_score"]), 4)
                        if int(agg["count_score"]) > 0
                        else None
                    ),
                    avg_score_rules=(
                        round(float(agg["sum_score_rules"]) / int(agg["count_score_rules"]), 4)
                        if int(agg["count_score_rules"]) > 0
                        else None
                    ),
                    avg_score_market=(
                        round(float(agg["sum_score_market"]) / int(agg["count_score_market"]), 4)
                        if int(agg["count_score_market"]) > 0
                        else None
                    ),
                    green_count=int(agg["green"]),
                    gray_count=int(agg["gray"]),
                    red_count=int(agg["red"]),
                )
            )
        upserted += 1

    if not dry_run:
        db.flush()
    return {
        "hours": window_hours,
        "groups": len(grouped),
        "upserted": upserted,
        "dry_run": bool(dry_run),
        "processed_rows": int(processed_rows),
        "max_rows": int(max_rows),
        "truncated": bool(processed_rows >= max_rows),
    }


def run_learning_pipeline_tick(db: Session, tenant_id: str) -> None:
    if not settings.LEARNING_PIPELINE_ENABLED:
        return
    now = datetime.now(timezone.utc)
    try:
        label_interval = max(1, int(settings.LEARNING_LABEL_INTERVAL_MINUTES))
        if now.minute % label_interval == 0:
            _label_learning_outcomes(
                db=db,
                tenant_id=tenant_id,
                horizon_minutes=int(settings.LEARNING_LABEL_HORIZON_MINUTES),
                limit=500,
                dry_run=False,
            )

        rollup_interval = max(1, int(settings.LEARNING_ROLLUP_INTERVAL_MINUTES))
        if now.minute % rollup_interval == 0:
            _refresh_learning_rollup_hourly(
                db=db,
                tenant_id=tenant_id,
                hours=48,
                dry_run=False,
            )

        if settings.LEARNING_RETENTION_ENABLED:
            retention_interval = max(5, int(settings.LEARNING_RETENTION_INTERVAL_MINUTES))
            if now.minute % retention_interval == 0:
                _run_learning_retention(db=db, dry_run=False)
        db.commit()
    except Exception:
        db.rollback()


@router.post("/admin/learning/label", response_model=LearningLabelRunOut)
def admin_learning_label(
    dry_run: bool = True,
    horizon_minutes: Optional[int] = None,
    limit: int = 500,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    if horizon_minutes is not None:
        horizon_minutes = validate_range_param(
            name="horizon_minutes",
            value=int(horizon_minutes),
            minimum=5,
            maximum=10080,
        )
    limit = validate_range_param(name="limit", value=int(limit), minimum=1, maximum=5000)

    out = _label_learning_outcomes(
        db=db,
        tenant_id=_tenant_id(current_user),
        horizon_minutes=horizon_minutes,
        limit=limit,
        dry_run=dry_run,
    )
    if not dry_run:
        db.commit()
    return out


@router.post("/admin/learning/retention/run", response_model=LearningRetentionRunOut)
def admin_learning_retention(
    dry_run: bool = True,
    raw_ttl_days: Optional[int] = None,
    rollup_ttl_days: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    _ = current_user
    out = _run_learning_retention(
        db=db,
        dry_run=dry_run,
        raw_ttl_days=raw_ttl_days,
        rollup_ttl_days=rollup_ttl_days,
    )
    if not dry_run:
        db.commit()
    return out


@router.post("/admin/learning/rollup/refresh")
def admin_learning_rollup_refresh(
    hours: int = 48,
    dry_run: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    hours = validate_range_param(name="hours", value=int(hours), minimum=1, maximum=24 * 30)
    out = _refresh_learning_rollup_hourly(
        db=db,
        tenant_id=_tenant_id(current_user),
        hours=hours,
        dry_run=dry_run,
    )
    if not dry_run:
        db.commit()
    return out


@router.get("/admin/learning/status", response_model=LearningStatusOut)
def admin_learning_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    tenant = _tenant_id(current_user)
    now = datetime.now(timezone.utc)
    pending = db.execute(
        select(func.count()).select_from(LearningDecisionOutcome).where(
            LearningDecisionOutcome.tenant_id == tenant,
            LearningDecisionOutcome.outcome_status == "pending",
        )
    ).scalar_one()
    labeled = db.execute(
        select(func.count()).select_from(LearningDecisionOutcome).where(
            LearningDecisionOutcome.tenant_id == tenant,
            LearningDecisionOutcome.outcome_status == "labeled",
        )
    ).scalar_one()
    expired = db.execute(
        select(func.count()).select_from(LearningDecisionOutcome).where(
            LearningDecisionOutcome.tenant_id == tenant,
            LearningDecisionOutcome.outcome_status == "expired",
        )
    ).scalar_one()
    no_price = db.execute(
        select(func.count()).select_from(LearningDecisionOutcome).where(
            LearningDecisionOutcome.tenant_id == tenant,
            LearningDecisionOutcome.outcome_status == "no_price",
        )
    ).scalar_one()
    snapshots_total = db.execute(
        select(func.count()).select_from(LearningDecisionSnapshot).where(
            LearningDecisionSnapshot.tenant_id == tenant,
        )
    ).scalar_one()
    outcomes_total = db.execute(
        select(func.count()).select_from(LearningDecisionOutcome).where(
            LearningDecisionOutcome.tenant_id == tenant,
        )
    ).scalar_one()
    outcomes_total_i = int(outcomes_total)
    pending_i = int(pending)
    labeled_i = int(labeled)
    expired_i = int(expired)
    no_price_i = int(no_price)
    return LearningStatusOut(
        generated_at=now.isoformat(),
        pending=pending_i,
        labeled=labeled_i,
        expired=expired_i,
        no_price=no_price_i,
        snapshots_total=int(snapshots_total),
        outcomes_total=outcomes_total_i,
        pending_rate_pct=compute_rate(pending_i, outcomes_total_i),
        labeled_rate_pct=compute_rate(labeled_i, outcomes_total_i),
        expired_rate_pct=compute_rate(expired_i, outcomes_total_i),
        no_price_rate_pct=compute_rate(no_price_i, outcomes_total_i),
    )


_LEARNING_HEALTH_WINDOWS: list[tuple[str, int]] = [
    ("24h", 24),
    ("7d", 24 * 7),
    ("30d", 24 * 30),
    ("6m", 24 * 30 * 6),
    ("1y", 24 * 365),
]


def _learning_health_window_metrics(
    *,
    db: Session,
    tenant_id: str,
    exchange_norm: str,
    from_dt: datetime,
) -> dict:
    outcome_filters = [
        LearningDecisionOutcome.tenant_id == tenant_id,
        LearningDecisionOutcome.decision_ts >= from_dt,
    ]
    decision_filters = [
        LearningDecisionSnapshot.tenant_id == tenant_id,
        LearningDecisionSnapshot.decision_ts >= from_dt,
    ]
    if exchange_norm in {"BINANCE", "IBKR"}:
        outcome_filters.append(LearningDecisionOutcome.exchange == exchange_norm)
        decision_filters.append(LearningDecisionSnapshot.exchange == exchange_norm)

    outcomes_total = int(
        db.execute(
            select(func.count()).select_from(LearningDecisionOutcome).where(*outcome_filters)
        ).scalar_one()
        or 0
    )
    pending = int(
        db.execute(
            select(func.count()).select_from(LearningDecisionOutcome).where(
                *outcome_filters,
                LearningDecisionOutcome.outcome_status == "pending",
            )
        ).scalar_one()
        or 0
    )
    labeled = int(
        db.execute(
            select(func.count()).select_from(LearningDecisionOutcome).where(
                *outcome_filters,
                LearningDecisionOutcome.outcome_status == "labeled",
            )
        ).scalar_one()
        or 0
    )
    expired = int(
        db.execute(
            select(func.count()).select_from(LearningDecisionOutcome).where(
                *outcome_filters,
                LearningDecisionOutcome.outcome_status == "expired",
            )
        ).scalar_one()
        or 0
    )
    no_price = int(
        db.execute(
            select(func.count()).select_from(LearningDecisionOutcome).where(
                *outcome_filters,
                LearningDecisionOutcome.outcome_status == "no_price",
            )
        ).scalar_one()
        or 0
    )
    decisions_total = int(
        db.execute(
            select(func.count()).select_from(LearningDecisionSnapshot).where(*decision_filters)
        ).scalar_one()
        or 0
    )
    hit_count = int(
        db.execute(
            select(func.count()).select_from(LearningDecisionOutcome).where(
                *outcome_filters,
                LearningDecisionOutcome.outcome_status == "labeled",
                LearningDecisionOutcome.hit.is_(True),
            )
        ).scalar_one()
        or 0
    )
    avg_return_raw = db.execute(
        select(func.avg(LearningDecisionOutcome.return_pct)).where(
            *outcome_filters,
            LearningDecisionOutcome.outcome_status == "labeled",
            LearningDecisionOutcome.return_pct.is_not(None),
        )
    ).scalar_one()
    hit_rate_pct = None
    if labeled > 0:
        hit_rate_pct = compute_rate(hit_count, labeled)
    avg_return_pct = None
    if avg_return_raw is not None:
        avg_return_pct = round(float(avg_return_raw), 4)
    return {
        "decisions_total": decisions_total,
        "outcomes_total": outcomes_total,
        "pending": pending,
        "labeled": labeled,
        "expired": expired,
        "no_price": no_price,
        "labeled_rate_pct": compute_rate(labeled, outcomes_total),
        "expired_rate_pct": compute_rate(expired, outcomes_total),
        "no_price_rate_pct": compute_rate(no_price, outcomes_total),
        "hit_rate_pct": hit_rate_pct,
        "avg_return_pct": avg_return_pct,
    }


@router.get("/admin/learning/health", response_model=LearningHealthOut)
def admin_learning_health(
    exchange: str = "ALL",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    now = datetime.now(timezone.utc)
    tenant = _tenant_id(current_user)
    exchange_norm = validate_choice_param(
        name="exchange",
        value=exchange,
        allowed={"ALL", "BINANCE", "IBKR"},
    )

    windows: list[LearningHealthWindowOut] = []
    for label, hours in _LEARNING_HEALTH_WINDOWS:
        from_dt = now - timedelta(hours=hours)
        m = _learning_health_window_metrics(
            db=db,
            tenant_id=tenant,
            exchange_norm=exchange_norm,
            from_dt=from_dt,
        )
        windows.append(
            LearningHealthWindowOut(
                label=label,
                hours=hours,
                decisions_total=m["decisions_total"],
                outcomes_total=m["outcomes_total"],
                pending=m["pending"],
                labeled=m["labeled"],
                expired=m["expired"],
                no_price=m["no_price"],
                labeled_rate_pct=m["labeled_rate_pct"],
                expired_rate_pct=m["expired_rate_pct"],
                no_price_rate_pct=m["no_price_rate_pct"],
                hit_rate_pct=m["hit_rate_pct"],
                avg_return_pct=m["avg_return_pct"],
            )
        )

    snapshot_filters = [LearningDecisionSnapshot.tenant_id == tenant]
    outcome_filters = [LearningDecisionOutcome.tenant_id == tenant]
    rollup_filters = [LearningRollupHourly.tenant_id == tenant]
    if exchange_norm in {"BINANCE", "IBKR"}:
        snapshot_filters.append(LearningDecisionSnapshot.exchange == exchange_norm)
        outcome_filters.append(LearningDecisionOutcome.exchange == exchange_norm)
        rollup_filters.append(LearningRollupHourly.exchange == exchange_norm)

    snapshots_total = int(
        db.execute(
            select(func.count()).select_from(LearningDecisionSnapshot).where(*snapshot_filters)
        ).scalar_one()
        or 0
    )
    outcomes_total = int(
        db.execute(
            select(func.count()).select_from(LearningDecisionOutcome).where(*outcome_filters)
        ).scalar_one()
        or 0
    )
    labeled_total = int(
        db.execute(
            select(func.count()).select_from(LearningDecisionOutcome).where(
                *outcome_filters,
                LearningDecisionOutcome.outcome_status == "labeled",
            )
        ).scalar_one()
        or 0
    )
    rollup_rows_total = int(
        db.execute(
            select(func.count()).select_from(LearningRollupHourly).where(*rollup_filters)
        ).scalar_one()
        or 0
    )

    first_snapshot_at = db.execute(
        select(func.min(LearningDecisionSnapshot.decision_ts)).where(*snapshot_filters)
    ).scalar_one()
    last_snapshot_at = db.execute(
        select(func.max(LearningDecisionSnapshot.decision_ts)).where(*snapshot_filters)
    ).scalar_one()
    last_outcome_at = db.execute(
        select(func.max(LearningDecisionOutcome.labeled_at)).where(*outcome_filters)
    ).scalar_one()
    last_rollup_at = db.execute(
        select(func.max(LearningRollupHourly.updated_at)).where(*rollup_filters)
    ).scalar_one()

    lifetime_days = 0
    if first_snapshot_at is not None:
        dt = first_snapshot_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        lifetime_days = max(0, (now - dt.astimezone(timezone.utc)).days)

    day24 = windows[0] if windows else LearningHealthWindowOut(
        label="24h",
        hours=24,
        decisions_total=0,
        outcomes_total=0,
        pending=0,
        labeled=0,
        expired=0,
        no_price=0,
    )
    recommendations: list[str] = []
    semaphore = "green"
    if day24.outcomes_total < 10:
        semaphore = "yellow"
        recommendations.append("Aumentar muestras recientes (24h) antes de subir peso de modelo.")
    if day24.expired_rate_pct >= 25.0 or day24.no_price_rate_pct >= 25.0:
        semaphore = "red"
        recommendations.append("Reducir expirados/no_price: revisar fuentes de precio y horizonte de etiquetado.")
    elif day24.labeled_rate_pct < 45.0:
        semaphore = "yellow"
        recommendations.append("Subir tasa de etiquetado ejecutando /ops/admin/learning/label con mayor frecuencia.")
    if day24.hit_rate_pct is not None and day24.labeled >= 20 and float(day24.hit_rate_pct) < 45.0:
        semaphore = "yellow" if semaphore != "red" else semaphore
        recommendations.append("Calibrar reglas/modelo: hit_rate 24h bajo para muestras etiquetadas.")
    if not recommendations:
        recommendations.append("Salud estable. Mantener ciclo label->rollup->retention y monitoreo diario.")

    summary = (
        f"24h labeled={day24.labeled_rate_pct}% "
        f"expired={day24.expired_rate_pct}% "
        f"no_price={day24.no_price_rate_pct}% "
        f"hit={day24.hit_rate_pct if day24.hit_rate_pct is not None else '-'}%"
    )

    return LearningHealthOut(
        generated_at=now.isoformat(),
        exchange=exchange_norm,
        semaphore=semaphore,
        summary=summary,
        recommendations=recommendations,
        windows=windows,
        experience=LearningExperienceOut(
            snapshots_total=snapshots_total,
            outcomes_total=outcomes_total,
            labeled_total=labeled_total,
            rollup_rows_total=rollup_rows_total,
            lifetime_days=lifetime_days,
            first_snapshot_at=_to_utc_iso(first_snapshot_at),
            last_snapshot_at=_to_utc_iso(last_snapshot_at),
            last_outcome_at=_to_utc_iso(last_outcome_at),
            last_rollup_at=_to_utc_iso(last_rollup_at),
        ),
    )


@router.get("/admin/learning/dataset", response_model=LearningDatasetOut)
def admin_learning_dataset(
    hours: int = 24,
    limit: int = 1000,
    outcome_status: str = "ALL",
    exchange: str = "ALL",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    hours = validate_range_param(name="hours", value=int(hours), minimum=1, maximum=24 * 30)
    limit = validate_range_param(name="limit", value=int(limit), minimum=1, maximum=5000)
    now = datetime.now(timezone.utc)
    from_dt = now - timedelta(hours=hours)
    tenant = _tenant_id(current_user)
    status_norm = validate_choice_param(
        name="outcome_status",
        value=outcome_status,
        allowed={"ALL", "PENDING", "LABELED", "EXPIRED", "NO_PRICE"},
    )
    exchange_norm = validate_choice_param(
        name="exchange",
        value=exchange,
        allowed={"ALL", "BINANCE", "IBKR"},
    )

    q = (
        select(LearningDecisionSnapshot, LearningDecisionOutcome)
        .outerjoin(
            LearningDecisionOutcome,
            and_(
                LearningDecisionOutcome.decision_id == LearningDecisionSnapshot.decision_id,
                LearningDecisionOutcome.horizon_minutes == LearningDecisionSnapshot.target_horizon_minutes,
            ),
        )
        .where(
            LearningDecisionSnapshot.tenant_id == tenant,
            LearningDecisionSnapshot.decision_ts >= from_dt,
        )
        .order_by(LearningDecisionSnapshot.decision_ts.desc())
        .limit(limit)
    )
    if exchange_norm in {"BINANCE", "IBKR"}:
        q = q.where(LearningDecisionSnapshot.exchange == exchange_norm)
    if status_norm != "ALL":
        q = q.where(LearningDecisionOutcome.outcome_status == status_norm.lower())

    rows = db.execute(q).all()
    out_rows: list[LearningDatasetRowOut] = []
    for snap, outcome in rows:
        out_rows.append(
            LearningDatasetRowOut(
                decision_id=snap.decision_id,
                timestamp=_to_utc_iso(snap.decision_ts) or now.isoformat(),
                due_at=_to_utc_iso(outcome.due_at if outcome else None),
                tenant_id=snap.tenant_id,
                user_id=snap.user_id,
                exchange=snap.exchange,
                symbol=snap.selected_symbol,
                decision=snap.decision,
                selected=bool(snap.selected),
                dry_run=bool(snap.dry_run),
                selected_score=snap.selected_score,
                selected_score_rules=snap.selected_score_rules,
                selected_score_market=snap.selected_score_market,
                selected_liquidity_state=snap.selected_liquidity_state,
                rr_estimate=snap.rr_estimate,
                trend_score=snap.trend_score,
                momentum_score=snap.momentum_score,
                atr_pct=snap.atr_pct,
                volume_24h_usdt=snap.volume_24h_usdt,
                horizon_minutes=int(snap.target_horizon_minutes or 60),
                outcome_status=(outcome.outcome_status if outcome else None),
                return_pct=(outcome.return_pct if outcome else None),
                pnl_quote=(outcome.pnl_quote if outcome else None),
                hit=(outcome.hit if outcome else None),
            )
        )
    return LearningDatasetOut(
        generated_at=now.isoformat(),
        hours=hours,
        window_from=from_dt.isoformat(),
        window_to=now.isoformat(),
        rows=out_rows,
    )


@router.get("/admin/learning/suggestion-report", response_model=LearningSuggestionReportOut)
def admin_learning_suggestion_report(
    hours: int = 24,
    limit: int = 500,
    exchange: str = "ALL",
    outcome_status: str = "ALL",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    hours = validate_range_param(name="hours", value=int(hours), minimum=1, maximum=24 * 30)
    limit = validate_range_param(name="limit", value=int(limit), minimum=1, maximum=5000)
    now = datetime.now(timezone.utc)
    tenant = _tenant_id(current_user)
    from_dt = now - timedelta(hours=hours)
    exchange_norm = validate_choice_param(
        name="exchange",
        value=exchange,
        allowed={"ALL", "BINANCE", "IBKR"},
    )
    status_norm = validate_choice_param(
        name="outcome_status",
        value=outcome_status,
        allowed={"ALL", "PENDING", "LABELED", "EXPIRED", "NO_PRICE"},
    )

    q = (
        select(LearningDecisionSnapshot, LearningDecisionOutcome)
        .join(
            LearningDecisionOutcome,
            and_(
                LearningDecisionOutcome.decision_id == LearningDecisionSnapshot.decision_id,
                LearningDecisionOutcome.horizon_minutes == LearningDecisionSnapshot.target_horizon_minutes,
            ),
        )
        .where(
            LearningDecisionSnapshot.tenant_id == tenant,
            LearningDecisionSnapshot.decision_ts >= from_dt,
        )
        .order_by(LearningDecisionSnapshot.decision_ts.desc())
        .limit(limit)
    )
    if exchange_norm in {"BINANCE", "IBKR"}:
        q = q.where(LearningDecisionSnapshot.exchange == exchange_norm)
    if status_norm in {"PENDING", "LABELED", "EXPIRED", "NO_PRICE"}:
        q = q.where(LearningDecisionOutcome.outcome_status == status_norm.lower())

    rows = db.execute(q).all()
    out_rows: list[LearningSuggestionReportRowOut] = []
    success_eval_count = 0
    success_eval_hits = 0
    for snap, outcome in rows:
        learning_prob_hit_pct = None
        learning_samples = None
        learning_score = None
        learning_delta_points = None
        score_base = None

        try:
            checks_rows = json.loads(snap.checks_json) if snap.checks_json else []
        except Exception:
            checks_rows = []
        if isinstance(checks_rows, list):
            selected_row = None
            for row in checks_rows:
                if str(row.get("symbol") or "").upper() != str(snap.selected_symbol or "").upper():
                    continue
                if str(row.get("side") or "").upper() != str(snap.selected_side or "").upper():
                    continue
                selected_row = row
                break
            if selected_row:
                learning_prob_hit_pct = selected_row.get("learning_prob_hit_pct")
                learning_samples = selected_row.get("learning_samples")
                learning_score = selected_row.get("learning_score")
                learning_delta_points = selected_row.get("learning_delta_points")
                score_base = selected_row.get("score_base")

        if score_base is None:
            score_base = snap.selected_score
        score_final = snap.selected_score

        suggestion_success = None
        if outcome.outcome_status == "labeled" and outcome.hit is not None:
            if learning_prob_hit_pct is not None:
                predicted_positive = float(learning_prob_hit_pct) >= 50.0
                actual_positive = bool(outcome.hit)
                suggestion_success = predicted_positive == actual_positive
                success_eval_count += 1
                success_eval_hits += 1 if suggestion_success else 0

        out_rows.append(
            LearningSuggestionReportRowOut(
                decision_id=snap.decision_id,
                timestamp=_to_utc_iso(snap.decision_ts) or now.isoformat(),
                user_email=snap.user_email,
                exchange=snap.exchange,
                symbol=snap.selected_symbol,
                side=snap.selected_side,
                selected=bool(snap.selected),
                decision=snap.decision,
                score_base=score_base,
                score_final=score_final,
                learning_prob_hit_pct=learning_prob_hit_pct,
                learning_samples=learning_samples,
                learning_score=learning_score,
                learning_delta_points=learning_delta_points,
                outcome_status=outcome.outcome_status,
                hit=outcome.hit,
                return_pct=outcome.return_pct,
                pnl_quote=outcome.pnl_quote,
                suggestion_success=suggestion_success,
            )
        )

    success_rate_pct = None
    if success_eval_count > 0:
        success_rate_pct = round((success_eval_hits / success_eval_count) * 100.0, 2)
    return LearningSuggestionReportOut(
        generated_at=now.isoformat(),
        hours=hours,
        window_from=from_dt.isoformat(),
        window_to=now.isoformat(),
        total_rows=len(out_rows),
        success_rate_pct=success_rate_pct,
        rows=out_rows,
    )


@router.get("/admin/learning/rollup", response_model=LearningRollupOut)
def admin_learning_rollup(
    hours: int = 72,
    limit: int = 2000,
    exchange: str = "ALL",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    hours = validate_range_param(name="hours", value=int(hours), minimum=1, maximum=24 * 30)
    limit = validate_range_param(name="limit", value=int(limit), minimum=1, maximum=5000)
    now = datetime.now(timezone.utc)
    from_dt = now - timedelta(hours=hours)
    tenant = _tenant_id(current_user)
    exchange_norm = validate_choice_param(
        name="exchange",
        value=exchange,
        allowed={"ALL", "BINANCE", "IBKR"},
    )
    q = (
        select(LearningRollupHourly)
        .where(
            LearningRollupHourly.tenant_id == tenant,
            LearningRollupHourly.bucket_hour >= from_dt,
        )
        .order_by(LearningRollupHourly.bucket_hour.desc())
        .limit(limit)
    )
    if exchange_norm in {"BINANCE", "IBKR"}:
        q = q.where(LearningRollupHourly.exchange == exchange_norm)
    rows = db.execute(q).scalars().all()
    out_rows = [
        LearningRollupRowOut(
            bucket_hour=_to_utc_iso(r.bucket_hour) or now.isoformat(),
            exchange=r.exchange,
            symbol=r.symbol,
            horizon_minutes=int(r.horizon_minutes),
            samples=int(r.samples),
            hit_rate_pct=float(r.hit_rate_pct or 0.0),
            avg_return_pct=float(r.avg_return_pct or 0.0),
            p50_return_pct=float(r.p50_return_pct or 0.0),
            p90_return_pct=float(r.p90_return_pct or 0.0),
            avg_score=r.avg_score,
            avg_score_rules=r.avg_score_rules,
            avg_score_market=r.avg_score_market,
            green_count=int(r.green_count or 0),
            gray_count=int(r.gray_count or 0),
            red_count=int(r.red_count or 0),
        )
        for r in rows
    ]
    return LearningRollupOut(
        generated_at=now.isoformat(),
        hours=hours,
        window_from=from_dt.isoformat(),
        window_to=now.isoformat(),
        rows=out_rows,
    )


@router.get("/admin/auto-pick/liquidity-report", response_model=AutoPickLiquidityReportOut)
def admin_auto_pick_liquidity_report(
    hours: int = 24,
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    hours = max(1, min(hours, 168))
    limit = max(1, min(limit, 5000))
    now = datetime.now(timezone.utc)
    from_dt = now - timedelta(hours=hours)
    tenant_ids = select(User.id).where(User.tenant_id == _tenant_id(current_user))
    user_rows = db.execute(
        select(User.id, User.email).where(User.tenant_id == _tenant_id(current_user))
    ).all()
    email_by_id = {uid: email for uid, email in user_rows}
    logs = db.execute(
        select(AuditLog)
        .where(
            AuditLog.user_id.in_(tenant_ids),
            AuditLog.action == "pretrade.auto_pick.completed",
            AuditLog.created_at >= from_dt,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).scalars().all()

    events: list[AutoPickLiquidityEventOut] = []
    green = gray = red = blocked = 0
    for r in logs:
        try:
            details = json.loads(r.details) if r.details else {}
        except Exception:
            details = {}
        decision = str(details.get("decision") or "unknown")
        selected = bool(details.get("selected", False))
        state = str(details.get("selected_liquidity_state") or "").lower().strip()
        if state not in {"green", "gray", "red"}:
            if not selected:
                state = "red"
            elif "gray" in decision:
                state = "gray"
            else:
                state = "green"
        if state == "green":
            green += 1
        elif state == "gray":
            gray += 1
        else:
            red += 1
        if not selected:
            blocked += 1
        created_at = r.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        created_at = (created_at or now).astimezone(timezone.utc)
        events.append(
            AutoPickLiquidityEventOut(
                timestamp=created_at.isoformat(),
                user_email=email_by_id.get(r.user_id, "unknown"),
                exchange=str(details.get("exchange") or "UNKNOWN"),
                decision=decision,
                selected_symbol=details.get("selected_symbol"),
                selected_score=details.get("selected_score"),
                selected_qty=details.get("selected_qty"),
                liquidity_state=state,
                size_multiplier=details.get("selected_size_multiplier"),
                scanned_assets=int(details.get("scanned_assets") or 0),
            )
        )
    total = len(events)
    blocked_rate = round((blocked / total) * 100.0, 2) if total else 0.0
    return AutoPickLiquidityReportOut(
        generated_at=now.isoformat(),
        hours=hours,
        window_from=from_dt.isoformat(),
        window_to=now.isoformat(),
        total_events=total,
        green_events=green,
        gray_events=gray,
        red_events=red,
        blocked_events=blocked,
        blocked_rate_pct=blocked_rate,
        rows=events,
    )


@router.post("/execution/exit/binance/check", response_model=ExitCheckOut)
def exit_binance_check(
    payload: ExitCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
    )
    strategy = resolve_strategy_for_user_exchange(
        db=db,
        user_id=current_user.id,
        exchange="BINANCE",
    )
    market_regime, regime_source = infer_market_regime(
        trend_score=float(payload.market_trend_score),
        atr_pct=float(payload.atr_pct),
        momentum_score=float(payload.momentum_score),
    )
    runtime_policy = resolve_runtime_policy(
        db=db,
        strategy_id=strategy["strategy_id"],
        exchange="BINANCE",
    )
    checks, reasons = _build_exit_checks(
        exchange="BINANCE",
        strategy_id=strategy["strategy_id"],
        payload=payload,
        market_regime=market_regime,
        runtime_policy=runtime_policy,
    )
    should_exit = len(reasons) > 0
    log_audit_event(
        db,
        action="exit.check.triggered" if should_exit else "exit.check.hold",
        user_id=current_user.id,
        entity_type="exit",
        details={
            "exchange": "BINANCE",
            "strategy_id": strategy["strategy_id"],
            "strategy_source": strategy["source"],
            "market_regime": market_regime,
            "regime_source": regime_source,
            "should_exit": should_exit,
            "reasons": reasons,
            "checks": checks,
        },
    )
    db.commit()
    return {
        "should_exit": should_exit,
        "exchange": "BINANCE",
        "strategy_id": strategy["strategy_id"],
        "strategy_source": strategy["source"],
        "market_regime": market_regime,
        "regime_source": regime_source,
        "reasons": reasons,
        "checks": checks,
    }


@router.post("/execution/exit/ibkr/check", response_model=ExitCheckOut)
def exit_ibkr_check(
    payload: ExitCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="IBKR",
    )
    strategy = resolve_strategy_for_user_exchange(
        db=db,
        user_id=current_user.id,
        exchange="IBKR",
    )
    market_regime, regime_source = infer_market_regime(
        trend_score=float(payload.market_trend_score),
        atr_pct=float(payload.atr_pct),
        momentum_score=float(payload.momentum_score),
    )
    runtime_policy = resolve_runtime_policy(
        db=db,
        strategy_id=strategy["strategy_id"],
        exchange="IBKR",
    )
    checks, reasons = _build_exit_checks(
        exchange="IBKR",
        strategy_id=strategy["strategy_id"],
        payload=payload,
        market_regime=market_regime,
        runtime_policy=runtime_policy,
    )
    should_exit = len(reasons) > 0
    log_audit_event(
        db,
        action="exit.check.triggered" if should_exit else "exit.check.hold",
        user_id=current_user.id,
        entity_type="exit",
        details={
            "exchange": "IBKR",
            "strategy_id": strategy["strategy_id"],
            "strategy_source": strategy["source"],
            "market_regime": market_regime,
            "regime_source": regime_source,
            "should_exit": should_exit,
            "reasons": reasons,
            "checks": checks,
        },
    )
    db.commit()
    return {
        "should_exit": should_exit,
        "exchange": "IBKR",
        "strategy_id": strategy["strategy_id"],
        "strategy_source": strategy["source"],
        "market_regime": market_regime,
        "regime_source": regime_source,
        "reasons": reasons,
        "checks": checks,
    }


@router.post("/execution/prepare", response_model=ExecutionPrepareOut)
def prepare_execution(
    payload: ExecutionPrepareRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="execution_prepare",
        exchange=payload.exchange,
    )
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange=payload.exchange,
    )
    assert_exposure_limits(
        db=db,
        current_user=current_user,
        exchange=payload.exchange,
        symbol=payload.symbol,
        qty=payload.qty,
        price_estimate=0.0,
    )
    req_payload = payload.model_dump()
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/prepare",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached

    result = prepare_execution_for_user(
        user_id=current_user.id,
        exchange=payload.exchange,
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
    )
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/prepare",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=result,
    )
    return result


@router.post("/execution/binance/test-order", response_model=BinanceTestOrderOut)
def execution_binance_test_order(
    payload: BinanceTestOrderRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="test_order",
        exchange="BINANCE",
    )
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
    )
    assert_exposure_limits(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
        symbol=payload.symbol,
        qty=payload.qty,
        price_estimate=0.0,
    )
    req_payload = payload.model_dump()
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/binance/test-order",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached

    result = execute_binance_test_order_for_user(
        user_id=current_user.id,
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
    )
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/binance/test-order",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=result,
    )
    return result


@router.post("/execution/ibkr/test-order", response_model=IbkrTestOrderOut)
def execution_ibkr_test_order(
    payload: IbkrTestOrderRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="test_order",
        exchange="IBKR",
    )
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="IBKR",
    )
    assert_exposure_limits(
        db=db,
        current_user=current_user,
        exchange="IBKR",
        symbol=payload.symbol,
        qty=payload.qty,
        price_estimate=0.0,
    )
    req_payload = payload.model_dump()
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/ibkr/test-order",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached

    result = execute_ibkr_test_order_for_user(
        user_id=current_user.id,
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
    )
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/ibkr/test-order",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=result,
    )
    return result


@router.get("/execution/binance/account-status", response_model=AccountStatusOut)
def execution_binance_account_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="account_status",
        exchange="BINANCE",
    )
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
    )
    return get_binance_account_status_for_user(user_id=current_user.id)


@router.get("/execution/ibkr/account-status", response_model=AccountStatusOut)
def execution_ibkr_account_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="account_status",
        exchange="IBKR",
    )
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="IBKR",
    )
    return get_ibkr_account_status_for_user(user_id=current_user.id)


@router.post("/security/reencrypt-exchange-secrets", response_model=ReencryptSecretsOut)
def security_reencrypt_exchange_secrets(
    payload: ReencryptSecretsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = reencrypt_exchange_secrets(
        db=db,
        old_key=payload.old_key,
        new_key=payload.new_key,
        dry_run=payload.dry_run,
        new_version=payload.new_version,
        batch_size=payload.batch_size,
        canary_count=payload.canary_count,
    )
    log_audit_event(
        db,
        action="security.key_rotation.reencrypt",
        user_id=current_user.id,
        entity_type="security",
        details={
            "dry_run": payload.dry_run,
            "updated": result["updated"],
            "failed": result.get("failed", 0),
            "new_version": payload.new_version,
            "batch_size": payload.batch_size,
            "canary_count": payload.canary_count,
        },
    )
    db.commit()
    return result


@router.get("/security/posture", response_model=SecurityPostureOut)
def security_posture(
    real_only: bool = False,
    max_secret_age_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    now, posture_rows, missing_2fa, stale_secrets = _build_security_posture_rows(
        db,
        tenant_id=_tenant_id(current_user),
        real_only=real_only,
        max_secret_age_days=max_secret_age_days,
    )

    log_audit_event(
        db,
        action="security.posture.read",
        user_id=current_user.id,
        entity_type="security",
        details={
            "real_only": real_only,
            "max_secret_age_days": max_secret_age_days,
            "users": len(posture_rows),
            "missing_2fa": missing_2fa,
            "stale_secrets": stale_secrets,
        },
    )
    db.commit()

    return SecurityPostureOut(
        generated_at=now.isoformat(),
        max_secret_age_days=max_secret_age_days,
        real_only=real_only,
        summary=SecurityPostureSummaryOut(
            total_users=len(posture_rows),
            users_missing_2fa=missing_2fa,
            users_with_stale_secrets=stale_secrets,
        ),
        users=posture_rows,
    )


def _max_dt(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    out = max(vals)
    if out.tzinfo is None:
        out = out.replace(tzinfo=timezone.utc)
    return out


@router.post("/admin/cleanup-smoke-users", response_model=CleanupSmokeUsersOut)
def cleanup_smoke_users(
    dry_run: bool = True,
    older_than_days: int = 14,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(0, older_than_days))
    smoke_users = db.execute(
        select(User)
        .where(
            User.email.like("smoke.%"),
            User.tenant_id == _tenant_id(current_user),
        )
        .order_by(User.email.asc())
    ).scalars().all()

    rows: list[CleanupSmokeUsersUserOut] = []
    eligible_ids: list[str] = []

    for u in smoke_users:
        last_audit = db.execute(
            select(func.max(AuditLog.created_at)).where(AuditLog.user_id == u.id)
        ).scalar_one()
        last_position_open = db.execute(
            select(func.max(Position.opened_at)).where(Position.user_id == u.id)
        ).scalar_one()
        last_position_close = db.execute(
            select(func.max(Position.closed_at)).where(Position.user_id == u.id)
        ).scalar_one()
        last_signal = db.execute(
            select(func.max(Signal.updated_at)).where(Signal.user_id == u.id)
        ).scalar_one()
        last_secret = db.execute(
            select(func.max(ExchangeSecret.updated_at)).where(ExchangeSecret.user_id == u.id)
        ).scalar_one()
        last_assignment = db.execute(
            select(func.max(StrategyAssignment.updated_at)).where(StrategyAssignment.user_id == u.id)
        ).scalar_one()

        last_activity = _max_dt(
            [
                last_audit,
                last_position_open,
                last_position_close,
                last_signal,
                last_secret,
                last_assignment,
            ]
        )
        eligible = last_activity is None or last_activity < cutoff
        if eligible:
            eligible_ids.append(u.id)

        rows.append(
            CleanupSmokeUsersUserOut(
                user_id=u.id,
                email=u.email,
                last_activity_at=last_activity.isoformat() if last_activity else None,
                eligible_for_delete=eligible,
            )
        )

    deleted = 0
    if not dry_run and eligible_ids:
        db.query(AuditLog).filter(AuditLog.user_id.in_(eligible_ids)).delete(synchronize_session=False)
        db.query(DailyRiskState).filter(DailyRiskState.user_id.in_(eligible_ids)).delete(synchronize_session=False)
        db.query(Position).filter(Position.user_id.in_(eligible_ids)).delete(synchronize_session=False)
        db.query(Signal).filter(Signal.user_id.in_(eligible_ids)).delete(synchronize_session=False)
        db.query(ExchangeSecret).filter(ExchangeSecret.user_id.in_(eligible_ids)).delete(synchronize_session=False)
        db.query(StrategyAssignment).filter(StrategyAssignment.user_id.in_(eligible_ids)).delete(synchronize_session=False)
        db.query(UserTwoFactor).filter(UserTwoFactor.user_id.in_(eligible_ids)).delete(synchronize_session=False)
        deleted = db.query(User).filter(User.id.in_(eligible_ids)).delete(synchronize_session=False)

    log_audit_event(
        db,
        action="ops.cleanup.smoke_users",
        user_id=current_user.id,
        entity_type="ops",
        details={
            "dry_run": dry_run,
            "older_than_days": older_than_days,
            "scanned": len(smoke_users),
            "eligible": len(eligible_ids),
            "deleted": deleted,
        },
    )
    db.commit()

    return CleanupSmokeUsersOut(
        dry_run=dry_run,
        older_than_days=older_than_days,
        scanned=len(smoke_users),
        eligible=len(eligible_ids),
        deleted=deleted,
        users=rows,
    )


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
def dashboard_summary(
    real_only: bool = True,
    max_secret_age_days: int = 30,
    recent_hours: int = 24,
    email_contains: Optional[str] = None,
    exchange: str = "ALL",
    include_service_users: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    now, posture_rows, missing_2fa, stale_secrets = _build_security_posture_rows(
        db,
        tenant_id=_tenant_id(current_user),
        real_only=real_only,
        max_secret_age_days=max_secret_age_days,
    )
    today = today_colombia()

    posture_map = {row.user_id: row for row in posture_rows}
    user_status_rows: list[DashboardUserOut] = []
    profile_agg: dict[str, dict[str, float]] = {}
    trades_today_total = 0
    open_positions_total = 0
    blocked_open_attempts_total = 0

    users = db.execute(
        select(User)
        .where(User.tenant_id == _tenant_id(current_user))
        .order_by(User.email.asc())
    ).scalars().all()
    for user in users:
        if user.id not in posture_map:
            continue
        email_l = (user.email or "").lower()
        if not include_service_users and email_l.startswith("ops.bot."):
            continue
        if email_contains and email_contains.lower() not in (user.email or "").lower():
            continue

        profile = resolve_risk_profile(db, user.id, user.email)
        p = posture_map[user.id]
        exchange_u = (exchange or "ALL").upper()
        if exchange_u == "BINANCE" and not p.binance_secret_configured:
            continue
        if exchange_u == "IBKR" and not p.ibkr_secret_configured:
            continue

        dr = (
            db.execute(
                select(DailyRiskState).where(
                    DailyRiskState.user_id == user.id,
                    DailyRiskState.day == today,
                )
            )
            .scalar_one_or_none()
        )
        open_positions = db.execute(
            select(func.count())
            .select_from(Position)
            .where(Position.user_id == user.id, Position.status == "OPEN")
        ).scalar_one()
        blocked_today = db.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.user_id == user.id,
                AuditLog.action.like("position.open.blocked.%"),
                func.date(AuditLog.created_at) == str(today),
            )
        ).scalar_one()

        trades_today = int(dr.trades_today) if dr else 0
        realized_pnl_today = float(dr.realized_pnl_today) if dr else 0.0

        trades_today_total += trades_today
        open_positions_total += int(open_positions)
        blocked_open_attempts_total += int(blocked_today)

        profile_name = str(profile["profile_name"])
        max_trades_profile = int(profile["max_trades_per_day"])
        bucket = profile_agg.setdefault(
            profile_name,
            {
                "users_count": 0,
                "trades_today_total": 0,
                "blocked_open_attempts_total": 0,
                "realized_pnl_today_total": 0.0,
                "max_trades_capacity_total": 0,
            },
        )
        bucket["users_count"] += 1
        bucket["trades_today_total"] += trades_today
        bucket["blocked_open_attempts_total"] += int(blocked_today)
        bucket["realized_pnl_today_total"] += realized_pnl_today
        bucket["max_trades_capacity_total"] += max_trades_profile

        user_status_rows.append(
            DashboardUserOut(
                user_id=user.id,
                email=user.email,
                role=user.role,
                risk_profile=profile["profile_name"],
                two_factor_enabled=bool(p.two_factor_enabled),
                binance_secret_configured=bool(p.binance_secret_configured),
                ibkr_secret_configured=bool(p.ibkr_secret_configured),
                trades_today=trades_today,
                open_positions_now=int(open_positions),
                blocked_open_attempts_today=int(blocked_today),
                realized_pnl_today=realized_pnl_today,
            )
        )

    scope_user_ids = [u.user_id for u in user_status_rows]
    profile_productivity: list[DashboardProfileProductivityOut] = []
    for profile_name in sorted(profile_agg.keys()):
        p = profile_agg[profile_name]
        users_count = int(p["users_count"])
        trades_total = int(p["trades_today_total"])
        blocked_total = int(p["blocked_open_attempts_total"])
        pnl_total = float(p["realized_pnl_today_total"])
        capacity = int(p["max_trades_capacity_total"])
        avg_pnl = round((pnl_total / users_count), 4) if users_count > 0 else 0.0
        util = round((trades_total / capacity) * 100.0, 2) if capacity > 0 else 0.0
        profile_productivity.append(
            DashboardProfileProductivityOut(
                risk_profile=profile_name,
                users_count=users_count,
                trades_today_total=trades_total,
                blocked_open_attempts_total=blocked_total,
                realized_pnl_today_total=round(pnl_total, 4),
                avg_realized_pnl_per_user=avg_pnl,
                trades_utilization_pct=util,
            )
        )

    cutoff = now - timedelta(hours=recent_hours)
    errors_last_24h = db.execute(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.created_at >= cutoff,
            or_(
                AuditLog.action.like("%.error"),
                AuditLog.action.like("execution.blocked.%"),
            ),
        )
    ).scalar_one()

    pretrade_blocked_last_24h = db.execute(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "pretrade.check.blocked",
            AuditLog.created_at >= cutoff,
        )
    ).scalar_one()

    trends_7d: list[DashboardTrendDayOut] = []
    for i in range(6, -1, -1):
        day_i = today - timedelta(days=i)

        if scope_user_ids:
            trades_agg = db.execute(
                select(func.coalesce(func.sum(DailyRiskState.trades_today), 0)).where(
                    DailyRiskState.day == day_i,
                    DailyRiskState.user_id.in_(scope_user_ids),
                )
            ).scalar_one()
            blocked_agg = db.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.user_id.in_(scope_user_ids),
                    AuditLog.action.like("position.open.blocked.%"),
                    func.date(AuditLog.created_at) == str(day_i),
                )
            ).scalar_one()
            errors_agg = db.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.user_id.in_(scope_user_ids),
                    func.date(AuditLog.created_at) == str(day_i),
                    or_(
                        AuditLog.action.like("%.error"),
                        AuditLog.action.like("execution.blocked.%"),
                    ),
                )
            ).scalar_one()
        else:
            trades_agg = 0
            blocked_agg = 0
            errors_agg = 0

        trends_7d.append(
            DashboardTrendDayOut(
                day=str(day_i),
                trades_total=int(trades_agg or 0),
                blocked_open_attempts_total=int(blocked_agg or 0),
                errors_total=int(errors_agg or 0),
            )
        )

    overall_status = "green"
    if missing_2fa > 0 or stale_secrets > 0:
        overall_status = "red"
    elif blocked_open_attempts_total > 0:
        overall_status = "yellow"

    return DashboardSummaryOut(
        generated_at=now.isoformat(),
        day=str(today),
        overall_status=overall_status,
        generated_for=current_user.email,
        security=DashboardSecurityOut(
            total_users=len(posture_rows),
            users_missing_2fa=missing_2fa,
            users_with_stale_secrets=stale_secrets,
            max_secret_age_days=max_secret_age_days,
        ),
        operations=DashboardOperationsOut(
            trades_today_total=trades_today_total,
            open_positions_total=open_positions_total,
            blocked_open_attempts_total=blocked_open_attempts_total,
        ),
        recent_events=DashboardEventsOut(
            errors_last_24h=int(errors_last_24h),
            pretrade_blocked_last_24h=int(pretrade_blocked_last_24h),
        ),
        profile_productivity=profile_productivity,
        trends_7d=trends_7d,
        users=user_status_rows,
    )


@router.get("/admin/snapshot/daily")
def admin_snapshot_daily(
    real_only: bool = True,
    max_secret_age_days: int = 30,
    recent_hours: int = 24,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    dashboard = dashboard_summary(
        real_only=real_only,
        max_secret_age_days=max_secret_age_days,
        recent_hours=recent_hours,
        email_contains=None,
        exchange="ALL",
        include_service_users=False,
        db=db,
        current_user=current_user,
    )
    backoffice_sum = backoffice_summary(
        real_only=real_only,
        max_secret_age_days=max_secret_age_days,
        db=db,
        current_user=current_user,
    )
    backoffice_usr = backoffice_users(
        real_only=real_only,
        db=db,
        current_user=current_user,
    )
    posture = security_posture(
        real_only=real_only,
        max_secret_age_days=max_secret_age_days,
        db=db,
        current_user=current_user,
    )
    risk = daily_risk_compare(
        real_only=real_only,
        db=db,
        current_user=current_user,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_for": current_user.email,
        "real_only": real_only,
        "dashboard": dashboard,
        "backoffice_summary": backoffice_sum,
        "backoffice_users": backoffice_usr,
        "security_posture": posture,
        "risk_daily_compare": risk,
    }


@router.get("/admin/readiness/daily-gate")
def admin_readiness_daily_gate(
    real_only: bool = True,
    include_service_users: bool = False,
    max_secret_age_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    tenant = _tenant_id(current_user)
    now, posture_rows, missing_2fa, stale_secrets = _build_security_posture_rows(
        db,
        tenant_id=tenant,
        real_only=real_only,
        max_secret_age_days=max_secret_age_days,
    )
    readiness = _build_operational_readiness_report(
        db,
        tenant_id=tenant,
        real_only=real_only,
        include_service_users=include_service_users,
    )
    trading_enabled = get_trading_enabled(db)

    checks = [
        {
            "name": "security_missing_2fa_zero",
            "passed": int(missing_2fa) == 0,
            "detail": f"missing_2fa={missing_2fa}",
        },
        {
            "name": "security_stale_secrets_zero",
            "passed": int(stale_secrets) == 0,
            "detail": f"stale_secrets={stale_secrets}",
        },
        {
            "name": "readiness_missing_zero",
            "passed": int(readiness["summary"]["missing_users"]) == 0,
            "detail": f"missing_users={readiness['summary']['missing_users']}",
        },
        {
            "name": "trading_control_known",
            "passed": isinstance(trading_enabled, bool),
            "detail": f"trading_enabled={trading_enabled}",
        },
    ]
    passed = all(bool(c["passed"]) for c in checks)
    return {
        "generated_at": now.isoformat(),
        "generated_for": current_user.email,
        "real_only": real_only,
        "include_service_users": include_service_users,
        "max_secret_age_days": max_secret_age_days,
        "passed": passed,
        "checks": checks,
        "security_summary": {
            "users_in_scope": len(posture_rows),
            "users_missing_2fa": int(missing_2fa),
            "users_with_stale_secrets": int(stale_secrets),
        },
        "readiness_summary": readiness["summary"],
    }


@router.get("/admin/ci/status", response_model=CIStatusOut)
def admin_ci_status(
    current_user: User = Depends(require_any_role("admin", "operator")),
):
    _ = current_user
    return _build_ci_status_snapshot()


@router.get("/admin/ci/log-hint", response_model=CILogHintOut)
def admin_ci_log_hint(
    current_user: User = Depends(require_any_role("admin", "operator")),
):
    _ = current_user
    snap = _build_ci_status_snapshot()
    run_map = {
        w.key: w.html_url
        for w in snap.workflows
        if w.html_url
    }
    line = (
        f"Integration: {run_map.get('integration', '<sin_run>')} / "
        f"Smoke: {run_map.get('smoke', '<sin_run>')} / "
        f"DR: {run_map.get('dr_drill', '<sin_run>')}"
    )
    return CILogHintOut(
        generated_at=datetime.now(timezone.utc).isoformat(),
        line_for_registro_operacion_diaria=line,
        runs=run_map,
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    return _render_ops_template("ops_console_v2.html")
    return HTMLResponse(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Ops Dashboard</title>
  <style>
    :root { --bg:#f5f7f9; --card:#ffffff; --text:#142033; --muted:#5b677a; --ok:#117a3e; --warn:#a35b00; --bad:#b42318; --line:#dde3ea; }
    * { box-sizing:border-box; }
    body { margin:0; font-family: "Segoe UI", Tahoma, sans-serif; background:linear-gradient(180deg,#eef4ff 0%,var(--bg) 45%); color:var(--text); }
    .wrap { max-width:1100px; margin:24px auto; padding:0 16px 32px; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px; margin-bottom:14px; }
    h1 { margin:0 0 6px; font-size:28px; }
    .muted { color:var(--muted); font-size:13px; }
    .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
    input { width:420px; max-width:100%; border:1px solid var(--line); border-radius:10px; padding:10px 12px; }
    button { border:0; border-radius:10px; padding:10px 14px; font-weight:600; cursor:pointer; background:#0b62d6; color:#fff; }
    .ghost { background:#eef3fb; color:#0b62d6; border:1px solid #bcd0f4; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px; }
    .kpi { border:1px solid var(--line); border-radius:10px; padding:10px; }
    .kpi .v { font-size:24px; font-weight:700; }
    .trend-grid { display:grid; grid-template-columns:1fr; gap:8px; }
    table { width:100%; border-collapse:collapse; }
    th,td { border-bottom:1px solid var(--line); text-align:left; padding:8px 6px; font-size:13px; }
    .badge { display:inline-block; padding:3px 9px; border-radius:999px; font-weight:700; font-size:12px; color:#fff; }
    .tag { display:inline-block; padding:2px 8px; border-radius:999px; font-weight:700; font-size:11px; margin-right:4px; }
    .tag-binance { background:#fff3d0; color:#7a5200; border:1px solid #e7c060; }
    .tag-ibkr { background:#dcecff; color:#164a8a; border:1px solid #90b6ea; }
    .tag-off { background:#f1f4f8; color:#667085; border:1px solid #d0d7e2; }
    .green { background:var(--ok); }
    .yellow { background:var(--warn); }
    .red { background:var(--bad); }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Ops Dashboard</h1>
      <div class="muted">Single-screen view for health, security posture and daily operations.</div>
      <div class="row" style="margin-top:12px">
        <input id="token" placeholder="Paste admin bearer token here" />
        <button id="load">Load</button>
        <label style="display:flex;align-items:center;gap:6px;font-size:12px;color:#445066;">
          <input id="rememberToken" type="checkbox" />
          Remember token
        </label>
        <input id="emailFilter" placeholder="email contains (optional)" />
        <select id="realOnlyFilter" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;">
          <option value="true">real_only=true</option>
          <option value="false">real_only=false</option>
        </select>
        <select id="exchangeFilter" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;">
          <option value="ALL">ALL</option>
          <option value="BINANCE">BINANCE</option>
          <option value="IBKR">IBKR</option>
        </select>
        <button id="resetBtn" class="ghost">Reset Filters</button>
        <button id="incidentBtn" class="ghost">Open Incident</button>
      </div>
      <div class="row" style="margin-top:10px">
        <input id="loginEmail" placeholder="admin email (for auto token)" />
        <input id="loginPassword" type="password" placeholder="admin password" />
        <input id="loginOtp" placeholder="otp (if required)" style="width:180px" />
        <button id="loginBtn" class="ghost">Get Token</button>
      </div>
      <div class="muted" id="stamp" style="margin-top:8px">Waiting for token...</div>
    </div>
    <div class="card">
      <div class="row"><strong>Overall status:</strong> <span id="overall" class="badge yellow">unknown</span></div>
      <div class="grid" style="margin-top:10px">
        <div class="kpi"><div class="muted">Users in scope</div><div id="k_users" class="v">-</div></div>
        <div class="kpi"><div class="muted">Missing 2FA</div><div id="k_2fa" class="v">-</div></div>
        <div class="kpi"><div class="muted">Stale secrets</div><div id="k_stale" class="v">-</div></div>
        <div class="kpi"><div class="muted">Trades today</div><div id="k_trades" class="v">-</div></div>
        <div class="kpi"><div class="muted">Open positions</div><div id="k_open" class="v">-</div></div>
        <div class="kpi"><div class="muted">Blocked opens today</div><div id="k_blocked" class="v">-</div></div>
      </div>
    </div>
    <div class="card">
      <strong>Profile Productivity</strong>
      <div class="muted" style="margin:4px 0 10px">Daily comparison by risk profile (conservative vs loose).</div>
      <table>
        <thead>
          <tr><th>Risk profile</th><th>Users</th><th>Trades</th><th>Utilization %</th><th>Blocked opens</th><th>PnL total</th><th>Avg PnL/user</th></tr>
        </thead>
        <tbody id="profileBody"><tr><td colspan="7" class="muted">No profile data yet</td></tr></tbody>
      </table>
    </div>
    <div class="card">
      <strong>7-day trend</strong>
      <div class="muted" style="margin:4px 0 10px">Trades, blocked opens and errors per day.</div>
      <table>
        <thead>
          <tr><th>Day</th><th>Trades</th><th>Blocked opens</th><th>Errors</th></tr>
        </thead>
        <tbody id="trendBody"><tr><td colspan="4" class="muted">No trend data yet</td></tr></tbody>
      </table>
    </div>
    <div class="card">
      <strong>Users</strong>
      <table>
        <thead>
          <tr><th>Email</th><th>Role</th><th>Risk profile</th><th>Exchanges</th><th>2FA</th><th>Trades</th><th>Open</th><th>Blocked</th><th>Realized PnL</th></tr>
        </thead>
        <tbody id="tbody"><tr><td colspan="9" class="muted">No data yet</td></tr></tbody>
      </table>
    </div>
    <div class="card">
      <strong>User Admin</strong>
      <div class="muted" style="margin:4px 0 10px">Manage users, roles, passwords, risk profile and exchange secrets without SQL.</div>
      <div class="row" style="margin-bottom:10px">
        <input id="newUserEmail" placeholder="new user email" />
        <input id="newUserPassword" type="password" placeholder="new user password" />
        <button id="createUserBtn" class="ghost">Create user</button>
      </div>
      <div class="row" style="margin-bottom:10px">
        <select id="adminUserSelect" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;min-width:320px;"></select>
        <button id="refreshUsersBtn" class="ghost">Refresh users</button>
      </div>
      <div class="row" style="margin-bottom:10px">
        <select id="adminRoleSelect" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;">
          <option value="trader">trader</option>
          <option value="admin">admin</option>
          <option value="disabled">disabled</option>
        </select>
        <button id="setRoleBtn">Set role</button>
        <input id="newEmailInput" placeholder="new email (optional)" />
        <button id="setEmailBtn" class="ghost">Update email</button>
      </div>
      <div class="row" style="margin-bottom:10px">
        <select id="adminRiskSelect" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;min-width:260px;"></select>
        <button id="setRiskBtn">Set risk profile</button>
        <button id="clearRiskBtn" class="ghost">Clear risk override</button>
      </div>
      <div class="row" style="margin-bottom:10px">
        <input id="newPasswordInput" type="password" placeholder="new password (min 8 chars)" />
        <button id="setPasswordBtn">Set password</button>
      </div>
      <div class="row" style="margin-bottom:10px">
        <select id="adminExchangeSelect" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;">
          <option value="BINANCE">BINANCE</option>
          <option value="IBKR">IBKR</option>
        </select>
        <input id="adminApiKey" placeholder="API key" />
        <input id="adminApiSecret" type="password" placeholder="API secret" />
        <button id="setSecretBtn">Save secret</button>
        <button id="deleteSecretBtn" class="ghost">Delete secret</button>
      </div>
      <div class="muted" id="adminMsg">Admin panel idle.</div>
      <table style="margin-top:10px">
        <thead>
          <tr><th>User</th><th>Role</th><th>Risk profile</th><th>Source</th></tr>
        </thead>
        <tbody id="adminUsersBody"><tr><td colspan="4" class="muted">Load dashboard first</td></tr></tbody>
      </table>
    </div>
    <div class="card">
      <strong>User Readiness</strong>
      <div class="muted" style="margin:4px 0 10px">Single table with operability status by user.</div>
      <table>
        <thead>
          <tr><th>User</th><th>Role</th><th>2FA</th><th>Assignments</th><th>Secrets</th><th>Status</th><th>Main reason</th></tr>
        </thead>
        <tbody id="readinessBody"><tr><td colspan="7" class="muted">Load dashboard first</td></tr></tbody>
      </table>
    </div>
  </div>
  <script>
    const byId = (id) => document.getElementById(id);
    const TOKEN_SESSION_KEY = "ops_dashboard_token_session";
    const TOKEN_PERSIST_KEY = "ops_dashboard_token_persist";
    const TOKEN_REMEMBER_KEY = "ops_dashboard_token_remember";
    const LOGIN_EMAIL_KEY = "ops_dashboard_login_email";
    const DEFAULT_RISK_PROFILES = ["model2_conservador_productivo", "modelo_suelto_controlado"];
    const adminState = { users: [], riskProfiles: [...DEFAULT_RISK_PROFILES] };

    function saveToken(token) {
      sessionStorage.setItem(TOKEN_SESSION_KEY, token || "");
      const remember = byId("rememberToken").checked;
      localStorage.setItem(TOKEN_REMEMBER_KEY, remember ? "1" : "0");
      if (remember) {
        localStorage.setItem(TOKEN_PERSIST_KEY, token || "");
      } else {
        localStorage.removeItem(TOKEN_PERSIST_KEY);
      }
    }

    function loadStoredToken() {
      const remember = localStorage.getItem(TOKEN_REMEMBER_KEY) === "1";
      byId("rememberToken").checked = remember;
      const token = remember
        ? (localStorage.getItem(TOKEN_PERSIST_KEY) || "")
        : (sessionStorage.getItem(TOKEN_SESSION_KEY) || "");
      if (token) byId("token").value = token;
      const email = localStorage.getItem(LOGIN_EMAIL_KEY) || "";
      if (email) byId("loginEmail").value = email;
    }

    function setOverall(v) {
      const el = byId("overall");
      el.textContent = v || "unknown";
      el.className = "badge " + (v === "green" ? "green" : v === "red" ? "red" : "yellow");
    }

    function setAdminMsg(msg, isError = false) {
      const el = byId("adminMsg");
      el.textContent = msg;
      el.style.color = isError ? "var(--bad)" : "var(--muted)";
    }

    function authHeaders(token) {
      return {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      };
    }

    async function apiJson(path, token, opts = {}) {
      const headers = opts.headers || authHeaders(token);
      const res = await fetch(path, { ...opts, headers });
      const contentType = res.headers.get("content-type") || "";
      const data = contentType.includes("application/json")
        ? await res.json()
        : { detail: await res.text() };
      if (!res.ok) {
        throw new Error(data.detail || `${res.status} request failed`);
      }
      return data;
    }

    function selectedUserId() {
      return (byId("adminUserSelect").value || "").trim();
    }

    function selectedUserObj() {
      const id = selectedUserId();
      return adminState.users.find((u) => u.id === id) || null;
    }

    function renderRiskProfileOptions() {
      byId("adminRiskSelect").innerHTML = adminState.riskProfiles
        .map((p) => `<option value="${p}">${p}</option>`)
        .join("");
    }

    function renderAdminUsers(preferredUserId = "") {
      const users = adminState.users || [];
      const current = preferredUserId || selectedUserId();
      byId("adminUserSelect").innerHTML = users
        .map((u) => `<option value="${u.id}">${u.email} | ${u.role} | ${u.risk_profile}</option>`)
        .join("");
      if (current && users.some((u) => u.id === current)) {
        byId("adminUserSelect").value = current;
      }

      byId("adminUsersBody").innerHTML = users.map((u) => `<tr>
        <td>${u.email}</td><td>${u.role}</td><td>${u.risk_profile || "-"}</td><td>${u.risk_profile_source || "-"}</td>
      </tr>`).join("") || '<tr><td colspan="4" class="muted">No users found</td></tr>';
    }

    async function loadAdminUsers(preferredUserId = "") {
      const token = byId("token").value.trim();
      if (!token) return;
      const users = await apiJson("/users", token, { method: "GET", headers: { Authorization: `Bearer ${token}` } });
      adminState.users = users || [];
      renderAdminUsers(preferredUserId);
      await renderReadinessTable();
    }

    function fmtAssignments(a) {
      const keys = Object.keys(a || {}).sort();
      if (!keys.length) return "none";
      return keys.map((k) => `${k}:${a[k] ? "on" : "off"}`).join(" | ");
    }

    async function renderReadinessTable() {
      const token = byId("token").value.trim();
      if (!token) return;
      const users = adminState.users || [];
      if (!users.length) {
        byId("readinessBody").innerHTML = '<tr><td colspan="7" class="muted">No users</td></tr>';
        return;
      }
      const rows = await Promise.all(users.map(async (u) => {
        try {
          const r = await apiJson(`/users/${u.id}/readiness-check`, token, {
            method: "GET",
            headers: { Authorization: `Bearer ${token}` },
          });
          const failed = (r.checks || []).find((c) => !c.passed);
          return {
            email: r.email,
            role: r.role,
            two_factor_enabled: r.two_factor_enabled,
            assignments: fmtAssignments(r.assignments),
            secrets: (r.secrets_configured || []).join(", ") || "none",
            ready: !!r.ready,
            reason: failed ? `${failed.name}: ${failed.detail}` : "ok",
          };
        } catch (e) {
          return {
            email: u.email,
            role: u.role,
            two_factor_enabled: false,
            assignments: "n/a",
            secrets: "n/a",
            ready: false,
            reason: String(e.message || e),
          };
        }
      }));
      byId("readinessBody").innerHTML = rows.map((r) => `<tr>
        <td>${r.email}</td>
        <td>${r.role}</td>
        <td>${r.two_factor_enabled ? "yes" : "no"}</td>
        <td>${r.assignments}</td>
        <td>${r.secrets}</td>
        <td><span class="badge ${r.ready ? "green" : "red"}">${r.ready ? "READY" : "MISSING"}</span></td>
        <td>${r.reason}</td>
      </tr>`).join("");
    }

    async function runReadinessCheck(userId) {
      const token = byId("token").value.trim();
      if (!token || !userId) return;
      const readiness = await apiJson(`/users/${userId}/readiness-check`, token, {
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
      });
      const failed = (readiness.checks || []).filter((c) => !c.passed);
      if (!failed.length) {
        setAdminMsg(`Readiness OK for ${readiness.email}`);
        return;
      }
      const first = failed[0];
      setAdminMsg(`Readiness warning for ${readiness.email}: ${first.name} (${first.detail})`, true);
    }

    async function loadRiskProfiles() {
      const token = byId("token").value.trim();
      if (!token) return;
      try {
        const profiles = await apiJson("/users/risk-profiles", token, { method: "GET", headers: { Authorization: `Bearer ${token}` } });
        adminState.riskProfiles = (profiles && profiles.length) ? profiles : [...DEFAULT_RISK_PROFILES];
      } catch (_) {
        adminState.riskProfiles = [...DEFAULT_RISK_PROFILES];
      }
      renderRiskProfileOptions();
    }

    function fill(d) {
      setOverall(d.overall_status);
      byId("stamp").textContent = `Generated: ${d.generated_at} | Day: ${d.day} | For: ${d.generated_for}`;
      byId("k_users").textContent = d.security.total_users;
      byId("k_2fa").textContent = d.security.users_missing_2fa;
      byId("k_stale").textContent = d.security.users_with_stale_secrets;
      byId("k_trades").textContent = d.operations.trades_today_total;
      byId("k_open").textContent = d.operations.open_positions_total;
      byId("k_blocked").textContent = d.operations.blocked_open_attempts_total;
      byId("profileBody").innerHTML = (d.profile_productivity || []).map(p => `<tr>
        <td>${p.risk_profile}</td><td>${p.users_count}</td><td>${p.trades_today_total}</td><td>${p.trades_utilization_pct}</td><td>${p.blocked_open_attempts_total}</td><td>${p.realized_pnl_today_total}</td><td>${p.avg_realized_pnl_per_user}</td>
      </tr>`).join("") || '<tr><td colspan="7" class="muted">No profile data yet</td></tr>';
      byId("trendBody").innerHTML = (d.trends_7d || []).map(t => `<tr>
        <td>${t.day}</td><td>${t.trades_total}</td><td>${t.blocked_open_attempts_total}</td><td>${t.errors_total}</td>
      </tr>`).join("") || '<tr><td colspan="4" class="muted">No trend data yet</td></tr>';
      byId("tbody").innerHTML = d.users.map(u => `<tr>
        <td>${u.email}</td><td>${u.role}</td><td>${u.risk_profile}</td>
        <td>
          <span class="tag ${u.binance_secret_configured ? "tag-binance" : "tag-off"}">BINANCE ${u.binance_secret_configured ? "on" : "off"}</span>
          <span class="tag ${u.ibkr_secret_configured ? "tag-ibkr" : "tag-off"}">IBKR ${u.ibkr_secret_configured ? "on" : "off"}</span>
        </td>
        <td>${u.two_factor_enabled ? "yes" : "no"}</td>
        <td>${u.trades_today}</td><td>${u.open_positions_now}</td><td>${u.blocked_open_attempts_today}</td><td>${u.realized_pnl_today}</td>
      </tr>`).join("") || '<tr><td colspan="9" class="muted">No users in scope</td></tr>';
    }
    async function load() {
      const token = byId("token").value.trim();
      if (!token) return;
      saveToken(token);
      const email = encodeURIComponent(byId("emailFilter").value.trim());
      const exchange = encodeURIComponent(byId("exchangeFilter").value || "ALL");
      const realOnly = encodeURIComponent(byId("realOnlyFilter").value || "true");
      const qs = `/ops/dashboard/summary?real_only=${realOnly}&email_contains=${email}&exchange=${exchange}`;
      const res = await fetch(qs, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Dashboard request failed");
      fill(data);
      await loadRiskProfiles();
      await loadAdminUsers();
    }
    byId("load").addEventListener("click", async () => {
      try { await load(); } catch (e) { byId("stamp").textContent = String(e.message || e); setOverall("red"); }
    });
    byId("resetBtn").addEventListener("click", async () => {
      byId("emailFilter").value = "";
      byId("realOnlyFilter").value = "true";
      byId("exchangeFilter").value = "ALL";
      try { await load(); } catch (e) { byId("stamp").textContent = String(e.message || e); setOverall("red"); }
    });
    byId("rememberToken").addEventListener("change", () => {
      const token = byId("token").value.trim();
      saveToken(token);
    });
    byId("incidentBtn").addEventListener("click", () => {
      const repo = "https://github.com/Gonzalo-Giraldo/crypto-saas";
      const ts = new Date().toISOString();
      const title = encodeURIComponent(`[Ops Dashboard] Incident ${ts}`);
      const body = encodeURIComponent(`Opened from /ops/dashboard\n\n- Timestamp: ${ts}\n- Context: dashboard review\n`);
      window.open(`${repo}/issues/new?title=${title}&body=${body}`, "_blank");
    });
    byId("refreshUsersBtn").addEventListener("click", async () => {
      try {
        const keepId = selectedUserId();
        await loadAdminUsers(keepId);
        await runReadinessCheck(selectedUserId());
        setAdminMsg("Users refreshed.");
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("createUserBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const email = byId("newUserEmail").value.trim();
        const password = byId("newUserPassword").value;
        if (!token) throw new Error("Token required");
        if (!email || !password) throw new Error("Email and password are required");
        await apiJson("/users", token, {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        byId("newUserPassword").value = "";
        await loadAdminUsers(selectedUserId());
        await runReadinessCheck(selectedUserId());
        setAdminMsg(`User created: ${email}`);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("setRoleBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const user = selectedUserObj();
        const role = byId("adminRoleSelect").value;
        if (!token) throw new Error("Token required");
        if (!user) throw new Error("Select a user first");
        await apiJson(`/users/${user.id}/role`, token, {
          method: "PATCH",
          body: JSON.stringify({ role }),
        });
        await loadAdminUsers(user.id);
        setAdminMsg(`Role updated for ${user.email}: ${role}`);
        await runReadinessCheck(user.id);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("setEmailBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const user = selectedUserObj();
        const email = byId("newEmailInput").value.trim();
        if (!token) throw new Error("Token required");
        if (!user) throw new Error("Select a user first");
        if (!email) throw new Error("New email is required");
        await apiJson(`/users/${user.id}/email`, token, {
          method: "PATCH",
          body: JSON.stringify({ email }),
        });
        byId("newEmailInput").value = "";
        await loadAdminUsers(user.id);
        setAdminMsg(`Email updated for user id ${user.id}`);
        await runReadinessCheck(user.id);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("setRiskBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const user = selectedUserObj();
        const profile_name = byId("adminRiskSelect").value;
        if (!token) throw new Error("Token required");
        if (!user) throw new Error("Select a user first");
        await apiJson(`/users/${user.id}/risk-profile`, token, {
          method: "PUT",
          body: JSON.stringify({ profile_name }),
        });
        await loadAdminUsers(user.id);
        setAdminMsg(`Risk profile updated for ${user.email}: ${profile_name}`);
        await runReadinessCheck(user.id);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("clearRiskBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const user = selectedUserObj();
        if (!token) throw new Error("Token required");
        if (!user) throw new Error("Select a user first");
        await apiJson(`/users/${user.id}/risk-profile`, token, {
          method: "PUT",
          body: JSON.stringify({ profile_name: null }),
        });
        await loadAdminUsers(user.id);
        setAdminMsg(`Risk override cleared for ${user.email}`);
        await runReadinessCheck(user.id);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("setPasswordBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const user = selectedUserObj();
        const new_password = byId("newPasswordInput").value;
        if (!token) throw new Error("Token required");
        if (!user) throw new Error("Select a user first");
        if (!new_password || new_password.length < 8) throw new Error("Password must be at least 8 characters");
        await apiJson(`/users/${user.id}/password`, token, {
          method: "PUT",
          body: JSON.stringify({ new_password }),
        });
        byId("newPasswordInput").value = "";
        setAdminMsg(`Password updated for ${user.email}`);
        await runReadinessCheck(user.id);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("setSecretBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const user = selectedUserObj();
        const exchange = byId("adminExchangeSelect").value;
        const api_key = byId("adminApiKey").value.trim();
        const api_secret = byId("adminApiSecret").value;
        if (!token) throw new Error("Token required");
        if (!user) throw new Error("Select a user first");
        if (!api_key || !api_secret) throw new Error("API key and API secret are required");
        await apiJson(`/users/${user.id}/exchange-secrets`, token, {
          method: "PUT",
          body: JSON.stringify({ exchange, api_key, api_secret }),
        });
        byId("adminApiSecret").value = "";
        setAdminMsg(`Secret saved for ${user.email} (${exchange})`);
        await runReadinessCheck(user.id);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("deleteSecretBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const user = selectedUserObj();
        const exchange = byId("adminExchangeSelect").value;
        if (!token) throw new Error("Token required");
        if (!user) throw new Error("Select a user first");
        await apiJson(`/users/${user.id}/exchange-secrets/${exchange}`, token, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        });
        setAdminMsg(`Secret deleted for ${user.email} (${exchange})`);
        await runReadinessCheck(user.id);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("adminUserSelect").addEventListener("change", async () => {
      try {
        await runReadinessCheck(selectedUserId());
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("loginBtn").addEventListener("click", async () => {
      try {
        const email = byId("loginEmail").value.trim();
        const password = byId("loginPassword").value;
        const otp = byId("loginOtp").value.trim();
        if (!email || !password) {
          throw new Error("Email and password are required");
        }
        localStorage.setItem(LOGIN_EMAIL_KEY, email);
        const body = new URLSearchParams();
        body.set("username", email);
        body.set("password", password);
        if (otp) body.set("otp", otp);
        const res = await fetch("/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: body.toString(),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Login failed");
        const token = data.access_token || "";
        if (!token) throw new Error("No token returned");
        byId("token").value = token;
        saveToken(token);
        byId("loginPassword").value = "";
        byId("loginOtp").value = "";
        await load();
      } catch (e) {
        byId("stamp").textContent = String(e.message || e);
        setOverall("red");
      }
    });
    setInterval(async () => {
      const token = byId("token").value.trim();
      if (!token) return;
      try { await load(); } catch (_) {}
    }, 60000);
    loadStoredToken();
  </script>
</body>
</html>
        """
    )


@router.get("/console", response_class=HTMLResponse)
def ops_console_page():
    return _render_ops_template("ops_console_v2.html")
