# --- Consumo persistente de intent_key por contexto (debe estar a nivel módulo) ---
def build_intent_consumption_key(user_id, broker, intent_key, account_id=None):
    """
    Construye la clave de consumo persistente de intent_key por contexto elegible.
    Si account_id falta, usa 'no-account'.
    """
    acc = account_id if (account_id is not None and str(account_id).strip()) else "no-account"
    return (str(user_id), str(broker), str(intent_key), str(acc))

class IntentConsumptionStore:

    def attach_execution(
        self,
        user_id,
        broker,
        intent_key,
        account_id,
        execution_id,
        execution_id_type,
        symbol=None,
        market=None,
    ):
        key = build_intent_consumption_key(user_id, broker, intent_key, account_id)
        if key not in self._consumption_store:
            return False
        self._consumption_store[key]["broker_execution_id"] = execution_id
        self._consumption_store[key]["broker_execution_id_type"] = execution_id_type
        if symbol is not None:
            self._consumption_store[key]["symbol"] = symbol
        if market is not None:
            self._consumption_store[key]["market"] = market
        self._save_store()
        return True
    def list_recent_consumptions(self, limit=10):
        """
        Devuelve una lista de los consumos recientes de intent_key.
        Cada elemento incluye: intent_key, user_id, broker, account_id, consumed_at (si existe), symbol, market.
        El orden es el actual del store (dict), sin semántica de timestamp si no existe.
        """
        items = list(self._consumption_store.items())
        result = []
        for k, v in items[:limit]:
            entry = {
                'intent_key': k[2],
                'user_id': k[0],
                'broker': k[1],
                'account_id': k[3],
                'consumed_at': v.get('consumed_at') if 'consumed_at' in v else None
            }
            if 'broker_execution_id' in v:
                entry['broker_execution_id'] = v['broker_execution_id']
            if 'broker_execution_id_type' in v:
                entry['broker_execution_id_type'] = v['broker_execution_id_type']
            if 'symbol' in v:
                entry['symbol'] = v['symbol']
            if 'market' in v:
                entry['market'] = v['market']
            result.append(entry)
        return result

    def get_consumption_record(self, user_id, broker, intent_key, account_id=None):
        """
        Consulta read-only de consumo de intent_key por contexto.
        Devuelve dict con campos mínimos y estado encontrado/no encontrado.
        Lee desde DB, no desde JSON local. Devuelve symbol si existe.
        """
        from apps.api.app.db.session import SessionLocal

        intent_id = str(intent_key)
        consumer = self._build_consumer(user_id, broker, account_id)

        db = SessionLocal()
        try:
            from sqlalchemy import text
            row = db.execute(
                text("""
                    SELECT execution_ref, symbol
                    FROM intent_consumptions
                    WHERE intent_id = :intent_id AND consumer = :consumer
                    LIMIT 1
                """),
                {"intent_id": intent_id, "consumer": consumer}
            ).fetchone()

            if row is not None:
                execution_ref, symbol = row
                result = {
                    "found": True,
                    "intent_key": intent_key,
                    "user_id": user_id,
                    "broker": broker,
                    "account_id": account_id if account_id is not None else "no-account",
                    "consumed_at": None,
                }
                if execution_ref:
                    result["broker_execution_id"] = execution_ref
                if symbol:
                    result["symbol"] = symbol
                return result

            return {
                "found": False,
                "intent_key": intent_key,
                "user_id": user_id,
                "broker": broker,
                "account_id": account_id if account_id is not None else "no-account",
                "consumed_at": None,
            }

        finally:
            db.close()

    """
    Almacenamiento persistente mínimo para consumo de intent_key por contexto.
    Reutiliza el patrón de idempotencia (archivo json en disco).
    """
    def __init__(self):
        self._store_path = self._build_store_path()
        self._consumption_store = self._load_store()

    def _build_store_path(self):
        # Deterministically resolve the project root by directory structure (4 levels up from this file)
        here = os.path.abspath(os.path.dirname(__file__))
        project_root = here
        for _ in range(4):
            project_root = os.path.dirname(project_root)
        return os.path.join(project_root, '.intent_consumption_store.json')

    def _serialize_store_key(self, key):
        # key is (user_id, broker, intent_key, account_id)
        return f"{key[0]}::{key[1]}::{key[2]}::{key[3]}"

    def _deserialize_store_key(self, s):
        parts = s.split('::')
        return (parts[0], parts[1], parts[2], parts[3])

    def _load_store(self):
        path = self._store_path
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            store = {}
            for k, v in data.items():
                store[self._deserialize_store_key(k)] = v
            return store
        except Exception:
            return {}

    def _save_store(self):
        path = self._store_path
        data = {self._serialize_store_key(k): v for k, v in self._consumption_store.items()}
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, sort_keys=True)
        except Exception:
            pass


    def has_consumed(self, user_id, broker, intent_key, account_id=None):
        from apps.api.app.db.session import SessionLocal
        intent_id = str(intent_key)
        consumer = self._build_consumer(user_id, broker, account_id)
        db = SessionLocal()
        try:
            result = db.execute(
                "SELECT 1 FROM intent_consumptions WHERE intent_id = %s AND consumer = %s LIMIT 1",
                (intent_id, consumer)
            ).fetchone()
            return result is not None
        finally:
            db.close()

    def register_consumption(self, user_id, broker, intent_key, account_id=None, symbol=None, market=None):
        from apps.api.app.db.session import SessionLocal
        intent_id = str(intent_key)
        consumer = self._build_consumer(user_id, broker, account_id)
        db = SessionLocal()
        try:
            db.execute(
                "INSERT INTO intent_consumptions (intent_id, consumer) VALUES (%s, %s) ON CONFLICT (intent_id, consumer) DO NOTHING",
                (intent_id, consumer)
            )
            db.commit()
        finally:
            db.close()

    def _build_consumer(self, user_id, broker, account_id=None):
        acc = account_id if (account_id is not None and str(account_id).strip()) else "no-account"
        return f"{user_id}:{broker}:{acc}"
import os
import json
class ExecutionResult:
    def __init__(self, **kwargs):
        self._data = kwargs

    def to_dict(self):
        return self._data.copy()

from apps.worker.app.engine.risk_engine import RiskIntent, RiskEngine

def normalize_order_ref(order_ref):
    """
    Normaliza order_ref: strip() y valida no vacío.
    Si es None o vacío tras strip, retorna None (el caller debe manejar el error como hoy).
    No cambia case ni formato.
    """
    if order_ref is None:
        return None
    ref = str(order_ref).strip()
    if not ref:
        return None
    return ref

class MinimalExecutionRuntime:
    def _build_idempotency_key(self, user_id, broker, order_ref, account_id=None):
        """
        Construye la clave de idempotencia.
        Si account_id existe y no es vacío, la clave es (user_id, account_id, broker, order_ref).
        Si no, la clave es (user_id, broker, order_ref).
        """
        if account_id is not None and str(account_id).strip():
            return (user_id, account_id, broker, order_ref)
        return (user_id, broker, order_ref)
    def __init__(self):
        self._store_path = self._build_store_path()
        self._idempotency_store = self._load_store()

    def _build_store_path(self):
        # Deterministically resolve the project root by directory structure (5 levels up from this file)
        here = os.path.abspath(os.path.dirname(__file__))
        project_root = here
        for _ in range(4):
            project_root = os.path.dirname(project_root)
        return os.path.join(project_root, '.minimal_runtime_idempotency_store.json')

    def _serialize_store_key(self, key):
        # key is (user_id, order_ref)
        return f"{key[0]}::{key[1]}"

    def _deserialize_store_key(self, s):
        parts = s.split('::', 1)
        return (parts[0], parts[1])

    def _load_store(self):
        path = self._store_path
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            store = {}
            for k, v in data.items():
                store[self._deserialize_store_key(k)] = v
            return store
        except Exception:
            return {}

    def _save_store(self):
        path = self._store_path
        data = {self._serialize_store_key(k): v for k, v in self._idempotency_store.items()}
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, sort_keys=True)
        except Exception:
            pass

    def submit_intent(
        self,
        *,
        user_id,
        strategy_id,
        broker,
        market,
        symbol,
        side,
        quantity,
        order_ref,
        mode,
        metadata=None
    ):
        import time
        # Normalizar order_ref
        norm_order_ref = normalize_order_ref(order_ref)
        if not norm_order_ref:
            return self._reject(
                stage="input_validation",
                reason="order_ref is required",
                broker=broker,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_ref=order_ref,
            )
        order_ref = norm_order_ref
        account_id = None
        if metadata and isinstance(metadata, dict):
            account_id = metadata.get("account_id")
        idempotency_key = self._build_idempotency_key(user_id, broker, order_ref, account_id=account_id)
        if idempotency_key in self._idempotency_store:
            # Return the stored result, but update idempotency_status and stage for duplicate
            result = self._idempotency_store[idempotency_key].copy()
            result["idempotency_status"] = "duplicate"
            result["stage"] = "idempotency"
            return result
        if broker != "binance":
            return self._reject(
                stage="input_validation",
                reason=f"unsupported broker: {broker}",
                broker=broker,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_ref=order_ref,
            )
        if mode != "stub":
            return self._reject(
                stage="input_validation",
                reason=f"unsupported mode: {mode}",
                broker=broker,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_ref=order_ref,
            )
        if not symbol or not str(symbol).strip():
            return self._reject(
                stage="input_validation",
                reason="symbol is required",
                broker=broker,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_ref=order_ref,
            )        
        if not isinstance(quantity, (int, float)) or quantity <= 0:
            return self._reject(
                stage="input_validation",
                reason="quantity must be > 0",
                broker=broker,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_ref=order_ref,
            )        
        # Risk check
        intent = RiskIntent(
            strategy_id=strategy_id,
            symbol=symbol,
            side=side_norm,
            quantity=quantity,
            broker=broker,
            market=market,
            notional=None,
            metadata=metadata or {},
        )
        risk_decision = RiskEngine().evaluate_intent(intent)
        if not getattr(risk_decision, "approved", False):
            return self._reject(
                stage="risk_check",
                reason="risk engine rejected intent",
                broker=broker,
                symbol=symbol,
                side=side_norm,
                quantity=quantity,
                order_ref=order_ref,
                risk_status="rejected",
            )
        # Simulated submission (stub)
        now = time.time()
        intent_id = f"{user_id}:{order_ref}"
        result = ExecutionResult(
            accepted=True,
            intent_id=intent_id,
            stage="submission",
            reason=None,
            broker=broker,
            symbol=symbol,
            side=side_norm,
            quantity=quantity,
            order_ref=order_ref,
            idempotency_status="ok",
            risk_status="approved",
            intent_status="processed",
            submission_status="simulated_submitted",
            fill_status="not_filled",
            created_at=now,
            processed_at=now,
            portfolio_effect_applied=False,
        )
        # Invariants
        d = result.to_dict()
        assert d["fill_status"] != "filled"
        assert d["accepted"] is True
        assert d["submission_status"] is not None
        assert d["risk_status"] == "approved"
        self._idempotency_store[idempotency_key] = d.copy()
        self._save_store()
        return result.to_dict()

    def _reject(
        self,
        *,
        stage,
        reason,
        broker,
        symbol,
        side,
        quantity,
        order_ref,
        risk_status=None,
    ):
        import time
        intent_id = None
        now = time.time()
        result = ExecutionResult(
            accepted=False,
            intent_id=intent_id,
            stage=stage,
            reason=reason,
            broker=broker,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_ref=order_ref,
            idempotency_status="not_checked",
            risk_status=risk_status,
            intent_status="rejected",
            submission_status=None,
            fill_status="unknown",
            created_at=now,
            processed_at=now,
            portfolio_effect_applied=False,
        )
        d = result.to_dict()
        # Invariants
        assert d["accepted"] is False
        assert d["submission_status"] is None
        assert d["fill_status"] != "filled"
        return result.to_dict()
